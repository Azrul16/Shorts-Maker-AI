import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import ExitStack
from selector import Clip, complete_selection
from publishing import write_upload_details


class CountTests(unittest.TestCase):
    def test_movie_pipeline_recovers_from_single_ranked_clip(self):
        import pipeline
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / 'movie.mp4'
            source.write_bytes(b'source')
            exported = {}
            def render(source, clip, transcript, destination, **kwargs):
                Path(destination).write_bytes(b'output')
                exported[str(destination)] = clip.end-clip.start
                return {'path': str(destination)}
            def probe(path):
                return {'duration': exported.get(str(path), 120), 'height': 1920, 'width': 1080}
            with ExitStack() as stack:
                for name, value in [('DATA', Path(root)), ('hardware', lambda: {'nvenc': False}),
                                    ('probe', probe), ('render_clip', render)]:
                    stack.enter_context(patch.object(pipeline, name, value))
                stack.enter_context(patch.object(pipeline, 'transcribe', return_value=[{'start': 25, 'end': 65, 'text': 'One scene.', 'words': []}]))
                stack.enter_context(patch.object(pipeline, 'select_clips', return_value=[Clip(25, 65, 'One scene.', 60, '')]))
                stack.enter_context(patch.object(pipeline, 'select_activity', return_value=[]))
                result = pipeline.run(pipeline.Settings(str(source), root, count=3, duration=40, selection='movie'), lambda *args: None)
            self.assertEqual(len(result['clips']), 3)
            self.assertEqual(result['requested_count'], 3)
            self.assertTrue(all(Path(c['youtube']['file']).exists() for c in result['clips']))

    def test_sparse_movie_fills_requested_count(self):
        clips = complete_selection([Clip(100, 140, 'Dialogue.', 70, '')], 600, 8, 40)
        self.assertEqual(len(clips), 8)
        self.assertTrue(all(a.end <= b.start for a, b in zip(clips, clips[1:])))

    def test_fragmented_greedy_selection_repartitions(self):
        clips = complete_selection([Clip(25, 65, 'Middle', 60, '')], 120, 3, 40)
        self.assertEqual(len(clips), 3)
        self.assertTrue(all(a.end <= b.start for a, b in zip(clips, clips[1:])))
        self.assertEqual(sum(c.end-c.start for c in clips), 120)

    def test_short_source_reports_achievable_count(self):
        self.assertEqual(len(complete_selection([], 25, 10, 40)), 2)
        self.assertEqual(len(complete_selection([], 6, 3, 40)), 1)

    def test_no_speech_still_produces_distinct_clips(self):
        clips = complete_selection([], 300, 5, 30)
        self.assertEqual(len(clips), 5)
        self.assertEqual(len({(c.start, c.end) for c in clips}), 5)

    def test_upload_copy_is_bounded_and_relevant(self):
        with tempfile.TemporaryDirectory() as root:
            for category, tag in [('football', '#Football'), ('movie', '#MovieScene'), ('animation', '#Animation')]:
                details = write_upload_details(Path(root)/'clip.mp4', 'A'*150, Clip(0, 30, 'Scene 1', 0, ''), [], category, 2)
                self.assertLessEqual(len(details['title']), 100)
                self.assertIn(tag, details['hashtags'])
                self.assertTrue(Path(details['file']).is_file())
                self.assertNotIn('In this clip:', details['description'])

    def test_caption_excludes_speech_outside_clip(self):
        with tempfile.TemporaryDirectory() as root:
            details = write_upload_details(Path(root)/'clip.mp4', 'Story', Clip(10, 30, 'Hello.', 50, ''),
                [{'start': 0, 'end': 5, 'text': 'Wrong scene'}, {'start': 12, 'end': 15, 'text': 'Hello there.'}], 'movie', 1)
            self.assertIn('Hello there.', details['description'])
            self.assertNotIn('Wrong scene', details['description'])
