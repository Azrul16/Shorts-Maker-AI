"""Face-aware vertical framing with a full-scene fallback for ambiguous shots."""
import math
import cv2
import numpy as np
from runtime import ASSETS


def fit_scene(frame, output_size):
    """Keep every source pixel visible over a subdued blurred background."""
    width, height = output_size
    h, w = frame.shape[:2]
    background = cv2.resize(frame, (72, 128))
    background = cv2.GaussianBlur(background, (0, 0), 7)
    background = cv2.resize(background, output_size)
    background = (background.astype(np.float32) * .48).astype(np.uint8)
    scale = min(width / w, height / h)
    fw, fh = min(width, round(w * scale)), min(height, round(h * scale))
    foreground = cv2.resize(frame, (fw, fh), interpolation=cv2.INTER_LANCZOS4)
    x, y = (width-fw)//2, round((height-fh)*.42)
    background[y:y+fh, x:x+fw] = foreground
    return background


class FaceCamera:
    def __init__(self, follow=True, zoom=True, mode="smart"):
        if mode not in ("smart", "fill", "fit"):
            raise ValueError("Unknown framing mode.")
        self.follow, self.zoom, self.mode = follow, zoom, mode
        self.detector = None
        if follow and mode != "fit":
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
        self.boxes = []
        self.preserved_frames = 0
        self.preserve_until = 0

    def crop(self, frame, t, output_size):
        if self.mode == "fit":
            self.preserved_frames += 1
            return fit_scene(frame, output_size)
        h, w = frame.shape[:2]
        base_h = min(h, w * 16 / 9)
        thumb = cv2.resize(frame, (32, 18))
        cut = self.previous is not None and np.mean(cv2.absdiff(thumb, self.previous)) > 32
        self.previous = thumb
        if self.camera is None:
            self.camera = np.array([w / 2, h / 2, base_h], dtype=float)
            self.target = self.camera.copy()
        if cut:
            self.face = None
            self.boxes = []
            self.last_face = -10
            self.preserve_until = 0
        if self.follow and (t - self.last_detection >= .1 or cut):
            ratio = min(1, 640 / w)
            small = cv2.resize(frame, (round(w * ratio), round(h * ratio)))
            self.detector.setInputSize((small.shape[1], small.shape[0]))
            _, faces = self.detector.detect(small)
            self.last_detection = t
            self.samples += 1
            if faces is not None and len(faces):
                boxes = faces[:, :4] / ratio
                areas = [box[2]*box[3] for box in boxes]
                self.boxes = [b for b, area in zip(boxes, areas) if area >= max(areas)*.3]
                def score(box):
                    x, y, fw, fh = box
                    reference = self.face[0] + self.face[2]/2 if self.face is not None else w/2
                    distance = abs(x + fw/2 - reference) / w
                    return math.sqrt(max(1, fw*fh)) * (1 - min(.8, distance*1.5))
                self.face = max(self.boxes, key=score)
                self.last_face = t
                self.detections += 1
            elif t - self.last_face > .25:
                self.face = None
                self.boxes = []

        subject = self.face
        if len(self.boxes) > 1:
            left = min(b[0] for b in self.boxes)
            top = min(b[1] for b in self.boxes)
            right = max(b[0]+b[2] for b in self.boxes)
            bottom = max(b[1]+b[3] for b in self.boxes)
            subject = np.array([left, top, right-left, bottom-top])
        preserve = self.mode == "smart" and (
            subject is None or subject[2]*1.4 > base_h*9/16 or subject[3]*1.6 > base_h
        )
        if preserve:
            self.preserve_until = t + .6
        if self.mode == "smart" and (preserve or t < self.preserve_until):
            self.preserved_frames += 1
            # Still update the camera target below on subsequent face detections;
            # never crop an uncertain wide shot merely to fill the screen.
            if subject is not None:
                self.camera = np.array([subject[0]+subject[2]/2, h/2, base_h])
            return fit_scene(frame, output_size)

        if subject is not None and self.follow:
            x, y, fw, fh = subject
            # Do not zoom until there is enough room for the full head/group.
            min_h = max(base_h / 1.18, fw*1.5*16/9, fh*2.5)
            desired_h = min(base_h, max(min_h, fh*5.5)) if self.zoom else base_h
            self.target = np.array([x+fw/2, y+fh/2+desired_h*.16, desired_h])
        else:
            self.target = np.array([w/2, h/2, base_h])
        if cut:
            self.camera = self.target.copy()
        else:
            self.camera += (self.target-self.camera)*.2
        ch = max(2, min(h, int(self.camera[2])))
        cw = max(2, min(w, int(ch*9/16)))
        left = int(self.camera[0]-cw/2)
        top = int(self.camera[1]-ch/2)
        if subject is not None:
            x, y, fw, fh = subject
            # Override lagging smoothing when it would cut off a detected head.
            margin = fw*.18
            if fw+2*margin <= cw:
                left = int(np.clip(left, x+fw+margin-cw, x-margin))
            if fh*1.4 <= ch:
                top = int(np.clip(top, y+fh*1.2-ch, y-fh*.2))
        left, top = max(0, min(w-cw, left)), max(0, min(h-ch, top))
        return cv2.resize(frame[top:top+ch, left:left+cw], output_size, interpolation=cv2.INTER_LANCZOS4)
