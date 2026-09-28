import unittest
import cv2
import numpy as np
from ball_tracking import BallTracker, FootballCamera


def pitch(x=None, color=(250,250,250)):
    frame = np.full((360,640,3),(35,125,40),np.uint8)
    cv2.line(frame,(30,30),(30,340),(230,230,230),2)
    if x is not None:
        cv2.circle(frame,(x,210),4,color,-1)
    return frame


class BallTrackingTests(unittest.TestCase):
    def test_tracks_moving_white_and_yellow_balls(self):
        for color in ((250,250,250),(20,230,230)):
            tracker = BallTracker()
            errors = []
            for n in range(60):
                point = tracker.update(pitch(100+n*3,color),n/30)
                if point is not None:
                    errors.append(np.linalg.norm(point-[100+n*3,210]))
            self.assertGreater(len(errors),50)
            self.assertLess(max(errors),2)

    def test_static_markings_do_not_acquire_a_ball(self):
        tracker = BallTracker()
        for n in range(60):
            self.assertIsNone(tracker.update(pitch(300),n/30))

    def test_short_prediction_is_bounded_and_not_counted_as_observation(self):
        tracker = BallTracker()
        for n in range(30):
            tracker.update(pitch(100+n*3),n/30)
        observed_count = tracker.detections
        last = tracker.position.copy()
        predicted = tracker.update(pitch(),1.)
        self.assertIsNotNone(predicted)
        self.assertFalse(tracker.observed)
        self.assertEqual(tracker.detections,observed_count)
        self.assertGreater(tracker.predictions,0)
        self.assertLessEqual(abs(predicted[0]-last[0]),64)
        self.assertIsNone(tracker.update(pitch(),1.5))

    def test_brief_unconfirmed_blob_does_not_move_camera(self):
        camera = FootballCamera()
        for n in range(30):
            frame = pitch(500 if n==10 else None)
            camera.crop(frame,n/30,(180,320))
        self.assertAlmostEqual(camera.camera[0],320)
        self.assertEqual(camera.detections,0)

    def test_no_pitch_does_not_track_bright_objects(self):
        tracker = BallTracker()
        for n in range(30):
            frame = np.full((360,640,3),80,np.uint8)
            cv2.circle(frame,(100+n*3,210),4,(255,255,255),-1)
            self.assertIsNone(tracker.update(frame,n/30))

    def test_camera_follows_then_holds_without_wide_fallback(self):
        camera = FootballCamera()
        for n in range(120):
            image = camera.crop(pitch(200+n*2),n/30,(180,320))
        self.assertGreater(camera.camera[0],390)
        for n in range(120,130):
            camera.crop(pitch(),n/30,(180,320))
        last_target = camera.target.copy()
        for n in range(130,240):
            image = camera.crop(pitch(),n/30,(180,320))
        np.testing.assert_allclose(camera.target,last_target)
        self.assertEqual(camera.preserved_frames,0)
        self.assertLess(camera.camera[2],360)
        self.assertEqual(image.shape,(320,180,3))
        # The grass remains full brightness at every corner, without a blurred bed.
        for y,x in ((0,0),(0,-1),(-1,0),(-1,-1)):
            self.assertGreater(int(image[y,x,1]),110)

    def test_landscape_square_and_portrait_always_fill(self):
        for width,height in ((640,360),(360,640),(400,400)):
            frame = np.full((height,width,3),(35,125,40),np.uint8)
            camera = FootballCamera()
            result = camera.crop(frame,0,(180,320))
            self.assertTrue(np.all(result[:,:,1] == 125))
            self.assertLessEqual(camera.camera[2],height)
            self.assertLessEqual(camera.camera[2]*9/16,width)
