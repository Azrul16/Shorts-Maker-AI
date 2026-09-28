import json
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

from pipeline import Settings, run
from projects import make_draft, validate_draft
from renderer import render_clip, prepare_audio
from runtime import Cancelled, NO_WINDOW, probe, tool
from selector import Clip
from summary import select_summaries, timeline, validate_spans


class SummaryTests(unittest.TestCase):
    def test_whole_source_selection_retains_order_budget_and_outcome(self):
        phrases = ['The challenge is to survive for a prize of $1000.',
                   'The contestants build a shelter before the storm.',
                   'There is only one chance left and we might fail.',
                   'The storm arrives and everyone protects the shelter.',
                   'Finally the winner completed the challenge!']
        transcript = [dict(start=i*60., end=i*60.+8, text=t, words=[]) for i, t in enumerate(phrases)]
        clips = select_summaries(transcript, 5, 40, 300)
        self.assertEqual(len(clips), 1)  # Never fabricate five stories.
        clip = clips[0]
        self.assertGreaterEqual(len(clip.spans), 3)
        self.assertEqual(clip.spans[0]['start'], 0)
        self.assertEqual(clip.spans[-1]['start'], 240)
        self.assertLessEqual(clip.duration, 40)
        self.assertTrue(all(a['end'] <= b['start'] for a, b in zip(clip.spans, clip.spans[1:])))

    def test_missing_story_evidence_is_not_filled_with_random_windows(self):
        self.assertEqual(select_summaries([dict(start=0, end=5, text='Hello there.', words=[])], 3, 60, 600), [])

    def test_sponsor_dialogue_is_excluded_from_story(self):
        transcript = [dict(start=0, end=8, text='Our goal is to build a school for the community.', words=[]),
                      dict(start=80, end=88, text='The community has one chance left to complete the school.', words=[]),
                      dict(start=150, end=158, text='The co -founders are helping. Go online and buy yours.', words=[]),
                      dict(start=240, end=250, text='We built the school and the community finally won!', words=[])]
        clips = select_summaries(transcript, 1, 40, 300)
        self.assertTrue(clips)
        self.assertFalse(any(s['start'] <= 150 < s['end'] for s in clips[0].spans))

    def test_caption_mapping_excludes_omitted_text_and_preserves_words(self):
        clip = Clip(10, 103, 'Story', 1, '', spans=[dict(start=10, end=12), dict(start=100, end=103)])
        transcript = [dict(start=10, end=12, text='First.', words=[dict(start=10.2, end=11.8, word='First.')]),
                      dict(start=50, end=60, text='OMITTED', words=[]),
                      dict(start=100, end=103, text='Last.', words=[dict(start=100.1, end=102.5, word='Last.')])]
        local, mapped = timeline(clip, transcript)
        self.assertEqual(local.duration, 5)
        self.assertEqual([s['text'] for s in mapped], ['First.', 'Last.'])
        self.assertAlmostEqual(mapped[-1]['words'][0]['start'], 2.1)
        self.assertEqual(transcript[-1]['words'][0]['start'], 100.1)

    def test_story_events_keep_original_source_times_after_mapping(self):
        from story import story_plan
        clip = Clip(10, 105, 'Story', 1, '', spans=[dict(start=10, end=14), dict(start=100, end=105)])
        local, transcript = timeline(clip, [dict(start=10, end=12, text='The challenge.', words=[]),
                                           dict(start=101, end=104, text='The winner!', words=[])])
        events = story_plan(transcript, local)['events']
        self.assertEqual([e['source_time'] for e in events], [10, 101])
        self.assertEqual([e['time'] for e in events], [0, 5])

    def test_invalid_or_reversed_spans_are_rejected(self):
        for spans in ([dict(start=4, end=6), dict(start=2, end=3)],
                      [dict(start=0, end=3), dict(start=2, end=4)],
                      [dict(start=0, end=float('nan'))]):
            with self.assertRaises(ValueError):
                validate_spans(Clip(0, 6, '', 0, '', spans=spans), 6)


class SummaryRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.root = Path(cls.folder.name)
        silent = cls.root/'colors.mp4'
        writer = cv2.VideoWriter(str(silent), cv2.VideoWriter_fourcc(*'mp4v'), 30, (320, 180))
        for color in ((0, 0, 255), (0, 255, 0), (255, 0, 0)):
            frame = np.full((180, 320, 3), color, dtype=np.uint8)
            for _ in range(60):
                writer.write(frame)
        writer.release()
        cls.source = cls.root/'source.mp4'
        subprocess.run([tool('ffmpeg'), '-v', 'error', '-y', '-i', str(silent), '-f', 'lavfi', '-i',
                        r'aevalsrc=sin(2*PI*if(lt(t\,2)\,440\,if(lt(t\,4)\,660\,880))*t):s=48000:d=6',
                        '-c:v', 'copy', '-c:a', 'aac', str(cls.source)], check=True, creationflags=NO_WINDOW)
        cls.clip = Clip(.3, 5.2, 'Challenge result', 1, '', spans=[dict(start=.3, end=1.3), dict(start=4.2, end=5.2)])
        cls.transcript = [dict(start=.4, end=1.2, text='First challenge.', words=[]),
                          dict(start=2.2, end=3.8, text='OMITTED_GREEN', words=[]),
                          dict(start=4.3, end=5.1, text='The winner.', words=[])]

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def test_render_joins_correct_frames_audio_and_captions(self):
        output = self.root/'summary.mp4'
        render_clip(self.source, self.clip, self.transcript, output, height=1280, follow=False, zoom=False, nvenc=False)
        media = probe(output)
        self.assertAlmostEqual(media['duration'], 2, delta=.1)
        self.assertTrue(media['has_audio'])
        cap = cv2.VideoCapture(str(output))
        for time, dominant in ((.4, 2), (1.4, 0)):
            cap.set(cv2.CAP_PROP_POS_MSEC, time*1000)
            ok, frame = cap.read()
            self.assertTrue(ok)
            self.assertEqual(int(np.argmax(frame.mean(axis=(0, 1)))), dominant)
        cap.release()
        audio = subprocess.check_output([tool('ffmpeg'), '-v', 'error', '-i', str(output), '-vn', '-ar', '8000', '-ac', '1', '-f', 'f32le', 'pipe:1'], creationflags=NO_WINDOW)
        samples = np.frombuffer(audio, dtype='<f4')
        for start, expected in ((.2, 440), (1.2, 880)):
            window = samples[int(start*8000):int((start+.5)*8000)]
            frequency = np.fft.rfftfreq(len(window), 1/8000)[np.argmax(abs(np.fft.rfft(window)))]
            self.assertAlmostEqual(frequency, expected, delta=5)
        srt = output.with_suffix('.srt').read_text(encoding='utf-8')
        self.assertIn('winner', srt)
        self.assertNotIn('OMITTED', srt)
        self.assertIn('00:00:01,100', srt)

    def test_pipeline_preserves_spans_and_copy_uses_only_retained_speech(self):
        settings = Settings(str(self.source), str(self.root/'exports'), count=1, height=1280, gpu=False, music='off', follow=False)
        draft = make_draft(self.source, 'Challenge', probe(self.source), [self.clip], self.transcript, settings)
        with patch('pipeline.hardware', return_value={'nvenc': False}), patch('pipeline.DATA', self.root):
            result = run(settings, lambda *args: None, prepared=draft)
        self.assertFalse(result['source_deleted'])
        self.assertEqual(result['clips'][0]['spans'], self.clip.spans)
        self.assertNotIn('OMITTED', result['clips'][0]['youtube']['description'])
        plan = json.loads(Path(result['clips'][0]['path']).with_suffix('.edit.json').read_text(encoding='utf-8'))
        self.assertAlmostEqual(plan['duration'], 2)
        self.assertEqual(len(plan['source_spans']), 2)

    def test_summary_draft_accepts_long_source_envelope(self):
        clip = Clip(0, 1000, 'Story', 1, '', spans=[dict(start=0, end=10), dict(start=990, end=1000)])
        draft = make_draft(self.source, 'Story', dict(duration=1000), [clip], [], Settings(str(self.source)))
        validate_draft(draft)

    def test_summary_review_saves_and_exports_timeline(self):
        import os
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from PySide6.QtWidgets import QApplication
        from review import SummaryReviewDialog
        app = QApplication.instance() or QApplication([])
        draft = make_draft(self.source, 'Story', probe(self.source), [self.clip], self.transcript, Settings(str(self.source)))
        with patch('review.DATA', self.root):
            dialog = SummaryReviewDialog(draft)
            self.assertEqual(dialog.sections.rowCount(), 2)
            dialog.accept_edits()
            self.assertEqual(dialog.result_state['clips'][0]['spans'], self.clip.spans)
            self.assertTrue(dialog.draft_path.exists())
            dialog.deleteLater()
            app.processEvents()

    def test_audio_assembly_is_cancellable(self):
        event = threading.Event()
        event.set()
        with self.assertRaises(Cancelled):
            prepare_audio(self.source, self.clip.spans, self.root/'cancel.wav', event)
