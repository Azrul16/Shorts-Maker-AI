import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

import cv2
import numpy as np

from captions import write_captions
from formats import PROFILES, output_size
from pipeline import Settings
from projects import make_draft, validate_draft
from publishing import write_upload_details, groq_copy
from renderer import SourceCamera
from selector import Clip
from summary import select_summaries


class FormatTests(unittest.TestCase):
    def test_preserved_dimensions_and_vertical_reels(self):
        for width, height in ((1920,1080), (1080,1920), (1080,1080), (1440,1080)):
            media = dict(width=width,height=height)
            result = output_size(media,1920,'summary')
            self.assertAlmostEqual(result[0]/result[1],width/height,delta=.002)
            self.assertTrue(all(v%2 == 0 for v in result))
            self.assertEqual(output_size(media,1920,'reel'),(1080,1920))
        self.assertEqual(PROFILES['reel']['music'],.5)
        self.assertEqual(output_size(dict(width=1920,height=1080),1280,'summary'),(1280,720))

    def test_whole_source_camera_preserves_edges(self):
        frame = np.zeros((180,320,3),dtype=np.uint8)
        frame[:,:40,2] = 255
        frame[:,-40:,0] = 255
        camera = SourceCamera()
        result = camera.crop(frame,0,(1280,720))
        self.assertGreater(result[:,0,2].mean(),250)
        self.assertGreater(result[:,-1,0].mean(),250)
        self.assertEqual(camera.preserved_frames,1)

    def test_captions_fit_landscape_square_and_vertical_frames(self):
        with tempfile.TemporaryDirectory() as folder:
            for size, canvas in [((1920,1080),(1920,1080)),((1080,1080),(1080,1080)),((720,1280),(1080,1920))]:
                path=Path(folder)/'captions.ass'
                write_captions(path,[dict(start=0,end=3,text='A challenge with a clear outcome.')],0,3,output_size=size,effects='energetic',title='Challenge')
                text=path.read_text(encoding='utf-8')
                self.assertIn(f'PlayResX: {canvas[0]}',text)
                self.assertIn(f'PlayResY: {canvas[1]}',text)
                self.assertIn('outcome.',text)

    def test_long_story_selection_and_reel_cap(self):
        phrases = ['Our goal is to build a school for the community.',
                   'The community has only one chance to complete the school.',
                   'We built a classroom and now the school has a roof.',
                   'The community cannot fail because the school matters.',
                   'The school is finally complete and the community won!']
        transcript=[dict(start=i*22.,end=i*22.+18,text=phrases[min(4,i//8)],words=[]) for i in range(40)]
        reels=select_summaries(transcript,1,120,900)
        videos=select_summaries(transcript,1,360,900,minimum=240)
        self.assertTrue(reels)
        self.assertTrue(videos)
        self.assertLessEqual(reels[0].duration,120)
        self.assertTrue(240 <= videos[0].duration <= 360)
        self.assertEqual(select_summaries(transcript[:3]+transcript[-1:],1,360,900,minimum=240),[])

    def test_draft_enforces_format_limits(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'source.mp4';source.write_bytes(b'source')
            clip=Clip(0,1000,'Story',1,'',spans=[dict(start=0,end=150),dict(start=850,end=1000)])
            draft=make_draft(source,'Story',dict(duration=1000),[clip],[],Settings(str(source),output_type='summary',auto_duration=True))
            validate_draft(draft)
            draft['settings']['output_type']='reel'
            with self.assertRaises(ValueError):validate_draft(draft)
            draft['settings']['auto_duration']=False
            with self.assertRaises(ValueError):validate_draft(draft)
            draft['settings']['output_type']='summary'
            draft['clips'][0]['spans']=[dict(start=0,end=100)]
            with self.assertRaises(ValueError):validate_draft(draft)

    def test_post_copy_matches_selected_format(self):
        with tempfile.TemporaryDirectory() as folder:
            for mode, tag in [('reel','#Reels'),('summary','#FacebookVideo')]:
                result=write_upload_details(Path(folder)/'video.mp4','A community school',Clip(0,10,'The school opens',1,''),[dict(start=0,end=9,text='We built a school for the community.',words=[])],'challenge',1,output_type=mode)
                self.assertEqual(len(result['hashtags']),7)
                self.assertIn(tag,result['hashtags'])
                self.assertNotIn('#Shorts',result['hashtags'])
                self.assertTrue(result['file'].endswith('.post.txt'))
                self.assertIn('school',result['description'])

    def test_summary_copy_prompt_uses_facebook_context(self):
        response=Mock(status_code=200)
        response.json.return_value={'choices':[{'message':{'content':json.dumps(dict(title='A school changes the community',description='A community builds a school together. '*12,hashtags=['#Challenge']))}}]}
        with patch('requests.post',return_value=response) as post:
            _,_,tags=groq_copy('School','We built the school.','challenge','English','test-key','summary')
        self.assertIn('Facebook video',post.call_args.kwargs['json']['messages'][0]['content'])
        self.assertIn('#FacebookVideo',tags)

    def test_desktop_has_two_profiles_and_correct_defaults(self):
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        from PySide6.QtWidgets import QApplication
        from desktop import Window
        app=QApplication.instance() or QApplication([])
        with patch('desktop.HardwareJob'):
            window=Window()
            self.assertEqual(window.edit_mode.count(),2)
            self.assertEqual(window.music_level.value(),50)
            window.edit_mode.setCurrentIndex(1)
            self.assertEqual(window.music_level.value(),18)
            self.assertIn('4 to 6',window.duration.text())
            self.assertFalse(window.manual.isEnabled())
            window.edit_mode.setCurrentIndex(0)
            self.assertEqual(window.music_level.value(),50)
            window.deleteLater()
            app.processEvents()
