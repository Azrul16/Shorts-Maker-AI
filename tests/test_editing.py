import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from keyframes import KeyframeCamera, validate_keyframes
from projects import make_draft, atomic_json, load_draft, validate_draft
from pipeline import Settings, run
from selector import Clip
from captions import correct_segment, write_srt, write_captions
from quality import export_report


class EditingTests(unittest.TestCase):
    def test_crop_is_seek_independent_and_fills_edges(self):
        camera = KeyframeCamera([dict(time=5,x=0,y=0,zoom=1),dict(time=9,x=1,y=1,zoom=2)],5,9)
        np.testing.assert_allclose(camera.position(7),[.5,.5,1.5])
        frame = np.full((360,640,3),150,np.uint8)
        first = camera.crop(frame,2,(180,320))
        camera.crop(frame,4,(180,320))
        np.testing.assert_array_equal(first,camera.crop(frame,2,(180,320)))
        self.assertTrue(np.all(first==150))

    def test_invalid_crop_points_rejected(self):
        point = dict(time=1,x=.5,y=.5,zoom=1)
        for points in ([point,point],[dict(point,x=float('nan'))],[dict(point,zoom=3)],[dict(point,time=20)]):
            with self.assertRaises(ValueError):
                validate_keyframes(points,0,10)

    def test_drafts_keep_edits_not_credentials_and_detect_source_change(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/'source.mp4'
            source.write_bytes(b'source')
            draft = make_draft(source,'Match',{'duration':10},[Clip(0,5,'Goal',1,'')],[],Settings(str(source),groq_key='private-test-value'))
            draft['checked'] = [False]
            path = Path(directory)/'edit.shortmaker.json'
            atomic_json(path,draft)
            self.assertNotIn('private-test-value',path.read_text())
            self.assertEqual(load_draft(path)['checked'],[False])
            source.write_bytes(b'changed source')
            with self.assertRaisesRegex(ValueError,'changed'):
                load_draft(path)

    def test_atomic_failed_write_preserves_previous_draft(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'draft.json'
            atomic_json(path,{'valid':True})
            with self.assertRaises(ValueError):
                atomic_json(path,{'value':float('nan')})
            self.assertIn('true',path.read_text())
            self.assertEqual(list(Path(directory).glob('*.tmp')),[])

    def test_caption_correction_and_clipped_srt(self):
        segment = dict(start=2,end=4,text='a goal',words=[dict(start=2,end=3,word='a'),dict(start=3,end=4,word='goal')])
        corrected = correct_segment(segment,'great save')
        self.assertEqual(corrected['words'][1],dict(start=3,end=4,word='save'))
        self.assertEqual(segment['words'][1]['word'],'goal')
        self.assertEqual(correct_segment(segment,'a very good save')['words'],[])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'clip.srt'
            write_srt(path,[corrected],3,3.5)
            self.assertIn('00:00:00,000 --> 00:00:00,500',path.read_text())
            self.assertIn('save',path.read_text())
            self.assertNotIn('great',path.read_text())
            write_captions(path,[corrected],2,4,'bold')
            self.assertIn('Arial,76',path.read_text())

    def test_quality_fails_missing_audio_and_wrong_dimensions(self):
        with tempfile.TemporaryDirectory() as directory:
            report = export_report(Path(directory)/'clip.mp4',dict(width=1920,height=1080,duration=5,has_audio=False),dict(face_samples=100,face_detections=40),5,1920)
            self.assertFalse(report['technical_pass'])
            self.assertEqual(report['face_observation_coverage'],.4)
            self.assertIn('do not measure editorial quality',report['note'])

    def test_resume_preserves_review_choices_without_reanalysis(self):
        from runtime import Cancelled
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/'source.mp4'
            source.write_bytes(b'fixture')
            settings = Settings(str(source),review=True,music='off',selection='challenge')
            media = dict(duration=10,width=640,height=360,has_audio=True)
            draft = make_draft(source,'Match',media,[Clip(0,5,'Goal',1,'')],[],settings)
            draft['checked'] = [False]
            seen = []
            def review(state):
                seen.append(state['checked'])
                return None
            with patch('pipeline.hardware',return_value={'nvenc':False}), patch('pipeline.probe',return_value=media), patch('pipeline.transcribe',side_effect=AssertionError('unexpected transcription')), patch('pipeline.select_activity',side_effect=AssertionError('unexpected selection')):
                with self.assertRaises(Cancelled):
                    run(settings,lambda *args:None,prepared=draft,review=review)
            self.assertEqual(seen,[[False]])
            self.assertTrue(source.exists())
