import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import ExitStack
from selector import Clip
from publishing import write_upload_details


class CountTests(unittest.TestCase):
    def test_pipeline_does_not_pad_count_with_weak_clips(self):
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
                result = pipeline.run(pipeline.Settings(str(source), root, count=3, duration=40, selection='challenge', edit_mode='moments'), lambda *args: None)
            self.assertEqual(len(result['clips']), 1)
            self.assertIn('not enough', result['count_warning'])
            self.assertEqual(result['requested_count'], 3)
            self.assertTrue(all(Path(c['youtube']['file']).exists() for c in result['clips']))

    def test_upload_copy_is_bounded_and_relevant(self):
        with tempfile.TemporaryDirectory() as root:
            for category, tag in [('challenge', '#Challenge')]:
                details = write_upload_details(Path(root)/'clip.mp4', 'A'*150, Clip(0, 30, 'Scene 1', 0, ''), [], category, 2)
                self.assertLessEqual(len(details['title']), 100)
                self.assertIn(tag, details['hashtags'])
                self.assertTrue(Path(details['file']).is_file())
                self.assertNotIn('In this clip:', details['description'])

    def test_caption_excludes_speech_outside_clip(self):
        with tempfile.TemporaryDirectory() as root:
            details = write_upload_details(Path(root)/'clip.mp4', 'Story', Clip(10, 30, 'Hello.', 50, ''),
                [{'start': 0, 'end': 5, 'text': 'Wrong scene'}, {'start': 12, 'end': 15, 'text': 'Hello there.'}], 'challenge', 1)
            self.assertIn('Hello there.', details['description'])
            self.assertNotIn('Wrong scene', details['description'])
