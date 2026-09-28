"""Single-owner video decoder with one pending request, never a frame backlog."""
import copy
import math
import threading
import cv2
from PySide6.QtCore import QThread, Signal
from framing import FaceCamera
from keyframes import KeyframeCamera
from effects import punch_zoom
from story import story_plan
from types import SimpleNamespace


class PreviewWorker(QThread):
    ready = Signal(object)
    failed = Signal(int,str)

    def __init__(self, source, parent=None, transcript=None):
        super().__init__(parent)
        self.source = source
        self.transcript = transcript or []
        self.condition = threading.Condition()
        self.pending = None
        self.stopping = False

    def request(self, token, position, clip, settings, seek=True):
        with self.condition:
            self.pending = (token,position,copy.deepcopy(clip),dict(settings),seek)
            self.condition.notify()

    def stop(self):
        with self.condition:
            self.stopping = True
            self.pending = None
            self.condition.notify()

    def run(self):
        cap = None
        camera = None
        previous_config = None
        pulses = []
        frame_index = -1
        frame = None
        try:
            # Open, seek, decode and track exclusively on this worker thread.
            cap = cv2.VideoCapture(self.source,cv2.CAP_FFMPEG,[cv2.CAP_PROP_N_THREADS,2])
            if not cap.isOpened():
                raise ValueError('Cannot open video for preview.')
            fps = cap.get(cv2.CAP_PROP_FPS)
            if not math.isfinite(fps) or fps<=0:
                raise ValueError('Invalid preview frame rate.')
            while True:
                with self.condition:
                    self.condition.wait_for(lambda:self.stopping or self.pending is not None)
                    if self.stopping:
                        return
                    token,position,clip,settings,seek = self.pending
                    self.pending = None
                try:
                    desired = max(0,round(position*fps))
                    config = (clip['start'],clip['end'],clip.get('crop_keyframes',[]),settings)
                    reset = seek or config!=previous_config or desired<frame_index
                    if reset or desired-frame_index>max(1,round(fps)):
                        cap.set(cv2.CAP_PROP_POS_FRAMES,desired)
                        frame_index = desired-1
                    while frame_index<desired:
                        with self.condition:
                            if self.stopping:
                                return
                        ok,decoded = cap.read()
                        if not ok:
                            raise ValueError('Preview could not decode this frame. Try an earlier time.')
                        frame = decoded
                        frame_index += 1
                    if reset or camera is None:
                        pulses = story_plan(self.transcript,SimpleNamespace(start=clip["start"],end=clip["end"]))["punch_times"]
                        if clip.get('crop_keyframes'):
                            camera = KeyframeCamera(clip['crop_keyframes'],clip['start'],clip['end'])
                        else:
                            camera = FaceCamera(settings.get('follow',True),settings.get('zoom',True),'fill')
                    previous_config = copy.deepcopy(config)
                    # Bound preview work and queued image memory independently of 4K inputs.
                    h,w = frame.shape[:2]
                    scale = min(1.,960/max(w,h))
                    small = cv2.resize(frame,(max(1,round(w*scale)),max(1,round(h*scale)))) if scale<1 else frame
                    elapsed = max(0,position-clip['start'])
                    zoom = 1. if clip.get('crop_keyframes') else punch_zoom(elapsed,clip['end']-clip['start'],clip.get('effects','off'),pulses)
                    output = camera.crop(small,elapsed,(180,320),effect_zoom=zoom)
                    with self.condition:
                        stale = self.stopping or self.pending is not None
                    if not stale:
                        geometry = camera.camera.copy()
                        geometry[2] /= zoom
                        self.ready.emit(dict(token=token,position=position,source=small,output=output,camera=geometry,fps=fps))
                except Exception as exc:
                    self.failed.emit(token,str(exc))
        except Exception as exc:
            self.failed.emit(-1,str(exc))
        finally:
            if cap is not None:
                cap.release()
