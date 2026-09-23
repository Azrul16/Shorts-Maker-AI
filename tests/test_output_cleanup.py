from contextlib import ExitStack
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pipeline
from selector import Clip
from runtime import Cancelled


class OutputTests(unittest.TestCase):
    def test_safe_titles_and_repeat_runs(self):
        self.assertEqual(pipeline.safe_name('A: video / title?'), 'A video title')
        self.assertEqual(pipeline.safe_name('CON'), '_CON')
        with tempfile.TemporaryDirectory() as root:
            first = pipeline.create_output_folder(root, 'Main video')
            second = pipeline.create_output_folder(root, 'Main video')
            self.assertEqual(first, Path(root) / 'shorts/Main video')
            self.assertEqual(second.name, 'Main video (2)')

    def run_job(self, root, *, local=False, failure=None, invalid=False, outside=False):
        downloads = root / 'downloads'
        downloads.mkdir(exist_ok=True)
        source = (root if outside else downloads) / 'original.mp4'
        source.write_bytes(b'original')

        def download(url, **kwargs):
            kwargs['metadata'].update(title='My Video: Great Story', url=url)
            return str(source)

        def render(source, clip, transcript, destination, **kwargs):
            if failure:
                raise failure
            Path(destination).write_bytes(b'export')
            return {'path': str(destination)}

        def probe(path):
            return {'duration': 2 if invalid and str(path) != str(source) else 6, 'width': 1080, 'height': 1920}

        with ExitStack() as stack:
            for name, value in [('DATA', root), ('DOWNLOAD_DIR', downloads)]:
                stack.enter_context(patch.object(pipeline, name, value))
            stack.enter_context(patch.object(pipeline, 'hardware', return_value={'cuda': False, 'nvenc': False}))
            stack.enter_context(patch.object(pipeline, 'download_video', side_effect=download))
            stack.enter_context(patch.object(pipeline, 'transcribe', return_value=[{'start': 0, 'end': 6, 'text': 'Great story.', 'words': []}]))
            stack.enter_context(patch.object(pipeline, 'select_clips', return_value=[Clip(0, 6, 'A great moment!', 1, '')]))
            stack.enter_context(patch.object(pipeline, 'render_clip', side_effect=render))
            stack.enter_context(patch.object(pipeline, 'probe', side_effect=probe))
            result = pipeline.run(pipeline.Settings(str(source) if local else 'https://example.com/video', str(root / 'shorts')), lambda *args: None)
        return source, result

    def test_download_deleted_only_after_verified_export(self):
        with tempfile.TemporaryDirectory() as directory:
            source, result = self.run_job(Path(directory))
            self.assertFalse(source.exists())
            self.assertTrue(result['source_deleted'])
            self.assertEqual(Path(result['folder']).name, 'My Video Great Story')
            self.assertEqual(Path(result['clips'][0]['path']).name, '01 - A great moment!.mp4')
            self.assertTrue((Path(result['folder']) / 'project.json').exists())

    def test_local_and_outside_files_are_kept(self):
        for kwargs in ({'local': True}, {'outside': True}):
            with self.subTest(kwargs=kwargs), tempfile.TemporaryDirectory() as directory:
                source, result = self.run_job(Path(directory), **kwargs)
                self.assertTrue(source.exists())
                self.assertFalse(result['source_deleted'])

    def test_failed_cancelled_or_invalid_exports_keep_original(self):
        for kwargs in ({'failure': RuntimeError('render failed')}, {'failure': Cancelled('stopped')}, {'invalid': True}):
            with self.subTest(kwargs=kwargs), tempfile.TemporaryDirectory() as directory:
                with self.assertRaises((RuntimeError, Cancelled)):
                    self.run_job(Path(directory), **kwargs)
                self.assertTrue((Path(directory) / 'downloads/original.mp4').exists())
