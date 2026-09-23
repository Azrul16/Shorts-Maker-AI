"""AI Short Maker desktop application."""
import json
import os
from pathlib import Path
import sys
import threading
import time
import traceback

from PySide6.QtCore import Qt, QThread, Signal, QTimer, QUrl, QSettings
from PySide6.QtGui import QDesktopServices, QPixmap, QFont, QIcon, QFontDatabase
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QSpinBox, QCheckBox, QProgressBar,
    QFileDialog, QFrame, QScrollArea, QPlainTextEdit, QMessageBox, QGridLayout)

from pipeline import Settings, run
from runtime import DATA, ASSETS, Cancelled, hardware

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
QLineEdit, QComboBox, QSpinBox { background: #0d1523; border: 1px solid #33425d; border-radius: 7px; padding: 10px; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border: 1px solid #64e5c3; }
QPushButton { background: #24324a; border: 1px solid #35445f; border-radius: 7px; padding: 10px 16px; font-weight: 600; }
QPushButton:hover { background: #31435f; }
QPushButton#primary { background: #63e5c2; color: #09281f; border: none; font-size: 15px; padding: 14px 24px; }
QPushButton#primary:hover { background: #92f3d9; }
QPushButton:disabled { background: #1d283a; color: #63738c; border-color: #28354b; }
QCheckBox { spacing: 9px; padding: 4px 0; }
QCheckBox::indicator { width: 17px; height: 17px; }
QProgressBar { border: none; border-radius: 4px; background: #253148; min-height: 8px; max-height: 8px; }
QProgressBar::chunk { background: #63e5c2; border-radius: 4px; }
QPlainTextEdit { background: #0b1320; color: #aabbd3; border: 1px solid #28354b; border-radius: 7px; font-family: Consolas; font-size: 11px; }
QScrollArea { border: none; }
QScrollBar:vertical { background: #101725; width: 9px; }
QScrollBar::handle:vertical { background: #35445f; border-radius: 4px; min-height: 30px; }
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

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.cancel = threading.Event()

    def run(self):
        try:
            result = run(self.settings, self.progress.emit, self.cancel)
            self.completed.emit(result)
        except Exception as exc:
            if self.cancel.is_set() or isinstance(exc, Cancelled):
                self.stopped.emit("Stopped. Any completed shorts are saved in your output folder.")
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
        side.addWidget(label("01   Create shorts", "section"))
        side.addWidget(label("Paste a link. Find the moment.\nMake it vertical.", "muted"))
        side.addStretch()
        side.addWidget(label("PROCESSING ENGINE", "eyebrow"))
        self.hardware_label = label("Checking CPU + GPU…", "muted")
        side.addWidget(self.hardware_label)
        side.addSpacing(12)
        side.addWidget(label("Runs on your computer.\nNo cloud processing fees.", "muted"))
        outer.addWidget(sidebar)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll, 1)
        body = QWidget()
        scroll.setWidget(body)
        content = QVBoxLayout(body)
        content.setContentsMargins(32, 28, 32, 28)
        content.setSpacing(18)
        content.addWidget(label("FROM LONG VIDEO TO SHORT STORIES", "eyebrow"))
        content.addWidget(label("Your next short starts here.", "title"))
        content.addWidget(label("Automatic highlights, smooth face framing, and captions — made locally.", "muted"))

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
        self.duration = QComboBox()
        for seconds in (30, 40, 60):
            self.duration.addItem(f"About {seconds} seconds", seconds)
        self.duration.setCurrentIndex(1)
        self.model = QComboBox()
        self.model.addItem("Balanced · small", "small")
        self.model.addItem("More accurate · medium", "medium")
        self.model.addItem("Fast draft · base", "base")
        self.model.setToolTip("Medium takes more memory and downloads its model on first use. Small is the default for a 4 GB GPU.")
        self.quality = QComboBox()
        self.quality.addItem("1080 × 1920 · Full HD", 1920)
        self.quality.addItem("720 × 1280 · Faster", 1280)
        for column, (name, widget) in enumerate((("Shorts", self.count), ("Target length", self.duration), ("Transcription", self.model), ("Export quality", self.quality))):
            grid.addWidget(label(name, "muted"), 0, column)
            grid.addWidget(widget, 1, column)
        options_layout.addLayout(grid)
        toggles = QHBoxLayout()
        self.follow = QCheckBox("Follow faces")
        self.zoom = QCheckBox("Auto zoom")
        self.captions = QCheckBox("Word captions")
        self.gpu = QCheckBox("Use NVIDIA GPU")
        for check in (self.follow, self.zoom, self.captions, self.gpu):
            check.setChecked(True)
            toggles.addWidget(check)
        self.follow.toggled.connect(self.zoom.setEnabled)
        options_layout.addLayout(toggles)
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
        options_layout.addWidget(label("Lengths follow speech boundaries. Local scoring finds candidate moments; review your shorts before sharing.", "muted"))
        content.addWidget(options_card)

        actions = QHBoxLayout()
        self.generate = QPushButton("Generate shorts  →")
        self.generate.setObjectName("primary")
        self.generate.clicked.connect(self.start)
        actions.addWidget(self.generate)
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
        self.inputs = [self.source, self.browse, self.count, self.duration, self.model, self.quality, self.follow, self.zoom, self.captions, self.gpu, self.output_browse]
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(1000)
        self.hardware_job = HardwareJob()
        self.hardware_job.ready.connect(self.hardware_ready)
        self.hardware_job.start()

    def hardware_ready(self, info):
        self.hardware_label.setText(f"{info['name']}\n\nCPU · face tracking + captions\nCUDA · {'available' if info['cuda'] else 'unavailable'}\nNVENC · {'verified' if info['nvenc'] else 'CPU fallback'}")

    def choose_source(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose video", "", "Videos (*.mp4 *.mkv *.mov *.webm *.avi *.m4v);;All files (*)")
        if path:
            self.source.setText(path)

    def choose_output(self):
        path = QFileDialog.getExistingDirectory(self, "Save shorts to", self.output.text())
        if path:
            self.output.setText(path)

    def toggle_log(self):
        self.log.setVisible(not self.log.isVisible())
        self.log_button.setText("Hide activity" if self.log.isVisible() else "Show activity")

    def start(self):
        if self.job and self.job.isRunning():
            return
        if not self.source.text().strip():
            self.source.setFocus()
            self.detail.setText("Paste a video URL or choose a local video first.")
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
        settings = Settings(self.source.text().strip(), self.output.text(), self.count.value(), self.duration.currentData(), self.model.currentData(), self.quality.currentData(), self.follow.isChecked(), self.zoom.isChecked() and self.follow.isChecked(), self.captions.isChecked(), self.gpu.isChecked())
        self.job = Job(settings)
        self.job.progress.connect(self.progress)
        self.job.completed.connect(self.completed)
        self.job.failed.connect(self.failed)
        self.job.stopped.connect(self.stopped)
        self.job.finished.connect(self.unlock)
        self.job.start()

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
        self.zoom.setEnabled(self.follow.isChecked())
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
        self.status.setText(f"Your {len(result['clips'])} shorts are ready")
        self.detail.setText("Open a short to review it, or open the folder for all exports and captions.")
        if result.get("cleanup_warning"):
            self.detail.setText(result["cleanup_warning"])
        elif result.get("source_deleted"):
            self.detail.setText("Shorts saved and verified. The downloaded full video has been deleted.")
        while self.result_layout.count():
            item = self.result_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.result_layout.addWidget(label("Your shorts", "section"))
        for i, clip in enumerate(result["clips"]):
            row = QWidget()
            layout = QHBoxLayout(row)
            image = QLabel()
            pix = QPixmap(str(Path(clip["path"]).with_suffix(".jpg")))
            image.setPixmap(pix.scaled(64, 114, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            layout.addWidget(image)
            text = label(f"{i+1:02}  {clip['title']}\n\n{clip['end']-clip['start']:.0f} seconds · 9:16 · {clip['encoder']}")
            layout.addWidget(text, 1)
            button = QPushButton("Play short")
            button.clicked.connect(lambda checked=False, p=clip["path"]: QDesktopServices.openUrl(QUrl.fromLocalFile(p)))
            layout.addWidget(button)
            self.result_layout.addWidget(row)
        folder = QPushButton("Open output folder")
        folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(result["folder"])))
        self.result_layout.addWidget(folder)
        self.result_card.show()

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
