import json
import unittest
from unittest.mock import Mock, patch

from credentials import groq_api_key
from publishing import groq_copy


class AutomaticCopyTests(unittest.TestCase):
    def test_environment_key_is_used_without_ui(self):
        with patch.dict('os.environ', {'GROQ_API_KEY': 'local-test-key'}):
            self.assertEqual(groq_api_key(), 'local-test-key')

    def test_saved_key_is_used_and_generic_hashtags_removed(self):
        response = Mock(status_code=200)
        response.json.return_value = {'choices': [{'message': {'content': json.dumps({
            'title': 'Fold the wings evenly', 'description': 'The final step in folding a paper airplane.',
            'hashtags': ['#Viral', '#FYP', '#PaperAirplane', '#DIY', '#Shorts']})}}]}
        with patch('publishing.groq_api_key', return_value='local-test-key'), patch('requests.post', return_value=response) as post:
            _, _, tags = groq_copy('Paper airplane', 'Fold the wings evenly.', 'speech', 'English', '')
        self.assertEqual(tags, ['#PaperAirplane', '#DIY', '#Shorts'])
        self.assertEqual(post.call_args.kwargs['headers']['Authorization'], 'Bearer local-test-key')
        self.assertNotIn('local-test-key', json.dumps(post.call_args.kwargs['json']))

    def test_windows_user_key_is_read_when_parent_environment_is_stale(self):
        import os
        if os.name != 'nt':
            self.skipTest('Windows user environment')
        with patch.dict('os.environ', {'GROQ_API_KEY': ''}), patch('winreg.OpenKey') as opened, patch('winreg.QueryValueEx', return_value=('stored-key', 1)):
            opened.return_value.__enter__.return_value = 'registry-handle'
            self.assertEqual(groq_api_key(), 'stored-key')
