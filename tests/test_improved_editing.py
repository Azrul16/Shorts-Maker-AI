from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import numpy as np

from activity import choose_activity_windows
from framing import FaceCamera
from music import audio_filter, music_path
from runtime import NO_WINDOW, probe, tool
from selector import editorial_score, sentences_from_transcript


class EditingTests(unittest.TestCase):
    def test_speech_window_splits_on_word_boundaries(self):
        segments = [{'start': 0, 'end': 5, 'text': 'First idea. Next idea.', 'words': [
            {'start': 0, 'end': 1, 'word': 'First'}, {'start': 1, 'end': 2, 'word': 'idea.'},
            {'start': 3, 'end': 4, 'word': 'Next'}, {'start': 4, 'end': 5, 'word': 'idea.'}]}]
        sentences = sentences_from_transcript(segments)
        self.assertEqual(len(sentences), 2)
        self.assertEqual(sentences[1]['start'], 3)

    def test_standalone_hook_beats_dependent_opening_and_ad(self):
        closing = {'text': 'Finally, the result changed everything.'}
        def score(opening, content='This discovery changed everything. ' * 9):
            return editorial_score({'text': opening}, closing, content, 30, 30, {})[0]
        good = score('Why does this happen?')
        self.assertGreater(good, score("He's never done this before."))
        self.assertGreater(good, score("How's it going?"))
        self.assertGreater(good, score('Why does this happen?', 'Use my promo code and subscribe.'))

    def test_action_selection_includes_peak_and_leadup(self):
        energy = np.full(600, .02)
        energy[200:216] = .5
        clips = choose_activity_windows(energy, 150, 2, 20)
        self.assertEqual(len(clips), 2)
        event = next(c for c in clips if c.start < 52 < c.end)
        self.assertLess(event.start, 48)
        self.assertLessEqual(clips[0].end, clips[1].start)

    def test_action_selection_does_not_treat_intro_boundary_as_a_peak(self):
        energy = np.full(600, .08)
        energy[:6] = .4
        energy[250:270] = .3
        clip = choose_activity_windows(energy, 150, 1, 30)[0]
        self.assertGreater(clip.start, 30)
        self.assertLess(clip.start, 65)

    def test_smart_framing_preserves_separated_people(self):
        class Detector:
            def setInputSize(self, value): pass
            def detect(self, frame):
                return None, np.array([[20, 80, 60, 70], [550, 80, 60, 70]], dtype=np.float32)
        frame = np.zeros((360, 640, 3), dtype=np.uint8)
        frame[:, :80] = (0, 0, 255)
        frame[:, -80:] = (255, 0, 0)
        camera = FaceCamera(follow=False)
        camera.follow = True
        camera.detector = Detector()
        result = camera.crop(frame, 0, (360, 640))
        self.assertEqual(camera.preserved_frames, 1)
        self.assertGreater(np.count_nonzero(result[:, :, 0] > 240), 3000)
        self.assertGreater(np.count_nonzero(result[:, :, 2] > 240), 3000)

    def test_missing_face_preserves_the_full_scene(self):
        camera = FaceCamera(follow=False)
        camera.crop(np.zeros((360, 640, 3), dtype=np.uint8), 0, (360, 640))
        self.assertEqual(camera.preserved_frames, 1)

    def test_builtin_music_and_off(self):
        self.assertTrue(music_path('ambient').is_file())
        self.assertTrue(music_path('beat').is_file())
        self.assertIsNone(music_path('off'))
        with self.assertRaises(ValueError):
            music_path('missing-music-file.wav')

    def test_music_ducks_under_original_audio(self):
        # Original audio has a 200 Hz tone only during seconds 2-4.
        # Background music is an 880 Hz tone throughout. Measure that component.
        voice = "aevalsrc=if(between(t\\,2\\,4)\\,0.4*sin(2*PI*200*t)\\,0):s=48000:d=6"
        command = [tool('ffmpeg'), '-v', 'error', '-f', 'lavfi', '-i', 'anullsrc=r=48000', '-f', 'lavfi', '-i', voice, '-f', 'lavfi', '-i', 'sine=frequency=880:sample_rate=48000:duration=6', '-filter_complex', audio_filter(6, .5), '-map', '[mixed]', '-t', '6', '-ac', '1', '-ar', '48000', '-f', 'f32le', 'pipe:1']
        result = subprocess.run(command, capture_output=True, creationflags=NO_WINDOW, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        samples = np.frombuffer(result.stdout, dtype='<f4')
        def magnitude(start):
            section = samples[round(start*48000):round((start+.5)*48000)]
            times = np.arange(len(section))/48000
            return abs(np.mean(section*np.exp(-2j*np.pi*880*times)))
        quiet = magnitude(1)
        speaking = magnitude(2.8)
        self.assertGreater(quiet, .005)
        self.assertLess(speaking, quiet*.5)
        self.assertLessEqual(float(np.max(np.abs(samples))), .951)

    def test_emoji_filename_can_be_verified(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'Football ⚽ highlights.mp4'
            subprocess.run([tool('ffmpeg'), '-y', '-v', 'error', '-f', 'lavfi', '-i', 'color=s=64x64:d=0.2', '-f', 'lavfi', '-i', 'sine=duration=0.2', '-c:v', 'libx264', '-c:a', 'aac', str(target)], check=True, creationflags=NO_WINDOW)
            self.assertEqual(probe(target)['width'], 64)


if __name__ == '__main__':
    unittest.main()
