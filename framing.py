"""YuNet face detection, scene-aware camera smoothing, and bounded auto zoom."""
import math
import cv2
import numpy as np
from runtime import ASSETS


class FaceCamera:
    def __init__(self, follow=True, zoom=True):
        self.follow, self.zoom = follow, zoom
        self.detector = None
        if follow:
            model = ASSETS / "assets/face_detection_yunet_2023mar.onnx"
            if not model.is_file():
                raise RuntimeError("Face tracking model is missing from the app.")
            self.detector = cv2.FaceDetectorYN.create(str(model), "", (640, 360), .75, .3, 5000)
        self.camera = None
        self.target = None
        self.previous = None
        self.last_detection = -10
        self.last_face = -10
        self.detections = 0
        self.samples = 0
        self.face = None

    def crop(self, frame, t, output_size):
        h, w = frame.shape[:2]
        base_h = min(h, w * 16 / 9)
        thumb = cv2.resize(frame, (32, 18))
        cut = self.previous is not None and np.mean(cv2.absdiff(thumb, self.previous)) > 42
        self.previous = thumb
        if self.camera is None:
            self.camera = np.array([w / 2, h / 2, base_h], dtype=float)
            self.target = self.camera.copy()
        if cut:
            self.face = None
            self.last_face = -10
        detect = self.follow and (t - self.last_detection >= .18 or cut)
        if detect:
            ratio = min(1, 640 / w)
            small = cv2.resize(frame, (round(w * ratio), round(h * ratio)))
            self.detector.setInputSize((small.shape[1], small.shape[0]))
            _, faces = self.detector.detect(small)
            self.last_detection = t
            self.samples += 1
            if faces is not None and len(faces):
                boxes = faces[:, :4] / ratio
                def score(box):
                    x, y, fw, fh = box
                    distance = abs(x + fw / 2 - self.camera[0]) / w
                    return math.sqrt(max(1, fw * fh)) * (1 - min(.65, distance))
                self.face = max(boxes, key=score)
                self.last_face = t
                self.detections += 1
            elif t - self.last_face > .8:
                self.face = None
        if self.face is not None and self.follow:
            x, y, fw, fh = self.face
            # Subtle zoom only; do not enlarge already close-up faces.
            desired_h = max(base_h / 1.18, min(base_h, fh * 5.5)) if self.zoom else base_h
            self.target = np.array([x + fw / 2, y + fh / 2 + desired_h * .18, desired_h])
        else:
            self.target = np.array([w / 2, h / 2, base_h])
        if cut:
            self.camera = self.target.copy()
        else:
            self.camera += (self.target - self.camera) * .12
        ch = max(2, min(h, int(self.camera[2])))
        cw = max(2, min(w, int(ch * 9 / 16)))
        left = max(0, min(w - cw, int(self.camera[0] - cw / 2)))
        top = max(0, min(h - ch, int(self.camera[1] - ch / 2)))
        return cv2.resize(frame[top:top+ch, left:left+cw], output_size, interpolation=cv2.INTER_LANCZOS4)
