import json
from pathlib import Path
import tempfile
import unittest
from captions import write_captions, timestamp
from selector import select_clips


class SelectionTests(unittest.TestCase):
    def test_selected_ranges_are_bounded_and_nonoverlapping(self):
        segments = [{"start": i * 5, "end": i * 5 + 4.8, "text": f"Here is why building school number {i} changes lives."} for i in range(40)]
        clips = select_clips(segments, count=3, target=30, duration=200)
        self.assertEqual(len(clips), 3)
        for clip in clips:
            self.assertGreaterEqual(clip.start, 0)
            self.assertLessEqual(clip.end, 200)
            self.assertLessEqual(clip.end - clip.start, 41)
        for a, b in zip(clips, clips[1:]):
            self.assertLessEqual(a.end, b.start)

    def test_short_source_does_not_request_nonexistent_audio(self):
        clips = select_clips([{"start": 0, "end": 7, "text": "This is a complete short video."}], duration=8)
        self.assertEqual(len(clips), 1)
        self.assertEqual(clips[0].end, 8)

    def test_no_speech_has_actionable_error(self):
        with self.assertRaisesRegex(ValueError, "No speech"):
            select_clips([])

    def test_real_transcript_selects_three_clips(self):
        path = Path(__file__).resolve().parents[1] / "transcripts/v9QtM6qnG50.json"
        if not path.exists():
            self.skipTest("Local sample transcript unavailable")
        clips = select_clips(json.loads(path.read_text(encoding="utf-8")), 3, 40, 1142.394)
        self.assertEqual(len(clips), 3)
        self.assertTrue(all(c.start < c.end <= 1142.394 for c in clips))


class CaptionTests(unittest.TestCase):
    def test_clip_relative_word_times_and_literal_braces(self):
        segments = [{"start": 10, "end": 12, "text": "Hello {world}", "words": [{"start": 10, "end": 11, "word": "Hello"}, {"start": 11, "end": 12, "word": "{world}"}]}]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "captions.ass"
            write_captions(path, segments, 10, 12)
            text = path.read_text(encoding="utf-8")
            self.assertIn("0:00:00.00,0:00:02.00", text)
            self.assertIn("{\\k100}Hello", text)
            self.assertIn("(world)", text)
            self.assertNotIn("{world}", text)

    def test_timestamp_rounding_carries_into_next_minute(self):
        self.assertEqual(timestamp(59.999), "0:01:00.00")


if __name__ == "__main__":
    unittest.main()
