"""Deterministic, editable crop paths shared by preview and final rendering."""
from bisect import bisect_right
import math
import cv2
import numpy as np


def validate_keyframes(points, start=0., end=float('inf')):
    result = []
    for point in points:
        item = {k: float(point[k]) for k in ('time', 'x', 'y', 'zoom')}
        if not all(math.isfinite(v) for v in item.values()):
            raise ValueError('Crop points must contain finite values.')
        if not start <= item['time'] <= end or not 0 <= item['x'] <= 1 or not 0 <= item['y'] <= 1 or not 1 <= item['zoom'] <= 2:
            raise ValueError('Crop points must be inside the clip, with zoom between 1x and 2x.')
        result.append(item)
    result.sort(key=lambda p: p['time'])
    if any(a['time'] == b['time'] for a,b in zip(result,result[1:])):
        raise ValueError('Only one crop point is allowed at each time.')
    return result


class KeyframeCamera:
    samples = detections = preserved_frames = 0

    def __init__(self, points, start=0., end=float('inf')):
        self.points = validate_keyframes(points,start,end)
        if not self.points:
            raise ValueError('Add at least one crop point.')
        self.times = tuple(p['time'] for p in self.points)
        self.start = start
        self.camera = None

    def position(self, t):
        after = bisect_right(self.times, t)
        a = self.points[max(0,after-1)]
        b = self.points[min(len(self.times)-1,after)]
        fraction = 0 if a['time']==b['time'] else np.clip((t-a['time'])/(b['time']-a['time']),0,1)
        # Ease at every user-defined point, avoiding linear velocity jumps.
        weight = fraction*fraction*(3-2*fraction)
        return np.array([a[k]+(b[k]-a[k])*weight for k in ('x','y','zoom')])

    def crop(self, frame, t, output_size, effect_zoom=1.):
        h,w = frame.shape[:2]
        x,y,zoom = self.position(t+self.start)
        ch = min(h,w*16/9)/zoom
        cw = ch*9/16
        cx,cy = np.clip([x*w,y*h],[cw/2,ch/2],[w-cw/2,h-ch/2])
        self.camera = np.array([cx,cy,ch])
        width,height = output_size
        scale = height/ch*effect_zoom
        transform = np.array([[scale,0,width/2-cx*scale],[0,scale,height/2-cy*scale]])
        return cv2.warpAffine(frame,transform,output_size,flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_REPLICATE)
