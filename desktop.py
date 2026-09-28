"""AI Short Maker desktop application."""
import os
from pathlib import Path
import sys
import threading
import time
import traceback

from PySide6.QtCore import Qt, QThread, Signal, QTimer, QUrl, QSettings
from PySide6.QtGui import QDesktopServices, QPixmap, QFont, QIcon, QFontDatabase
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox, QProgressBar,
    QFileDialog, QFrame, QScrollArea, QPlainTextEdit, QMessageBox, QGridLayout)

from pipeline import Settings, run
from runtime import DATA, ASSETS, Cancelled, hardware, configure_processing

STYLE = """
QWidget { background: #0c111b; color: #e9edf5; font-family: 'Segoe UI'; font-size: 13px; }
QLabel { background: transparent; }
QFrame#sidebar { background: #101725; border-right: 1px solid #243047; }
QFrame#card { background: #151e2e; border: 1px solid #28354b; border-radius: 12px; }
QFrame#card QLabel, QFrame#card QCheckBox { background: transparent; }
QLabel#muted { color: #95a5bf; }
QLabel#eyebrow { color: #64e5c3; font-size: 11px; font-weight: 700; }
QLabel#title { font-size: 30px; font-weight: 700; }
QLabel#section { font-size: 17px; font-weight: 600; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { background: #0d1523; border: 1px solid #33425d; border-radius: 7px; padding: 10px; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border: 1px solid #64e5c3; }
QPushButton { background: #24324a; border: 1px solid #35445f; border-radius: 7px; padding: 10px 16px; font-weight: 600; }
QPushButton:hover { background: #31435f; }
QPushButton#primary { background: #63e5c2; color: #09281f; border: none; font-size: 15px; padding: 14px 24px; }
QPushButton#primary:hover { background: #92f3d9; }
QPushButton:disabled { background: #1d283a; color: #63738c; border-color: #28354b; }
QCheckBox { spacing: 9px; padding: 4px 0; }
QCheckBox::indicator { width: 17px; height: 17px; }
QCheckBox::indicator:unchecked { background: #0d1523; border: 1px solid #65758f; border-radius: 3px; }
QProgressBar { border: none; border-radius: 4px; background: #253148; min-height: 8px; max-height: 8px; }
QProgressBar::chunk { background: #63e5c2; border-radius: 4px; }
QPlainTextEdit { background: #0b1320; color: #aabbd3; border: 1px solid #28354b; border-radius: 7px; font-family: Consolas; font-size: 11px; }
QScrollArea { border: none; }
QScrollBar:vertical { background: #101725; width: 9px; }
QScrollBar::handle:vertical { background: #35445f; border-radius: 4px; min-height: 30px; }
QListWidget, QTableWidget { background: #0d1523; color: #e9edf5; border: 1px solid #33425d; selection-background-color: #314b61; }
QHeaderView::section { background: #24324a; color: #e9edf5; border: none; padding: 7px; }
QSlider::groove:horizontal { background: #253148; height: 6px; border-radius: 3px; }
QSlider::handle:horizontal { background: #63e5c2; width: 14px; margin: -5px 0; border-radius: 6px; }
QToolTip { background: #24324a; color: white; border: 1px solid #456; padding: 5px; }
"""


def label(text, name=None):
    item = QLabel(text)
    item.setWordWrap(True)
    if name:
        item.setObjectName(name)
    return item


def card():
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(22, 20, 22, 20)
    layout.setSpacing(14)
    return frame, layout


class Job(QThread):
    progress = Signal(int, object, str)
    completed = Signal(object)
    failed = Signal(str)
    stopped = Signal(str)
    review_requested = Signal(object)

    def __init__(self, settings, prepared=None):
        super().__init__()
        self.settings = settings
        self.cancel = threading.Event()
        self.prepared = prepared
        self.review_ready = threading.Event()
        self.review_result = None
        self.review_note = None
        self.last_progress_time = 0.
        self.last_progress_stage = None

    def report_progress(self,stage,value,message):
        now = time.monotonic()
        if stage!=self.last_progress_stage or value in (None,1) or now-self.last_progress_time>=.1:
            self.last_progress_time = now
            self.last_progress_stage = stage
            self.progress.emit(stage,value,message)

    def ask_review(self,draft):
        self.review_ready.clear()
        self.review_result = None
        self.review_requested.emit(draft)
        while not self.review_ready.wait(.1):
            if self.cancel.is_set():
                raise Cancelled('Stopped during review.')
        return self.review_result

    def run(self):
        try:
            result = run(self.settings, self.report_progress, self.cancel,review=self.ask_review,prepared=self.prepared)
            self.completed.emit(result)
        except Exception as exc:
            if self.cancel.is_set() or isinstance(exc, Cancelled):
                self.stopped.emit(self.review_note or "Stopped. Any completed shorts are saved in your output folder.")
            else:
                try:
                    DATA.mkdir(parents=True, exist_ok=True)
                    (DATA / "last-error.log").write_text(traceback.format_exc(), encoding="utf-8")
                except OSError:
                    pass
                self.failed.emit(str(exc))


class HardwareJob(QThread):
    ready = Signal(object)

    def run(self):
        try:
            self.ready.emit(hardware())
        except Exception as exc:
            self.ready.emit({"name": "Hardware check unavailable", "cuda": False, "nvenc": False, "error": str(exc)})


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Short Maker")
        self.resize(1180, 920)
        self.setMinimumSize(960, 740)
        self.job = None
        self.result = None
        self.review_dialog = None
        self.started = None
        self.last_log = None
        self.prefs = QSettings("LocalStudio", "AIShortMaker")
        root = QWidget()
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(214)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(24, 32, 24, 28)
        side.setSpacing(16)
        side.addWidget(label("SHORT MAKER", "section"))
        side.addWidget(label("YOUR LOCAL VIDEO STUDIO", "eyebrow"))
        side.addSpacing(24)
        side.addWidget(label("01   Create videos", "section"))
        side.addWidget(label("Paste a link. Find the moment.\nMake it vertical.", "muted"))
        side.addStretch()
        side.addWidget(label("PROCESSING ENGINE", "eyebrow"))
        self.hardware_label = label("Checking CPU + GPU…", "muted")
        side.addWidget(self.hardware_label)
        side.addSpacing(12)
        side.addWidget(label("Local video processing.\nAutomatic online titles.", "muted"))
        outer.addWidget(sidebar)
        scroll = QScrollArea()
        self.scroll = scroll
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll, 1)
        body = QWidget()
        scroll.setWidget(body)
        content = QVBoxLayout(body)
        content.setContentsMargins(32, 28, 32, 28)
        content.setSpacing(18)
        content.addWidget(label("FROM LONG VIDEO TO SHORT STORIES", "eyebrow"))
        content.addWidget(label("What would you like to make?", "title"))
        content.addWidget(label("MrBeast-style challenge stories. Automatic editing, people framing, music and upload copy.", "muted"))

        source_card, source_layout = card()
        source_layout.addWidget(label("1  Add your video", "section"))
        source_row = QHBoxLayout()
        self.source = QLineEdit()
        self.source.setPlaceholderText("Paste a YouTube link or choose a video file")
        source_row.addWidget(self.source, 1)
        self.browse = QPushButton("Choose file")
        self.browse.clicked.connect(self.choose_source)
        source_row.addWidget(self.browse)
        source_layout.addLayout(source_row)
        source_layout.addWidget(label("Use a video you own or have permission to edit. Local files work offline after model setup.", "muted"))
        content.addWidget(source_card)

        options_card, options_layout = card()
        options_layout.addWidget(label("2  Make it yours", "section"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        self.count = QSpinBox()
        self.count.setRange(1, 10)
        self.count.setValue(int(self.prefs.value("count", 3)))
        self.duration = QLabel('Automatic - up to 2 minutes')
        self.edit_mode = QComboBox()
        self.edit_mode.addItem('Reel - automatic length, up to 2 minutes', 'reel')
        self.edit_mode.addItem('Summary video - 4 to 6 minutes', 'summary')
        self.quality = QComboBox()
        self.quality.addItem("1080 × 1920 · Full HD", 1920)
        self.quality.addItem("720 × 1280 · Faster", 1280)
        for column, (name, widget) in enumerate((("Outputs (maximum)", self.count), ("Length", self.duration))):
            grid.addWidget(label(name, "muted"), 0, column)
            grid.addWidget(widget, 1, column)
        options_layout.addWidget(self.edit_mode)
        options_layout.addLayout(grid)
        basic_layout = options_layout
        self.advanced_toggle = QPushButton("More options")
        self.advanced_toggle.setCheckable(True)
        basic_layout.addWidget(self.advanced_toggle)
        self.advanced = QWidget()
        options_layout = QVBoxLayout(self.advanced)
        basic_layout.addWidget(self.advanced)
        self.advanced.hide()
        self.advanced_toggle.toggled.connect(self.advanced.setVisible)
        self.advanced_toggle.toggled.connect(lambda checked: self.advanced_toggle.setText("Fewer options" if checked else "More options"))
        advanced_grid = QGridLayout()
        for column, (name, widget) in enumerate((("Export quality", self.quality),)):
            advanced_grid.addWidget(label(name, "muted"), 0, column)
            advanced_grid.addWidget(widget, 1, column)
        options_layout.addLayout(advanced_grid)
        self.captions = QCheckBox('Word captions')
        self.captions.setChecked(True)
        options_layout.addWidget(self.captions)
        extras = QHBoxLayout()
        self.music_level = QSpinBox()
        self.music_level.setRange(0, 50)
        self.music_level.setSuffix("%")
        self.music_level.setValue(50)
        extras.addWidget(label('Music volume','muted'))
        extras.addWidget(self.music_level)
        options_layout.addLayout(extras)
        options_layout.addWidget(label("Reels use full-screen vertical framing. Summary videos keep the original picture format.", "muted"))
        from music import catalog
        self.music_summary = label(f'Automatic music: {len(catalog())} energetic tracks. Titles, descriptions and 7 hashtags are generated automatically.','muted')
        basic_layout.insertWidget(3, self.music_summary)
        self.review_first = QCheckBox('Optional: review selected sections before export')
        self.review_first.setChecked(False)
        options_layout.addWidget(self.review_first)
        self.caption_style = QComboBox()
        for name in ('classic','clean','bold'):
            self.caption_style.addItem(name.title()+' captions',name)
        self.caption_style.setCurrentIndex(self.caption_style.findData('bold'))
        options_layout.addWidget(self.caption_style)
        self.effects = QCheckBox('Energetic animations: captions, opening title, smooth punch-ins')
        self.effects.setChecked(True)
        basic_layout.insertWidget(5,self.effects)
        self.normalize_audio = QCheckBox('Balance output loudness')
        self.normalize_audio.setChecked(True)
        options_layout.addWidget(self.normalize_audio)
        manual_row = QHBoxLayout()
        self.manual = QCheckBox("Choose exact moment (one reel, up to 120 sec)")
        self.manual_start = QDoubleSpinBox()
        self.manual_end = QDoubleSpinBox()
        for field in (self.manual_start, self.manual_end):
            field.setRange(0, 86400)
            field.setDecimals(2)
            field.setSuffix(" sec")
            field.setEnabled(False)
        self.manual_end.setValue(60)
        self.manual.toggled.connect(self.toggle_manual)
        manual_row.addWidget(self.manual)
        manual_row.addWidget(label("Start", "muted"))
        manual_row.addWidget(self.manual_start)
        manual_row.addWidget(label("End", "muted"))
        manual_row.addWidget(self.manual_end)
        options_layout.addLayout(manual_row)
        output_row = QHBoxLayout()
        saved_output = str(self.prefs.value("output", str(DATA / "shorts")))
        if Path(saved_output) == DATA / "outputs":
            saved_output = str(DATA / "shorts")
        self.output = QLineEdit(saved_output)
        self.output.setReadOnly(True)
        output_row.addWidget(self.output, 1)
        self.output_browse = QPushButton("Save to…")
        self.output_browse.clicked.connect(self.choose_output)
        output_row.addWidget(self.output_browse)
        options_layout.addLayout(output_row)
        options_layout.addWidget(label("Saved in shorts / video title. Downloaded originals are deleted after successful export; local files are kept.", "muted"))
        options_layout.addWidget(label("Length follows the selected story. Reels stay within 2 minutes; summaries target 4-6 minutes. Short sources are never padded. Review exports before sharing.", "muted"))
        content.addWidget(options_card)

        actions = QHBoxLayout()
        self.generate = QPushButton("Generate shorts  →")
        self.generate.setObjectName("primary")
        self.generate.clicked.connect(self.start)
        actions.addWidget(self.generate)
        self.resume_button = QPushButton('Open draft')
        self.resume_button.clicked.connect(self.open_draft)
        actions.addWidget(self.resume_button)
        self.cancel_button = QPushButton("Stop")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.stop)
        actions.addWidget(self.cancel_button)
        actions.addStretch()
        self.elapsed = label("Ready when you are", "muted")
        actions.addWidget(self.elapsed)
        content.addLayout(actions)

        progress_card, progress_layout = card()
        self.status = label("Ready to create", "section")
        progress_layout.addWidget(self.status)
        self.overall = QProgressBar()
        self.overall.setValue(0)
        self.overall.setTextVisible(False)
        progress_layout.addWidget(self.overall)
        stages = QHBoxLayout()
        self.stage_bars = []
        self.stage_labels = []
        for name in ("Download", "Transcribe", "Select moments", "Frame + export"):
            column = QVBoxLayout()
            title = label(name, "muted")
            column.addWidget(title)
            bar = QProgressBar()
            bar.setTextVisible(False)
            bar.setValue(0)
            column.addWidget(bar)
            stages.addLayout(column)
            self.stage_bars.append(bar)
            self.stage_labels.append(title)
        progress_layout.addLayout(stages)
        self.detail = label("The first run may download a speech model. Processing continues in the background.", "muted")
        progress_layout.addWidget(self.detail)
        self.log_button = QPushButton("Show activity")
        self.log_button.clicked.connect(self.toggle_log)
        progress_layout.addWidget(self.log_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(250)
        self.log.setFixedHeight(140)
        self.log.hide()
        progress_layout.addWidget(self.log)
        content.addWidget(progress_card)

        self.result_card, self.result_layout = card()
        self.result_card.hide()
        content.addWidget(self.result_card)
        content.addStretch()
        self.inputs = [self.edit_mode, self.source, self.browse, self.count, self.duration, self.quality, self.captions, self.output_browse]
        self.inputs += [self.music_level, self.manual, self.manual_start, self.manual_end]
        self.inputs += [self.review_first,self.caption_style,self.normalize_audio,self.resume_button,self.effects]
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(1000)
        self.edit_mode.currentIndexChanged.connect(self.change_format)
        self.change_format()
        self.hardware_job = HardwareJob()
        self.hardware_job.ready.connect(self.hardware_ready)
        self.hardware_job.start()

    def change_format(self, index=None):
        is_summary = self.edit_mode.currentData() == 'summary'
        self.duration.setText('Automatic - 4 to 6 minutes' if is_summary else 'Automatic - up to 2 minutes')
        self.music_level.setValue(18 if is_summary else 50)
        self.caption_style.setCurrentIndex(self.caption_style.findData('clean' if is_summary else 'bold'))
        self.effects.setChecked(not is_summary)
        self.manual.setChecked(False)
        self.manual.setEnabled(not is_summary)
        if is_summary:
            self.count.setValue(1)
        self.generate.setText('Generate summary video' if is_summary else 'Generate reels')

    def hardware_ready(self, info):
        self.hardware_label.setText(f"{info['name']}\n\nCPU · tracking + captions\nCUDA · {'available' if info['cuda'] else 'unavailable'}\nNVENC · {'verified' if info['nvenc'] else 'CPU fallback'}")

    def choose_source(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose video", "", "Videos (*.mp4 *.mkv *.mov *.webm *.avi *.m4v);;All files (*)")
        if path:
            self.source.setText(path)

    def choose_output(self):
        path = QFileDialog.getExistingDirectory(self, "Save shorts to", self.output.text())
        if path:
            self.output.setText(path)

    def toggle_manual(self, checked):
        self.manual_start.setEnabled(checked)
        self.manual_end.setEnabled(checked)
        self.count.setEnabled(not checked)
        self.duration.setEnabled(not checked)

    def toggle_log(self):
        self.log.setVisible(not self.log.isVisible())
        self.log_button.setText("Hide activity" if self.log.isVisible() else "Show activity")

    def start(self, checked=False, prepared=None):
        if self.job and self.job.isRunning():
            return
        prepared_settings = None
        if prepared is not None:
            try:
                prepared_settings = Settings(source=prepared['source'],**prepared['settings'])
            except (KeyError,TypeError,ValueError) as exc:
                QMessageBox.warning(self,'Cannot open draft',str(exc))
                return
        if not self.source.text().strip():
            self.source.setFocus()
            self.detail.setText("Paste a video URL or choose a local video first.")
            return
        if self.manual.isChecked() and self.manual_end.value() <= self.manual_start.value():
            self.detail.setText("The end of your chosen moment must be after its start.")
            return
        self.prefs.setValue("output", self.output.text())
        self.prefs.setValue("count", self.count.value())
        self.result_card.hide()
        self.log.clear()
        self.last_log = None
        self.overall.setValue(0)
        for bar in self.stage_bars:
            bar.setRange(0, 100)
            bar.setValue(0)
        for widget in self.inputs:
            widget.setEnabled(False)
        self.generate.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.started = time.monotonic()
        settings = Settings(source=self.source.text().strip(),output=self.output.text(),count=self.count.value(),duration=360 if self.edit_mode.currentData()=="summary" else 120,height=self.quality.currentData(),captions=self.captions.isChecked())
        settings.output_type = self.edit_mode.currentData()
        settings.auto_duration = True
        settings.edit_mode = "summary"
        settings.music_level = self.music_level.value()/100
        settings.use_groq = True
        settings.review = self.review_first.isChecked()
        settings.caption_style = self.caption_style.currentData()
        settings.effects = "energetic" if self.effects.isChecked() else "off"
        settings.normalize_audio = self.normalize_audio.isChecked()
        if self.manual.isChecked():
            settings.manual_start = self.manual_start.value()
            settings.manual_end = self.manual_end.value()
        if prepared is not None:
            settings = prepared_settings
            settings.selection = 'challenge'
            settings.model = 'small'
            settings.framing = 'fill'
            settings.music = 'auto'
            settings.review = True
            settings.use_groq = True
        self.job = Job(settings,prepared=prepared)
        self.job.review_requested.connect(self.review_clips)
        self.job.progress.connect(self.progress)
        self.job.completed.connect(self.completed)
        self.job.failed.connect(self.failed)
        self.job.stopped.connect(self.stopped)
        self.job.finished.connect(self.unlock)
        self.job.start()
        QTimer.singleShot(100, lambda: self.scroll.ensureWidgetVisible(self.status, 0, 30))

    def open_draft(self):
        from projects import load_draft
        path,_ = QFileDialog.getOpenFileName(self,'Resume a saved draft',str(DATA/'projects'),'Short Maker drafts (*.shortmaker.json)')
        if not path:
            return
        try:
            prepared = load_draft(path)
            self.source.setText(prepared['source'])
            self.manual.setChecked(False)
            self.start(prepared=prepared)
        except (ValueError,OSError,KeyError,TypeError) as exc:
            QMessageBox.warning(self,'Cannot open draft',str(exc))

    def review_clips(self,draft):
        job = self.job
        if job.cancel.is_set():
            job.review_ready.set()
            return
        try:
            from review import ReviewDialog, SummaryReviewDialog
            dialog_type = SummaryReviewDialog if (draft["settings"].get("output_type")=="summary" or any(c.get("spans") for c in draft["clips"])) else ReviewDialog
            self.review_dialog = dialog_type(draft,self)
            self.review_dialog.exec()
            job.review_result = self.review_dialog.result_state
            if job.review_result is None:
                job.review_note = f'Draft saved: {self.review_dialog.draft_path}. Use Open draft to resume.'
        except Exception as exc:
            self.log.appendPlainText(f'Review could not open: {exc}')
            QMessageBox.warning(self,'Review unavailable',str(exc))
        finally:
            self.review_dialog = None
            job.review_ready.set()

    def progress(self, stage, fraction, message):
        titles = ["Downloading your video", "Listening and transcribing", "Finding clip candidates", "Framing and exporting"]
        self.status.setText(titles[stage])
        self.detail.setText(message)
        for i in range(stage):
            self.stage_bars[i].setRange(0, 100)
            self.stage_bars[i].setValue(100)
        bar = self.stage_bars[stage]
        if fraction is None:
            bar.setRange(0, 0)
        else:
            bar.setRange(0, 100)
            bar.setValue(round(fraction * 100))
        weights = [15, 30, 5, 50]
        overall = sum(weights[:stage]) + weights[stage] * (fraction or 0)
        self.overall.setValue(max(self.overall.value(), round(overall)))
        # Keep activity useful instead of logging every frame.
        key = (stage, int((fraction or 0) * 10), message if fraction is None else "")
        if key != self.last_log:
            self.log.appendPlainText(message)
            self.last_log = key

    def stop(self):
        if self.job:
            self.job.cancel.set()
            self.cancel_button.setEnabled(False)
            self.detail.setText("Stopping after the current processing operation…")

    def unlock(self):
        for widget in self.inputs:
            widget.setEnabled(True)
        self.toggle_manual(self.manual.isChecked())
        self.manual.setEnabled(self.edit_mode.currentData() != "summary")
        self.generate.setEnabled(True)
        self.cancel_button.setEnabled(False)
        for bar in self.stage_bars:
            if bar.maximum() == 0:
                bar.setRange(0, 100)
        self.tick()
        self.started = None

    def tick(self):
        if self.started is not None:
            seconds = int(time.monotonic() - self.started)
            self.elapsed.setText(f"Elapsed {seconds // 60:02}:{seconds % 60:02}")

    def failed(self, message):
        self.status.setText("Could not finish this video")
        self.detail.setText(message)
        self.log.appendPlainText(message)
        self.log.show()
        self.log_button.setText("Hide activity")

    def stopped(self, message):
        self.status.setText("Stopped")
        self.detail.setText(message)

    def completed(self, result):
        self.result = result
        self.overall.setValue(100)
        self.status.setText(f"Your {len(result['clips'])} videos are ready")
        self.detail.setText("Open a video to review it, or open the folder for exports and captions.")
        if result.get("cleanup_warning"):
            self.detail.setText(result["cleanup_warning"])
        elif result.get("source_deleted"):
            self.detail.setText("Shorts saved and verified. The downloaded full video has been deleted.")
        while self.result_layout.count():
            item = self.result_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.result_layout.addWidget(label(f"Your videos ({len(result['clips'])}/{result.get('requested_count', len(result['clips']))})", "section"))
        if result.get("count_warning"):
            self.result_layout.addWidget(label(result["count_warning"]))
        for i, clip in enumerate(result["clips"]):
            row = QWidget()
            layout = QHBoxLayout(row)
            image = QLabel()
            pix = QPixmap(str(Path(clip["path"]).with_suffix(".jpg")))
            image.setPixmap(pix.scaled(64, 114, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            layout.addWidget(image)
            text = label(f"{i+1:02}  {clip.get('youtube',{}).get('title',clip['title'])}\n\n{clip.get('story', {}).get('duration', clip['end']-clip['start']):.0f} seconds · 9:16 · {clip['encoder']}")
            layout.addWidget(text, 1)
            button = QPushButton("Play video")
            button.clicked.connect(lambda checked=False, p=clip["path"]: QDesktopServices.openUrl(QUrl.fromLocalFile(p)))
            layout.addWidget(button)
            if clip.get("youtube"):
                details = QPushButton("Post caption")
                details.clicked.connect(lambda checked=False, p=clip["youtube"]["file"]: QDesktopServices.openUrl(QUrl.fromLocalFile(p)))
                layout.addWidget(details)
            if clip.get('quality'):
                checks = QPushButton('Export checks')
                checks.clicked.connect(lambda checked=False,p=clip['quality']['file']:QDesktopServices.openUrl(QUrl.fromLocalFile(p)))
                layout.addWidget(checks)
            self.result_layout.addWidget(row)
            warnings = list(clip.get("quality",{}).get("warnings",[]))
            if clip.get('youtube', {}).get('warning'):
                warnings = warnings + [clip['youtube']['warning']]
            for warning in warnings:
                self.result_layout.addWidget(label(warning, 'muted'))
        if result.get('publishing_desk'):
            desk = QPushButton('Open publishing desk')
            desk.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(result['publishing_desk'])))
            self.result_layout.addWidget(desk)
        folder = QPushButton("Open output folder")
        folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(result["folder"])))
        self.result_layout.addWidget(folder)
        self.result_card.show()
        QTimer.singleShot(100, lambda: self.scroll.ensureWidgetVisible(self.result_card, 0, 20))

    def closeEvent(self, event):
        if self.job and self.job.isRunning():
            self.stop()
            self.detail.setText("Stopping safely. Close the app again once processing stops.")
            event.ignore()
            return
        if self.hardware_job.isRunning():
            event.ignore()
            return
        event.accept()


def main():
    configure_processing()
    # Windowed EXEs have no console; libraries still expect usable streams.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")
    if "--verify-install" in sys.argv:
        from installation_check import verify
        index = sys.argv.index("--verify-install")
        return verify(sys.argv[index + 1], sys.argv[index + 2])
    app = QApplication(sys.argv)
    # The offscreen Windows Qt plugin does not discover system fonts itself.
    fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    for filename in ("segoeui.ttf", "segoeuib.ttf"):
        if (fonts / filename).exists():
            QFontDatabase.addApplicationFont(str(fonts / filename))
    app.setFont(QFont("Segoe UI", 10))
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    if '--verify-preview' in sys.argv:
        from installation_check import verify_preview
        index = sys.argv.index('--verify-preview')
        return verify_preview(app,sys.argv[index+1],sys.argv[index+2])
    icon = ASSETS / "assets/app.ico"
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))
    window = Window()
    window.show()
    if "--ui-smoke" in sys.argv:
        def capture():
            DATA.mkdir(parents=True, exist_ok=True)
            window.grab().save(str(DATA / "desktop-preview.png"))
            if window.hardware_job.isRunning():
                QTimer.singleShot(500, capture)
            else:
                app.quit()
        QTimer.singleShot(2500, capture)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
