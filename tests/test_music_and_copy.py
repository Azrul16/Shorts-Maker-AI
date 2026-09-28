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
        response.json.return_value = {'choices': [{'message': {'content': json.dumps({'title': 'A specific moment', 'description': 'A clear description.', 'hashtags': ['#Football', '#Shorts', '#Football', 'bad tag']})}}]}
        with patch('requests.post', return_value=response) as post:
            title, description, tags = groq_copy('Match', 'What a save!', 'football', 'English', 'test-key')
        self.assertEqual(tags, ['#Football', '#Shorts'])
        payload = post.call_args.kwargs['json']
        self.assertNotIn('test-key', json.dumps(payload))
        self.assertIn('What a save!', payload['messages'][1]['content'])

    def test_offline_mode_never_calls_groq(self):
        with tempfile.TemporaryDirectory() as folder, patch('requests.post') as post:
            result = write_upload_details(Path(folder)/'short.mp4', 'Film', Clip(0, 20, 'Scene', 0, ''), [], 'movie', 1)
        post.assert_not_called()
        self.assertEqual(result['provider'], 'offline')

    def test_groq_failure_falls_back_without_leaking_key_and_keeps_credit(self):
        with tempfile.TemporaryDirectory() as folder, patch('requests.post', side_effect=RuntimeError('SECRET')):
            result = write_upload_details(Path(folder)/'short.mp4', 'Film', Clip(0, 20, 'Scene', 0, ''), [], 'movie', 1, use_groq=True, api_key='SECRET', music_credit='Required artist credit')
            saved = Path(result['file']).read_text(encoding='utf-8')
        self.assertNotIn('SECRET', json.dumps(result)+saved)
        self.assertIn('Required artist credit', saved)
        self.assertIsNotNone(result['warning'])

    def test_auto_music_respects_sad_dialogue_over_action_category(self):
        capture = Mock()
        capture.read.return_value = (False, None)
        with patch('music.cv2.VideoCapture', return_value=capture), patch('music.first_beat', return_value=.25):
            track = select_music('video', Clip(0, 20, '', 0, ''), [{'start': 0, 'end': 15, 'text': 'I am sorry. Goodbye.'}], 'action')
        self.assertEqual(track['mood'], 'calm')
        self.assertEqual(track['offset'], .25)
        capture.release.assert_called_once()
