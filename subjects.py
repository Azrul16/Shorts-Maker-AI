"""Local subject continuity and composition; no cloud calls or identity recognition."""
import cv2
import numpy as np


class SubjectSelector:
    def __init__(self):
        self.primary = None
        self.challenger = None
        self.since = 0.

    def reset(self):
        self.primary = self.challenger = None

    def choose(self, boxes, width, crop_width, t):
        boxes = [np.asarray(b, dtype=float) for b in boxes]
        if not boxes:
            return None
        center = lambda b: b[:2]+b[2:]/2
        area = lambda b: b[2]*b[3]
        def prominence(b):
            # A large, cut-off bystander at the source edge should not displace
            # an unobstructed person near the center of the original shot.
            edge = .2 if b[0] <= width*.015 or b[0]+b[2] >= width*.985 else 1.
            return area(b)*edge*(1-.5*abs(center(b)[0]-width/2)/width)
        best = max(boxes, key=prominence)
        if self.primary is not None:
            old = min(boxes, key=lambda b: np.linalg.norm(center(b)-center(self.primary)))
            matched = np.linalg.norm(center(old)-center(self.primary)) < max(self.primary[2]*1.8,width*.08)
            if matched and prominence(best) < prominence(old)*1.8:
                best = old
                self.challenger = None
            elif matched:
                if self.challenger is None or np.linalg.norm(center(best)-center(self.challenger))>width*.08:
                    self.since = t
                self.challenger = best.copy()
                if t-self.since < .6:
                    best = old
        self.primary = best.copy()
        subject = best.copy()
        # Add companions only if their padded union fits the vertical crop.
        for other in sorted(boxes,key=lambda b:np.linalg.norm(center(b)-center(best))):
            if area(other)<area(best)*.3:
                continue
            lo = np.minimum(subject[:2],other[:2])
            hi = np.maximum(subject[:2]+subject[2:],other[:2]+other[2:])
            if (hi[0]-lo[0])*1.2 <= crop_width:
                subject = np.r_[lo,hi-lo]
        return subject


class PeopleDetector:
    """Bounded CPU fallback for upright people whose faces are not visible."""
    def __init__(self):
        self.detector = None
        self.last = -10.
        self.boxes = []

    def detect(self, frame, t):
        if t-self.last < .5:
            return self.boxes
        self.last = t
        h,w = frame.shape[:2]
        ratio = min(1.,512/max(w,h))
        small = cv2.resize(frame,(round(w*ratio),round(h*ratio)))
        if small.shape[0]<128 or small.shape[1]<64:
            self.boxes = []
            return self.boxes
        if self.detector is None:
            self.detector = cv2.HOGDescriptor()
            self.detector.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        boxes,weights = self.detector.detectMultiScale(small,winStride=(8,8),padding=(8,8),scale=1.1)
        self.boxes = [np.asarray(b,dtype=float)/ratio for b,score in zip(boxes,weights) if float(score)>.7]
        return self.boxes
