import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from captions import write_captions
from effects import punch_zoom
from music import catalog,select_music
from selector import Clip,challenge_signal


class FocusedStyleTests(unittest.TestCase):
    def test_punches_are_smooth_bounded_and_reset(self):
        times=np.arange(0,60,1/30)
        values=np.array([punch_zoom(t,60,'energetic',[3,11,19,27,35,43,51]) for t in times])
        self.assertGreater(values.max(),1)
        self.assertLessEqual(values.max(),1.09+1e-8)
        self.assertLess(np.max(np.abs(np.diff(values))),.009)
        self.assertEqual(punch_zoom(59.9,60,'energetic'),1)
        self.assertEqual(punch_zoom(3.6,60,'off'),1)

    def test_animated_text_is_optional_and_title_is_escaped(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'captions.ass'
            segments=[dict(start=0,end=2,text='The challenge begins')]
            write_captions(path,segments,0,5,'bold',effects='energetic',title=r'{\\pos(0,0)} A challenge')
            text=path.read_text()
            self.assertIn(r'\move(540,270,540,235',text)
            self.assertIn(r'\t(0,140,',text)
            self.assertNotIn(r'{\\pos(0,0)}',text)
            write_captions(path,segments,0,5,'bold',effects='off',title='No overlay')
            self.assertNotIn('No overlay',path.read_text())
            self.assertNotIn(r'\move',path.read_text())

    def test_focused_music_avoids_video_analysis_and_keeps_credit(self):
        tracks=catalog()
        self.assertGreaterEqual(len(tracks),15)
        self.assertTrue(all(t['mood']=='energetic' and int(t['bpm'])>=100 for t in tracks))
        with patch('music.first_beat',return_value=.2):
            for category in ('challenge',):
                track=select_music('unused',Clip(0,10,'',0,''),[],category)
                self.assertIn('Creative Commons',track['credit'])
                self.assertIn(track['file'],[t['file'] for t in tracks])

    def test_challenge_cues_use_supplied_dialogue(self):
        self.assertEqual(challenge_signal('The last to leave wins $1000.'),18)
        self.assertEqual(challenge_signal('We walked through the door.'),0)
