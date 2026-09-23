from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
import cv2
import numpy as np

from framing import FaceCamera
from renderer import render_clip
from runtime import Cancelled, NO_WINDOW, probe, tool
from selector import Clip


class RenderingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.root = Path(cls.folder.name)
        cls.source = cls.root / 'source.mp4'
        subprocess.run([tool('ffmpeg'), '-y', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=s=640x360:r=30:d=3', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=3', '-c:v', 'libx264', '-c:a', 'aac', str(cls.source)], check=True, creationflags=NO_WINDOW)

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def test_cpu_export_preserves_duration_audio_and_vertical_size(self):
        output = self.root / 'cpu.mp4'
        result = render_clip(self.source, Clip(.5, 2.5, 'Test', 0, ''), [{'start': .5, 'end': 2, 'text': 'Test captions.'}], output, height=1280, follow=False, nvenc=False)
        info = probe(output)
        self.assertEqual((info['width'], info['height']), (720, 1280))
        self.assertAlmostEqual(info['duration'], 2, delta=.1)
        self.assertEqual(result['encoder'], 'libx264')
        self.assertIn('Test', output.with_suffix('.ass').read_text(encoding='utf-8'))

    def test_cancellation_removes_partial_export(self):
        event = threading.Event()
        output = self.root / 'cancelled.mp4'
        with self.assertRaises(Cancelled):
            render_clip(self.source, Clip(0, 2, 'Test', 0, ''), [], output, height=1280, follow=False, nvenc=False, cancel=event, progress=lambda p, m: event.set())
        self.assertFalse(output.exists())
        self.assertFalse(output.with_name('cancelled.partial.mp4').exists())

    def test_camera_bounds_for_landscape_portrait_and_square(self):
        for width, height in ((640, 360), (360, 640), (400, 400)):
            camera = FaceCamera(follow=False)
            result = camera.crop(np.zeros((height, width, 3), dtype=np.uint8), 0, (360, 640))
            self.assertEqual(result.shape, (640, 360, 3))

    def test_camera_follows_face_and_limits_zoom(self):
        class Detector:
            x = 80
            def setInputSize(self, size):
                pass
            def detect(self, frame):
                return None, np.array([[self.x, 90, 50, 60]], dtype=np.float32)
        camera = FaceCamera(follow=False)
        camera.follow = True
        camera.detector = Detector()
        frame = np.zeros((360, 640, 3), dtype=np.uint8)
        for i in range(30):
            camera.crop(frame, i / 30, (360, 640))
        left = camera.camera[0]
        camera.detector.x = 500
        for i in range(30, 90):
            camera.crop(frame, i / 30, (360, 640))
        self.assertGreater(camera.camera[0], left + 250)
        self.assertGreaterEqual(camera.camera[2], 360 / 1.18)
        self.assertLessEqual(camera.camera[2], 360)


if __name__ == '__main__':
    unittest.main()
