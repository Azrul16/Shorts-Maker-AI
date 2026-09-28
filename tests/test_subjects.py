import unittest
from unittest.mock import Mock, patch
import numpy as np
from subjects import SubjectSelector, PeopleDetector
from framing import FaceCamera


class SubjectTests(unittest.TestCase):
    def test_far_apart_people_do_not_target_empty_middle(self):
        selector = SubjectSelector()
        subject = selector.choose([[40,80,70,80],[500,80,50,60]],640,180,0)
        self.assertLess(subject[0]+subject[2]/2,150)

    def test_large_partial_bystander_does_not_displace_central_person(self):
        subject = SubjectSelector().choose([[2,50,60,100],[265,73,45,54]],640,180,0)
        self.assertGreater(subject[0],200)

    def test_real_shot_change_reacquires_without_panning_across_empty_scene(self):
        camera = FaceCamera(follow=False,mode='fill');camera.follow=True
        camera.detector=Mock();camera.people=Mock();camera.people.detect.return_value=[]
        camera.detector.detect.return_value=(None,np.array([[70,80,50,60]],np.float32))
        rng=np.random.default_rng(1)
        first=rng.integers(0,255,(18,32,3),dtype=np.uint8)
        import cv2
        camera.crop(cv2.resize(first,(640,360)),0,(90,160))
        camera.detector.detect.return_value=(None,np.array([[480,80,50,60]],np.float32))
        camera.crop(cv2.resize(255-first,(640,360)),.2,(90,160))
        self.assertGreater(camera.camera[0],450)

    def test_close_companions_fit_together(self):
        subject = SubjectSelector().choose([[220,90,50,60],[280,90,45,55]],640,180,0)
        self.assertEqual(list(subject),[220,90,105,60])

    def test_brief_larger_distractor_does_not_steal_subject(self):
        selector = SubjectSelector()
        selector.choose([[40,80,50,60]],640,180,0)
        boxes = [[40,80,50,60],[450,80,90,100]]
        self.assertLess(selector.choose(boxes,640,180,.1)[0],100)
        self.assertLess(selector.choose(boxes,640,180,.4)[0],100)
        self.assertGreater(selector.choose(boxes,640,180,.8)[0],400)
        selector.reset()
        self.assertLess(selector.choose([[40,80,50,60]],640,180,.9)[0],100)

    def test_fill_holds_last_target_when_people_disappear(self):
        camera = FaceCamera(follow=False,mode='fill')
        camera.follow = True
        camera.detector = Mock()
        camera.detector.detect.return_value = (None,np.array([[70,80,50,60]],np.float32))
        camera.people = Mock();camera.people.detect.return_value = []
        frame = np.full((360,640,3),120,np.uint8)
        camera.crop(frame,0,(90,160));target=camera.target.copy()
        camera.detector.detect.return_value = (None,None)
        for n in range(1,91):camera.crop(frame,n/30,(90,160))
        np.testing.assert_allclose(camera.target,target)

    def test_body_fallback_frames_person_without_face(self):
        camera = FaceCamera(follow=False,mode='fill');camera.follow=True
        camera.detector=Mock();camera.detector.detect.return_value=(None,None)
        camera.people=Mock();camera.people.detect.return_value=[np.array([420,40,90,280])]
        camera.crop(np.full((360,640,3),120,np.uint8),0,(90,160))
        self.assertEqual(camera.subject_kind,'person')
        self.assertGreater(camera.camera[0],400)
        self.assertEqual(camera.camera[2],360)

    def test_people_detector_is_bounded_and_cached(self):
        detector=PeopleDetector();detector.detector=Mock()
        detector.detector.detectMultiScale.return_value=([[100,20,64,128]],[1.])
        image=np.zeros((720,1280,3),np.uint8)
        boxes=detector.detect(image,0);detector.detect(image,.2)
        self.assertEqual(detector.detector.detectMultiScale.call_count,1)
        self.assertEqual(detector.detector.detectMultiScale.call_args.args[0].shape[1],512)
        self.assertAlmostEqual(boxes[0][0],250)
