import unittest
import numpy as np
from framing import FaceCamera

class Detector:
    def __init__(self): self.boxes=[[260,110,50,50]]
    def setInputSize(self,size): pass
    def detect(self,frame):
        return None, np.array(self.boxes,dtype=np.float32) if self.boxes else None

class SmoothCameraTests(unittest.TestCase):
    def camera(self):
        camera=FaceCamera(follow=False)
        camera.follow=True
        camera.detector=Detector()
        return camera

    def test_short_detection_dropouts_do_not_change_layout_or_scale(self):
        camera=self.camera(); frame=np.full((360,640,3),150,np.uint8)
        sizes=[]
        for n in range(180):
            camera.detector.boxes=[] if 10 <= n%30 < 23 else [[260,110,50,50]]
            camera.crop(frame,n/30,(90,160));sizes.append(camera.camera[2])
            self.assertEqual(camera.layout,'crop')
        self.assertLess(max(sizes)-min(sizes),.01)

    def test_fit_crop_transitions_are_continuous_and_never_black(self):
        camera=self.camera();frame=np.full((360,640,3),180,np.uint8)
        states=[];brightness=[]
        for n in range(480):
            camera.detector.boxes=[] if 60 <= n < 260 else [[260,110,50,50]]
            output=camera.crop(frame,n/30,(90,160))
            states.append(camera.camera.copy());brightness.append(output.mean())
            self.assertGreater(output.min(),50)
        states=np.array(states)
        self.assertGreater(states[:,2].max(),1000)
        self.assertLess(states[-1,2],400)
        self.assertLessEqual(abs(np.diff(np.log(states[:,2]))).max(),.45/30+1e-6)
        self.assertLess(abs(np.diff(brightness)).max(),5)

    def test_exposure_flash_does_not_reset_camera(self):
        camera=self.camera(); positions=[]
        for n in range(90):
            camera.detector.boxes=[[80 if n<20 else 480,90,50,50]]
            frame=np.full((360,640,3),230 if n==35 else 90,np.uint8)
            camera.crop(frame,n/30,(90,160));positions.append(camera.camera.copy())
        self.assertLessEqual(abs(np.diff(np.array(positions)[:,0])).max(),360*.65/30+1e-6)

    def test_small_box_noise_does_not_pump_zoom(self):
        camera=self.camera();sizes=[]
        for n in range(120):
            camera.detector.boxes=[[260+n%3,110,40,58+n%3]]
            camera.crop(np.full((360,640,3),150,np.uint8),n/30,(90,160));sizes.append(camera.camera[2])
        self.assertLess(max(sizes)-min(sizes),1)

    def test_frame_rates_produce_similar_camera_positions(self):
        endpoints=[]
        for fps in (24,30,60):
            camera=self.camera()
            for n in range(3*fps+1):
                camera.detector.boxes=[[80 if n<fps else 450,90,50,50]]
                camera.crop(np.full((360,640,3),150,np.uint8),n/fps,(90,160))
            endpoints.append(camera.camera[0])
        self.assertLess(max(endpoints)-min(endpoints),12)
