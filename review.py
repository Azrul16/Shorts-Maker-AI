"""Local pre-export review: trim, captions, and click-to-correct crop paths."""
import copy
import time
import uuid
import cv2
from PySide6.QtCore import Qt, QTimer, Signal, QRectF
from PySide6.QtGui import QImage, QPainter, QColor, QPen
from PySide6.QtWidgets import (QDialog,QCheckBox,QVBoxLayout,QHBoxLayout,QGridLayout,QLabel,QPushButton,
    QListWidget,QListWidgetItem,QSlider,QDoubleSpinBox,QLineEdit,QComboBox,QTableWidget,
    QTableWidgetItem,QHeaderView,QMessageBox,QAbstractItemView,QSplitter,QWidget)
from captions import correct_segment
from projects import atomic_json,validate_draft
from runtime import DATA
from preview import PreviewWorker


class SummaryReviewDialog(QDialog):
    """Review source provenance and choose complete summaries before export."""
    def __init__(self, draft, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Review story summaries')
        self.resize(1000, 700)
        self.state = copy.deepcopy(draft)
        self.result_state = None
        self.draft_path = DATA/'projects'/f'{time.strftime("%Y%m%d-%H%M%S")}-{uuid.uuid4().hex[:8]}.shortmaker.json'
        layout = QVBoxLayout(self)
        hint = QLabel('Sections are joined in source order. Check that the setup and outcome belong to the same story. Select a summary to read its source dialogue; watch the finished edit in the publishing desk.')
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.clips = QListWidget()
        for i, clip in enumerate(self.state['clips']):
            duration = sum(s['end']-s['start'] for s in clip.get('spans', [])) or clip['end']-clip['start']
            item = QListWidgetItem(f'{i+1}. {clip["title"]} ({duration:.1f}s)')
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if draft.get('checked', [True]*len(draft['clips']))[i] else Qt.CheckState.Unchecked)
            self.clips.addItem(item)
        layout.addWidget(self.clips, 1)
        self.sections = QTableWidget(0, 4)
        self.sections.setHorizontalHeaderLabels(['Output time', 'Source time', 'Role', 'Retained dialogue'])
        self.sections.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.sections.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.sections, 3)
        self.status = QLabel()
        layout.addWidget(self.status)
        buttons = QHBoxLayout()
        for title, callback in [('Save draft', self.save_draft), ('Export selected summaries', self.accept_edits)]:
            button = QPushButton(title)
            button.clicked.connect(callback)
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.clips.currentRowChanged.connect(self.show_sections)
        self.clips.setCurrentRow(0)

    def show_sections(self, index):
        if index < 0:
            return
        clip = self.state['clips'][index]
        spans = clip.get('spans') or [dict(start=clip['start'], end=clip['end'], role='complete source', evidence=clip['title'])]
        self.sections.setRowCount(len(spans))
        offset = 0.
        for row, span in enumerate(spans):
            length = span['end']-span['start']
            values = [f'{offset:.1f}-{offset+length:.1f}s', f'{span["start"]:.1f}-{span["end"]:.1f}s', span.get('role', ''), span.get('evidence', '')]
            for column, value in enumerate(values):
                self.sections.setItem(row, column, QTableWidgetItem(value))
            offset += length
        self.sections.resizeRowsToContents()

    def save_draft(self):
        self.state['checked'] = [self.clips.item(i).checkState() == Qt.CheckState.Checked for i in range(self.clips.count())]
        try:
            validate_draft(self.state)
            atomic_json(self.draft_path, self.state)
        except (ValueError, OSError) as exc:
            self.status.setText(str(exc))
            return False
        self.status.setText(f'Draft saved: {self.draft_path}')
        return True

    def accept_edits(self):
        if not self.save_draft():
            return
        selected = [c for i, c in enumerate(self.state['clips']) if self.state['checked'][i]]
        if not selected:
            self.status.setText('Select at least one summary.')
            return
        self.result_state = {**self.state, 'clips': selected, 'checked': [True]*len(selected)}
        self.accept()

    def reject(self):
        if self.save_draft():
            super().reject()


class FrameView(QWidget):
    clicked = Signal(float,float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.image = None
        self.crop_rect = None
        self.target_rect = QRectF()
        self.setMinimumSize(280,180)

    def set_frame(self, frame, camera=None):
        rgb = cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
        self.image = QImage(rgb.data,rgb.shape[1],rgb.shape[0],rgb.strides[0],QImage.Format.Format_RGB888).copy()
        self.crop_rect = None
        if camera is not None:
            x,y,h = camera
            self.crop_rect = (x-h*9/32,y-h/2,h*9/16,h)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(),QColor('#080d15'))
        if self.image is None:
            return
        size = self.image.size().scaled(self.size(),Qt.AspectRatioMode.KeepAspectRatio)
        self.target_rect = QRectF((self.width()-size.width())/2,(self.height()-size.height())/2,size.width(),size.height())
        painter.drawImage(self.target_rect,self.image)
        if self.crop_rect:
            x,y,w,h = self.crop_rect
            sx,sy = size.width()/self.image.width(),size.height()/self.image.height()
            painter.setPen(QPen(QColor('#63e5c2'),2))
            painter.drawRect(QRectF(self.target_rect.x()+x*sx,self.target_rect.y()+y*sy,w*sx,h*sy))

    def mousePressEvent(self,event):
        if self.image and self.target_rect.contains(event.position()):
            self.clicked.emit((event.position().x()-self.target_rect.x())/self.target_rect.width(),
                              (event.position().y()-self.target_rect.y())/self.target_rect.height())


class ReviewDialog(QDialog):
    def __init__(self, draft, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Review shorts before export')
        self.resize(1180,880)
        self.state = copy.deepcopy(draft)
        self.result_state = None
        self.index = -1
        self.position = 0.
        self.frame = None
        self.loading = False
        self.caption_rows = []
        self.fps = self.state['media'].get('fps') or 30
        self.request_token = 0
        self.preview_busy = False
        self.closing_result = None
        self.worker = PreviewWorker(self.state['source'],self,transcript=self.state['transcript'])
        self.worker.ready.connect(self.preview_ready)
        self.worker.failed.connect(self.preview_failed)
        self.worker.finished.connect(self.preview_finished)
        self.seek_timer = QTimer(self)
        self.seek_timer.setSingleShot(True)
        self.seek_timer.setInterval(80)
        self.seek_timer.timeout.connect(self.request_preview)
        self.worker.start()
        self.draft_path = DATA/'projects'/f'{time.strftime("%Y%m%d-%H%M%S")}-{uuid.uuid4().hex[:8]}.shortmaker.json'
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.next_frame)
        layout = QVBoxLayout(self)
        title = QLabel('Review the moment. Keep the action in frame.')
        title.setStyleSheet('font-size:22px;font-weight:600')
        layout.addWidget(title)
        self.hint = QLabel('Silent crop preview; captions and music are applied on export. Click the subject in the source frame to add crop points as it moves. Clear points to restore automatic tracking.')
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        split = QSplitter()
        self.clips = QListWidget()
        self.clips.setMaximumWidth(235)
        for number,clip in enumerate(self.state['clips']):
            item = QListWidgetItem(f'{number+1:02}  {clip["title"]}\n{clip["end"]-clip["start"]:.1f} sec')
            item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable)
            checked = self.state.get('checked',[True]*len(self.state['clips']))[number]
            item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
            self.clips.addItem(item)
        split.addWidget(self.clips)
        preview = QWidget()
        preview_layout = QHBoxLayout(preview)
        self.source_view = FrameView()
        self.source_view.clicked.connect(self.add_point)
        preview_layout.addWidget(self.source_view,3)
        self.output_view = FrameView()
        self.output_view.setMinimumWidth(180)
        preview_layout.addWidget(self.output_view,1)
        split.addWidget(preview)
        layout.addWidget(split,3)
        play_row = QHBoxLayout()
        self.play = QPushButton('Play preview')
        self.play.clicked.connect(self.toggle_play)
        play_row.addWidget(self.play)
        self.scrub = QSlider(Qt.Orientation.Horizontal)
        self.scrub.setRange(0,round(self.state['media']['duration']*1000))
        self.scrub.sliderPressed.connect(self.pause)
        self.scrub.valueChanged.connect(self.seek_slider)
        play_row.addWidget(self.scrub,1)
        self.clock = QLabel('0.00 sec')
        play_row.addWidget(self.clock)
        layout.addLayout(play_row)
        edit = QGridLayout()
        self.title_edit = QLineEdit()
        self.title_edit.setMaxLength(300)
        edit.addWidget(QLabel('Clip title'),0,0)
        edit.addWidget(self.title_edit,0,1,1,5)
        self.begin = QDoubleSpinBox()
        self.end = QDoubleSpinBox()
        for field in (self.begin,self.end):
            field.setRange(0,self.state['media']['duration'])
            field.setDecimals(2)
            field.setSuffix(' sec')
            field.valueChanged.connect(self.trim_changed)
        edit.addWidget(QLabel('Start / end'),1,0)
        edit.addWidget(self.begin,1,1)
        edit.addWidget(self.end,1,2)
        mark_in = QPushButton('Start here')
        mark_out = QPushButton('End here')
        mark_in.clicked.connect(lambda:self.begin.setValue(self.position))
        mark_out.clicked.connect(lambda:self.end.setValue(self.position))
        edit.addWidget(mark_in,1,3)
        edit.addWidget(mark_out,1,4)
        self.style = QComboBox()
        for name in ('classic','clean','bold'):
            self.style.addItem(name.title(),name)
        edit.addWidget(QLabel('Caption style'),2,0)
        edit.addWidget(self.style,2,1)
        self.effects = QCheckBox('Energetic animations')
        self.effects.toggled.connect(self.fields_changed)
        edit.addWidget(self.effects,4,1,1,3)
        self.zoom = QDoubleSpinBox()
        self.zoom.setRange(1,2)
        self.zoom.setSingleStep(.05)
        self.zoom.setValue(1.06)
        self.zoom.setSuffix('x')
        edit.addWidget(QLabel('Crop point zoom'),2,2)
        edit.addWidget(self.zoom,2,3)
        clear = QPushButton('Clear crop points')
        clear.clicked.connect(self.clear_points)
        edit.addWidget(clear,2,4)
        self.point_count = QLabel('Automatic tracking')
        edit.addWidget(self.point_count,3,0,1,2)
        self.points = QComboBox()
        self.points.activated.connect(self.go_to_point)
        edit.addWidget(self.points,3,2,1,2)
        remove = QPushButton('Remove point')
        remove.clicked.connect(self.remove_point)
        edit.addWidget(remove,3,4)
        layout.addLayout(edit)
        self.captions = QTableWidget(0,2)
        self.captions.setHorizontalHeaderLabels(['Time','Caption text — double-click to correct'])
        self.captions.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.ResizeToContents)
        self.captions.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch)
        self.captions.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.captions.setMaximumHeight(155)
        self.captions.cellChanged.connect(self.caption_changed)
        layout.addWidget(self.captions,1)
        self.status = QLabel('Drafts are saved locally. Original video remains until export finishes.')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        buttons = QHBoxLayout()
        save = QPushButton('Save draft')
        save.clicked.connect(self.save_draft)
        buttons.addWidget(save)
        buttons.addStretch()
        cancel = QPushButton('Save and close')
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        export = QPushButton('Export checked clips')
        export.setObjectName('primary')
        export.clicked.connect(self.accept_edits)
        buttons.addWidget(export)
        layout.addLayout(buttons)
        self.clips.currentRowChanged.connect(self.select_clip)
        self.title_edit.textChanged.connect(self.fields_changed)
        self.style.currentIndexChanged.connect(self.fields_changed)
        self.clips.setCurrentRow(0)
        self.save_draft()

    def current_clip(self):
        return self.state['clips'][self.index]

    def pause(self):
        self.timer.stop()
        self.play.setText('Play preview')

    def toggle_play(self):
        if self.timer.isActive():
            self.pause()
        else:
            if self.position >= self.current_clip()['end']-.05:
                self.seek(self.current_clip()['start'])
            self.timer.start(round(1000/min(15,self.fps)))
            self.play.setText('Pause')

    def reset_camera(self):
        clip = self.current_clip()
        points = clip.get('crop_keyframes',[])
        self.point_count.setText(f'{len(points)} crop points. Manual path overrides auto tracking for this clip.' if points else 'Automatic tracking — play to let tracking settle.')
        self.point_count.setWordWrap(True)
        self.points.clear()
        for point in points:
            self.points.addItem(f"{point['time']:.2f}s — {point['zoom']:.2f}x",point['time'])
        if points:
            self.points.setCurrentIndex(min(range(len(points)), key=lambda i: abs(points[i]['time']-self.position)))

    def select_clip(self,index):
        if index<0:
            return
        self.pause()
        self.index = index
        clip = self.current_clip()
        self.loading = True
        self.title_edit.setText(clip['title'])
        self.begin.setValue(clip['start'])
        self.end.setValue(clip['end'])
        self.style.setCurrentIndex(self.style.findData(clip.get('caption_style','classic')))
        self.effects.setChecked(clip.get('effects','off')=='energetic')
        self.loading = False
        self.populate_captions()
        self.seek(clip['start'])

    def populate_captions(self):
        clip = self.current_clip()
        self.loading = True
        self.caption_rows = [i for i,s in enumerate(self.state['transcript']) if s['end']>clip['start'] and s['start']<clip['end']]
        self.captions.setRowCount(len(self.caption_rows))
        for row,index in enumerate(self.caption_rows):
            segment = self.state['transcript'][index]
            item = QTableWidgetItem(f'{segment["start"]:.1f}–{segment["end"]:.1f}')
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.captions.setItem(row,0,item)
            self.captions.setItem(row,1,QTableWidgetItem(segment['text']))
        self.loading = False

    def fields_changed(self,*args):
        if self.loading or self.index<0:
            return
        self.current_clip()['title'] = self.title_edit.text().strip() or 'Untitled clip'
        self.current_clip()['caption_style'] = self.style.currentData()
        self.current_clip()['effects'] = 'energetic' if self.effects.isChecked() else 'off'
        self.request_preview()
        self.refresh_list()

    def refresh_list(self):
        clip = self.current_clip()
        self.clips.item(self.index).setText(f'{self.index+1:02}  {clip["title"]}\n{clip["end"]-clip["start"]:.1f} sec')

    def trim_changed(self):
        if self.loading or self.index<0:
            return
        clip = self.current_clip()
        clip['start'],clip['end'] = self.begin.value(),self.end.value()
        clip['crop_keyframes'] = [p for p in clip.get('crop_keyframes',[]) if clip['start'] <= p['time'] <= clip['end']]
        self.refresh_list()
        self.populate_captions()
        self.reset_camera()

    def caption_changed(self,row,column):
        if self.loading or column!=1:
            return
        index = self.caption_rows[row]
        self.state['transcript'][index] = correct_segment(self.state['transcript'][index],self.captions.item(row,1).text())
        self.status.setText('Caption corrected. If word count changed, word timing is estimated within the original segment.')

    def seek_slider(self,value):
        if not self.loading:
            self.seek(value/1000)

    def seek(self,t):
        self.position = min(max(0,t),max(0,self.state['media']['duration']-1/self.fps))
        self.request_token += 1  # Ignore any frame from the previous timeline position.
        self.reset_camera()
        self.clock.setText(f'{self.position:.2f} sec')
        self.seek_timer.start()

    def request_preview(self, seek=True):
        if self.closing_result is not None:
            return
        self.request_token += 1
        self.preview_busy = True
        self.worker.request(self.request_token,self.position,self.current_clip(),self.state['settings'],seek)

    def next_frame(self):
        # Backpressure: a slow decoder never queues additional playback frames.
        if self.preview_busy or self.seek_timer.isActive():
            return
        step = 1/min(15,self.fps)
        if self.position+step >= self.current_clip()['end']:
            self.pause()
            return
        self.position += step
        self.request_preview(False)

    def draw_frame(self):
        self.request_preview()

    def preview_ready(self,result):
        if result['token']!=self.request_token or self.closing_result is not None:
            return
        self.preview_busy = False
        self.fps = result['fps']
        self.frame = result['source']
        self.source_view.set_frame(result['source'],result['camera'])
        self.output_view.set_frame(result['output'])
        self.loading = True
        self.scrub.setValue(round(self.position*1000))
        self.loading = False
        self.clock.setText(f'{self.position:.2f} sec')

    def preview_failed(self,token,message):
        if token not in (-1,self.request_token):
            return
        self.preview_busy = False
        self.pause()
        self.status.setText(message)

    def close_preview(self,result):
        self.pause()
        self.seek_timer.stop()
        self.closing_result = result
        self.setEnabled(False)
        self.status.setText('Closing preview...')
        self.worker.stop()
        if not self.worker.isRunning():
            self.preview_finished()

    def preview_finished(self):
        if self.closing_result is not None:
            super().done(self.closing_result)

    def add_point(self,x,y):
        clip = self.current_clip()
        if not clip['start'] <= self.position <= clip['end']:
            self.status.setText('Move inside this clip before adding a crop point.')
            return
        self.pause()
        points = [p for p in clip.get('crop_keyframes',[]) if abs(p['time']-self.position)>1/self.fps/2]
        points.append(dict(time=round(self.position,4),x=x,y=y,zoom=self.zoom.value()))
        clip['crop_keyframes'] = sorted(points,key=lambda p:p['time'])
        self.reset_camera()
        if self.frame is not None:
            self.draw_frame()

    def clear_points(self):
        self.current_clip()['crop_keyframes'] = []
        self.reset_camera()
        if self.frame is not None:
            self.draw_frame()

    def go_to_point(self,index):
        value = self.points.itemData(index)
        if value is not None:
            self.pause()
            self.seek(value)

    def remove_point(self):
        value = self.points.currentData()
        if value is not None:
            self.current_clip()['crop_keyframes'] = [p for p in self.current_clip()['crop_keyframes'] if p['time']!=value]
            self.reset_camera()
            if self.frame is not None:
                self.draw_frame()

    def save_draft(self):
        try:
            self.state['checked'] = [self.clips.item(i).checkState()==Qt.CheckState.Checked for i in range(self.clips.count())]
            validate_draft(self.state)
            atomic_json(self.draft_path,self.state)
            self.status.setText(f'Draft saved: {self.draft_path}')
            return True
        except (ValueError,OSError,KeyError,TypeError) as exc:
            self.status.setText(f'Cannot save draft: {exc}')
            return False

    def accept_edits(self):
        selected = [c for i,c in enumerate(self.state['clips']) if self.clips.item(i).checkState()==Qt.CheckState.Checked]
        result = {**self.state,'clips':selected,'checked':[True]*len(selected)}
        try:
            validate_draft(result)
            atomic_json(self.draft_path,result)
        except (ValueError,OSError,KeyError,TypeError) as exc:
            QMessageBox.warning(self,'Check edits',str(exc))
            return
        self.result_state = result
        self.close_preview(QDialog.DialogCode.Accepted)

    def reject(self):
        if not self.save_draft():
            # Invalid edits may be fixed instead of silently discarding them.
            answer = QMessageBox.question(self,'Draft not saved','Edits contain invalid times. Close without saving these edits?')
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.close_preview(QDialog.DialogCode.Rejected)
