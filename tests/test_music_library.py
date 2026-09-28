import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from music import catalog, choose_track, manual_music_info, select_music
from runtime import ASSETS
from selector import Clip

class MusicLibraryTests(unittest.TestCase):
    def test_library_contains_100_distinct_playable_assets_with_sources(self):
        tracks = catalog()
        self.assertGreaterEqual(len(tracks), 100)
        hashes = set()
        for track in tracks:
            data = (ASSETS/'assets/music'/track['file']).read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            self.assertNotIn(digest, hashes)
            hashes.add(digest)
            if track['artist'] == 'Kevin MacLeod':
                self.assertEqual(digest, track['sha256'])
                self.assertGreaterEqual(track['duration'], 12)
                self.assertTrue(track['source'].startswith('https://incompetech.com/'))
        for mood in ('energetic', 'playful', 'dramatic', 'calm'):
            self.assertGreaterEqual(sum(t['mood'] == mood for t in tracks), 20)

    def test_rotation_survives_reloading_history_and_avoids_boundary_repeat(self):
        tracks = [dict(file=str(i), mood='calm') for i in range(5)]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'history.json'
            cycle = [choose_track(tracks, 'calm', path)['file'] for _ in tracks]
            self.assertEqual(len(set(cycle)), 5)
            self.assertNotEqual(choose_track(tracks, 'calm', path)['file'], cycle[-1])
            path.write_text('broken')
            self.assertIn(choose_track(tracks, 'calm', path), tracks)

    def test_manual_licensed_track_keeps_attribution(self):
        track = next(t for t in catalog() if t['artist'] == 'Kevin MacLeod')
        info = manual_music_info(str(ASSETS/'assets/music'/track['file']))
        self.assertIn(track['title'], info['credit'])
        self.assertIn('Creative Commons Attribution 4.0', info['credit'])

    def test_content_types_choose_matching_moods(self):
        capture = Mock()
        capture.read.return_value = (False, None)
        with patch('music.cv2.VideoCapture', return_value=capture), patch('music.first_beat', return_value=0):
            for category, mood in [('football','energetic'), ('challenge','energetic'), ('animation','playful'), ('movie','dramatic'), ('speech','calm')]:
                self.assertEqual(select_music('unused', Clip(0,20,'',0,''), [], category)['mood'], mood)
