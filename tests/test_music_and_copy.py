import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock
from publishing import groq_copy, write_upload_details
from captions import write_captions
from selector import Clip
from music import select_music


class OptionalFeaturesTests(unittest.TestCase):
    def test_groq_sends_only_grounded_text_and_validates_tags(self):
        response = Mock(status_code=200)
        response.json.return_value = {'choices': [{'message': {'content': json.dumps({'title': 'A specific moment', 'description': 'A clear description of the challenge moment. '*10, 'hashtags': ['#Challenge', '#Shorts', '#Challenge', 'bad tag']})}}]}
        with patch('requests.post', return_value=response) as post:
            title, description, tags = groq_copy('Match', 'What a save!', 'challenge', 'English', 'test-key')
        self.assertEqual(len(tags),7)
        self.assertIn('#Challenge',tags)
        payload = post.call_args.kwargs['json']
        self.assertNotIn('test-key', json.dumps(payload))
        self.assertIn('What a save!', payload['messages'][1]['content'])

    def test_offline_mode_never_calls_groq(self):
        with tempfile.TemporaryDirectory() as folder, patch('requests.post') as post:
            result = write_upload_details(Path(folder)/'short.mp4', 'Film', Clip(0, 20, 'Scene', 0, ''), [], 'challenge', 1)
        post.assert_not_called()
        self.assertEqual(result['provider'], 'offline')

    def test_groq_failure_falls_back_without_leaking_key_and_keeps_credit(self):
        with tempfile.TemporaryDirectory() as folder, patch('requests.post', side_effect=RuntimeError('SECRET')):
            result = write_upload_details(Path(folder)/'short.mp4', 'Film', Clip(0, 20, 'Scene', 0, ''), [], 'challenge', 1, use_groq=True, api_key='SECRET', music_credit='Required artist credit')
            saved = Path(result['file']).read_text(encoding='utf-8')
        self.assertNotIn('SECRET', json.dumps(result)+saved)
        self.assertIn('Required artist credit', saved)
        self.assertIsNotNone(result['warning'])

    def test_auto_music_always_uses_the_fixed_energetic_pool(self):
        with patch('music.first_beat', side_effect=AssertionError('Bundled music must not be decoded again')):
            track=select_music('unused',Clip(0,20,'',0,''),[{'start':0,'end':15,'text':'I am sorry. Goodbye.'}],'challenge')
        self.assertEqual(track['mood'],'energetic')
        self.assertEqual(track['offset'],track['onset'])
        self.assertGreaterEqual(track['offset'],0)
        self.assertLess(track['offset'],8)
