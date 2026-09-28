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
    def test_library_contains_50_distinct_playable_assets_with_sources(self):
        tracks = catalog()
        self.assertEqual(len(tracks), 50)
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
        self.assertTrue(all(t['mood']=='energetic' for t in tracks))

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

    def test_supported_types_share_the_fixed_pool(self):
        with patch('music.first_beat',return_value=0):
            for category in ('challenge',):
                self.assertEqual(select_music('unused',Clip(0,20,'',0,''),[],category)['mood'],'energetic')
