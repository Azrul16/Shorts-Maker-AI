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
        self.last_time = None
        self.velocity = np.zeros(3)
        self.layout = None
        self.pending_layout = None
        self.pending_since = 0.

    def crop(self, frame, t, output_size):
        if self.mode == "fit":
            self.preserved_frames += 1
            return fit_scene(frame, output_size)
        h, w = frame.shape[:2]
        base_h = min(h, w * 16 / 9)
        dt = 1/30 if self.last_time is None else max(0., min(.1, t-self.last_time))
        self.last_time = t
        # Compare structure after removing exposure: a flash is not a new shot.
        thumb = cv2.cvtColor(cv2.resize(frame, (32, 18)), cv2.COLOR_BGR2GRAY).astype(float)
        structure = (thumb-thumb.mean()) / max(20., thumb.std())
        cut = self.previous is not None and np.mean(np.abs(structure-self.previous)) > 1.05
        self.previous = structure
        if cut:
            self.face = None
            self.boxes = []
            self.last_face = -10
        # Never reset camera position on a cut or a detector miss. All changes
        # use the same continuous, acceleration-limited camera trajectory.
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
            elif t - self.last_face > 1.0:
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
        wanted_layout = 'fit' if preserve else 'crop'
        if self.layout is None:
            self.layout = wanted_layout
        if wanted_layout != self.pending_layout:
            self.pending_layout, self.pending_since = wanted_layout, t
        # Require sustained evidence before changing composition. A crowded
        # scene zooms out sooner than a lone detection is allowed to zoom in.
        hold = .45 if wanted_layout == 'fit' else 1.2
        if wanted_layout != self.layout and t-self.pending_since >= hold:
            self.layout = wanted_layout
        full_h = max(h, w*16/9)
        if self.layout == 'fit':
            self.preserved_frames += 1
            desired = np.array([w/2, h/2, full_h], dtype=float)
        elif subject is not None and self.follow:
            x, y, fw, fh = subject
            # Modest zoom with deadband; detector box noise must not cause pumping.
            min_h = max(base_h/1.12, fw*1.5*16/9, fh*2.5)
            desired_h = min(base_h, max(min_h, fh*5.5)) if self.zoom else base_h
            desired = np.array([x+fw/2, y+fh/2+desired_h*.16, desired_h])
            if self.target is not None and abs(desired_h-self.target[2]) < base_h*.025:
                desired[2] = self.target[2]
            if self.target is not None:
                for axis in (0, 1):
                    if abs(desired[axis]-self.target[axis]) < base_h*.025:
                        desired[axis] = self.target[axis]
        else:
            desired = np.array([w/2, h/2, base_h], dtype=float)
        # Bound the destination, not the rendered crop: per-frame safety
        # overrides previously bypassed smoothing and produced abrupt jumps.
        for axis, extent, span in ((0,w,desired[2]*9/16),(1,h,desired[2])):
            desired[axis] = extent/2 if span >= extent else np.clip(desired[axis],span/2,extent-span/2)
        self.target = desired
        if self.camera is None:
            self.camera = desired.copy()
        elif dt > 0:
            # Critically damped spring in log zoom space: no overshoot, and
            # consistent motion at 24/30/60 fps. Limit both speed and acceleration.
            current = np.array([self.camera[0], self.camera[1], math.log(self.camera[2])])
            target = np.array([desired[0], desired[1], math.log(desired[2])])
            omega = 4.0
            acceleration = omega**2*(target-current)-2*omega*self.velocity
            acceleration = np.clip(acceleration, [-base_h*2,-base_h*2,-1.2], [base_h*2,base_h*2,1.2])
            self.velocity += acceleration*dt
            self.velocity = np.clip(self.velocity, [-base_h*.65,-base_h*.65,-.45], [base_h*.65,base_h*.65,.45])
            step = self.velocity*dt
            for axis in range(3):
                if (target[axis]-current[axis])*step[axis] >= 0 and abs(step[axis]) > abs(target[axis]-current[axis]):
                    step[axis] = target[axis]-current[axis]
                    self.velocity[axis] = 0
            current += step
            self.camera = np.array([current[0],current[1],math.exp(current[2])])
        # A single subpixel transform bridges full-scene and fill framing.
        # No hard layout swaps, integer crop rounding, or crossfade ghosting.
        width, height = output_size
        scale = height/self.camera[2]
        span_x, span_y = self.camera[2]*9/16, self.camera[2]
        cx = w/2 if span_x >= w else np.clip(self.camera[0],span_x/2,w-span_x/2)
        cy = h/2 if span_y >= h else np.clip(self.camera[1],span_y/2,h-span_y/2)
        transform = np.array([[scale,0,width/2-cx*scale],
                              [0,scale,height/2-cy*scale]], dtype=np.float64)
        if self.camera[2] > h or self.camera[2]*9/16 > w:
            background = cv2.resize(frame, (72,128))
            background = cv2.GaussianBlur(background,(0,0),7)
            canvas = (cv2.resize(background,output_size).astype(np.float32)*.48).astype(np.uint8)
        else:
            canvas = np.zeros((height,width,3),dtype=np.uint8)
        return cv2.warpAffine(frame,transform,output_size,dst=canvas,
                              flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_TRANSPARENT if span_y > h or span_x > w else cv2.BORDER_REPLICATE)
