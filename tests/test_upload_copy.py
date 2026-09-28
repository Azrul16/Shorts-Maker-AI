import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch,Mock
from publishing import hashtags,groq_copy,write_upload_details
from selector import Clip


class UploadCopyTests(unittest.TestCase):
    def test_seven_unique_grounded_tags_even_when_model_supplies_junk(self):
        tags=hashtags(['#Viral','#UnrelatedPerson','#Challenge','#challenge','#FYP','#Save'],'challenge','A save during the challenge')
        self.assertEqual(len(tags),7)
        self.assertEqual(len(set(t.lower() for t in tags)),7)
        self.assertIn('#Save',tags)
        self.assertNotIn('#UnrelatedPerson',tags)
        self.assertNotIn('#Viral',tags)
        self.assertIn('#Shorts',tags)

    def test_offline_description_is_substantial_and_keeps_credits(self):
        with tempfile.TemporaryDirectory() as folder:
            result=write_upload_details(Path(folder)/'clip.mp4','Last to leave',Clip(0,30,'The challenge begins',1,''),[],'challenge',1,music_credit='Required credit')
        self.assertEqual(len(result['hashtags']),7)
        self.assertGreaterEqual(len(result['description'].split()),70)
        self.assertIn('Required credit',result['description'])
        self.assertLessEqual(len(result['title']),100)

    def test_short_model_description_is_rejected(self):
        response=Mock(status_code=200)
        response.json.return_value={'choices':[{'message':{'content':'{"title":"A goal","description":"Watch it.","hashtags":["#Challenge"]}'}}]}
        with patch('requests.post',return_value=response):
            with self.assertRaises(ValueError):
                groq_copy('Challenge','A goal','challenge','English','test-key')
