"""Local football tracking: compact pitch objects with temporal confirmation.

This is a visual heuristic, not a trained ball detector. Uncertain observations
do not move the camera; it holds the last confirmed location instead.
"""
import cv2
import numpy as np


class BallTracker:
    def __init__(self):
        self.tracks = []
        self.position = None
        self.velocity = np.zeros(2)
        self.last_seen = -10.
        self.last_time = None
        self.previous = None
        self.samples = 0
        self.detections = 0
        self.confidence = 0.
        self.predictions = 0
        self.observed = False

    def update(self, frame, t):
        self.observed = False
        h, w = frame.shape[:2]
        ratio = min(1., 960/w)
        small = cv2.resize(frame, (round(w*ratio), round(h*ratio)))
        sh, sw = small.shape[:2]
        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        pitch = cv2.inRange(hsv, (30, 45, 35), (95, 255, 255))
        self.samples += 1
        dt = 1/30 if self.last_time is None else max(.001, min(.2, t-self.last_time))
        self.last_time = t
        shift = np.zeros(2)
        thumbnail = cv2.resize(gray, (160,90)).astype(np.float32)
        if self.previous is not None:
            # Compensate broadcast camera movement before judging object motion.
            if np.std(thumbnail) > 12 and np.std(self.previous) > 12:
                delta, response = cv2.phaseCorrelate(self.previous, thumbnail)
                if response > .25 and np.linalg.norm(delta) < 12:
                    shift = np.array(delta)*[sw/160, sh/90]
            a = (thumbnail-thumbnail.mean())/max(20., thumbnail.std())
            b = (self.previous-self.previous.mean())/max(20., self.previous.std())
            if np.mean(np.abs(a-b)) > 1.15:
                self.tracks = []
                self.position = None
                self.velocity[:] = 0
                self.last_seen = -10.
        self.previous = thumbnail
        # Close-ups, crowds and graphics are not reliable pitch tracking scenes.
        if np.mean(pitch > 0) < .22:
            self.tracks = []
            self.confidence = 0.
            return None
        white = cv2.inRange(hsv, (0,0,170), (179,105,255))
        yellow = cv2.inRange(hsv, (10,105,190), (38,255,255))
        mask = cv2.bitwise_or(white, yellow)
        # Exclude broadcast graphics at the extreme top/bottom, without trying
        # to identify or erase logos from the source.
        mask[:round(sh*.09)] = 0
        mask[round(sh*.96):] = 0
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates = []
        for contour in contours:
            x,y,bw,bh = cv2.boundingRect(contour)
            area = cv2.contourArea(contour)
            if not 2 <= area <= max(45,sh*sh*.00065) or not .55 <= bw/max(1,bh) <= 1.8:
                continue
            if max(bw,bh) > max(10,sh*.04):
                continue
            perimeter = cv2.arcLength(contour,True)
            roundness = 4*np.pi*area/max(1,perimeter**2)
            if roundness < .48 or area/(bw*bh) < .4:
                continue
            radius = max(5,round(max(bw,bh)*1.5))
            cx,cy = x+bw/2,y+bh/2
            patch = pitch[max(0,int(cy)-radius):min(sh,int(cy)+radius+1),
                          max(0,int(cx)-radius):min(sw,int(cx)+radius+1)]
            grass = float(np.mean(patch>0))
            if grass < .68:
                continue
            score = .5*min(1.,roundness)+.5*grass
            candidates.append((np.array([cx,cy]),score))
        # Associate each observation once. Three consecutive observations are
        # required before acquiring a ball; static field markings are rejected.
        matched = set()
        tracks = []
        for point,score in sorted(candidates,key=lambda c:c[1],reverse=True):
            choices = [(np.linalg.norm(point-track['point']-shift),i,track)
                       for i,track in enumerate(self.tracks) if i not in matched]
            distance,index,old = min(choices,key=lambda c:c[0]) if choices else (1e9,None,None)
            if distance < max(12,sw*.04):
                matched.add(index)
                movement = point-old['point']-shift
                tracks.append(dict(point=point,score=score,hits=old['hits']+1,
                                   motion=.65*old['motion']+.35*np.linalg.norm(movement),
                                   raw_motion=.65*old['raw_motion']+.35*np.linalg.norm(point-old['point'])))
            else:
                tracks.append(dict(point=point,score=score,hits=1,motion=0.,raw_motion=0.))
        self.tracks = tracks
        confirmed = [tr for tr in tracks if tr['hits'] >= 3]
        chosen = None
        if self.position is not None and t-self.last_seen < .8:
            predicted = (self.position+self.velocity*(t-self.last_seen))*ratio
            near = [(np.linalg.norm(tr['point']-predicted),tr) for tr in confirmed]
            if near:
                distance,nearest = min(near,key=lambda item:item[0])
                if distance < max(18,sw*.06):
                    chosen = nearest
        if chosen is None and (self.position is None or t-self.last_seen > .45):
            moving = [tr for tr in confirmed if tr['motion'] > .65 and tr['raw_motion'] > .55]
            if moving:
                chosen = max(moving,key=lambda tr:tr['score']+min(.3,tr['motion']*.05))
        if chosen is None:
            self.confidence = 0.
            elapsed = t-self.last_seen
            if self.position is not None and 0 < elapsed <= .25:
                # Short occlusions get bounded prediction. These frames are
                # deliberately not counted as observed ball detections.
                self.predictions += 1
                return np.clip(self.position+np.clip(self.velocity*elapsed,-w*.10,w*.10),[0,0],[w,h])
            return None
        point = chosen['point']/ratio
        if self.position is not None and t-self.last_seen < .3:
            measured = (point-self.position)/max(.001,t-self.last_seen)
            self.velocity = .65*self.velocity+.35*np.clip(measured,-w,w)
        else:
            self.velocity[:] = 0
        self.position = point
        self.last_seen = t
        self.detections += 1
        self.observed = True
        self.confidence = chosen['score']
        return point.copy()


class FootballCamera:
    """Always fills 9:16; smooth pan to confirmed ball, hold on uncertainty."""
    def __init__(self, zoom=True):
        self.tracker = BallTracker()
        self.zoom = zoom
        self.camera = None
        self.velocity = np.zeros(2)
        self.target = None
        self.last_time = None
        self.preserved_frames = 0
        self.ball_frames = 0
        self.held_frames = 0

    @property
    def samples(self):
        return self.tracker.samples

    @property
    def detections(self):
        return self.tracker.detections

    def crop(self, frame, t, output_size):
        h,w = frame.shape[:2]
        # A steady small zoom leaves room around the ball without zoom pumping.
        ch = min(h,w*16/9)/(1.06 if self.zoom else 1.)
        cw = ch*9/16
        dt = 1/30 if self.last_time is None else max(0.,min(.1,t-self.last_time))
        self.last_time = t
        point = self.tracker.update(frame,t)
        if self.camera is None:
            self.camera = np.array([w/2,h/2,ch],dtype=float)
            self.target = self.camera[:2].copy()
        if point is not None:
            # A little lead space helps keep passes visible while the camera pans.
            lead = np.clip(self.tracker.velocity*.10,[-cw*.15,-ch*.08],[cw*.15,ch*.08])
            goal = point+lead
            if np.linalg.norm(goal-self.target) > cw*.035:
                self.target = goal
            self.ball_frames += 1
        else:
            # Never jump back to the centre or switch to full-scene framing.
            self.held_frames += 1
        self.target = np.clip(self.target,[cw/2,ch/2],[w-cw/2,h-ch/2])
        if dt > 0:
            delta = self.target-self.camera[:2]
            acceleration = 7.**2*delta-14.*self.velocity
            self.velocity += np.clip(acceleration,-w*3,w*3)*dt
            self.velocity = np.clip(self.velocity,-w*.65,w*.65)
            step = self.velocity*dt
            crossed = (step*delta >= 0)&(abs(step)>abs(delta))
            step[crossed] = delta[crossed]
            self.velocity[crossed] = 0
            self.camera[:2] += step
        self.camera[:2] = np.clip(self.camera[:2],[cw/2,ch/2],[w-cw/2,h-ch/2])
        width,height = output_size
        scale = height/ch
        matrix = np.array([[scale,0,width/2-self.camera[0]*scale],
                           [0,scale,height/2-self.camera[1]*scale]])
        return cv2.warpAffine(frame,matrix,output_size,flags=cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_REPLICATE)
