import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from story import story_plan, cues, boundary_score, opening_penalty
from selector import Clip, select_clips
from effects import punch_zoom
from delivery import write_delivery
from music import select_music
from publishing import hashtags


class StoryStudioTests(unittest.TestCase):
    def test_setup_and_ending_outcome_are_preferred_to_incomplete_story(self):
        self.assertGreater(boundary_score(cues('If you survive, win $500.'),cues('You won!')),
                           boundary_score(cues('And then we went there.'),cues('Let me explain.')))

    def test_short_acknowledgments_do_not_outrank_contextual_hooks(self):
        self.assertGreater(opening_penalty('Thank you.'),opening_penalty('I built a city in this field.'))
        self.assertGreater(opening_penalty('Fine.'),opening_penalty('If you stay, you win $1000.'))
        self.assertEqual(opening_penalty('Win $1000!'),0)

    def test_story_events_are_clipped_and_use_word_time(self):
        words=[dict(word=w,start=t,end=t+.4) for w,t in [('We',10),('have',10.5),('one',11),('chance',11.5),('left.',12),('You',18),('won!',18.5)]]
        segment=dict(start=10,end=19,text='We have one chance left. You won!',words=words)
        short=story_plan([segment],Clip(10,15,'',0,''))
        self.assertFalse(short['has_payoff'])
        self.assertTrue(all(e['time']<5 for e in short['events']))
        full=story_plan([segment],Clip(5,25,'',0,''))
        self.assertTrue(full['has_payoff'])
        self.assertTrue(any(e['kind']=='payoff' and e['source_time']==18.5 for e in full['events']))
        self.assertTrue(all(b-a>=6 for a,b in zip(full['punch_times'],full['punch_times'][1:])))

    def test_no_dialogue_cues_means_no_artificial_punches(self):
        plan=story_plan([dict(start=0,end=10,text='We walked through the door.')],Clip(0,10,'',0,''))
        self.assertEqual(plan['punch_times'],[])
        self.assertTrue(all(punch_zoom(t/30,10,'energetic',[])==1 for t in range(300)))
        self.assertGreater(punch_zoom(4.6,10,'energetic',[4]),1)
        self.assertEqual(punch_zoom(5.3,10,'energetic',[4]),1)

    def test_music_uses_dialogue_vibe_and_artist_tags(self):
        tracks=[dict(file=str(i),mood='energetic',tags='Dark Intense',onset=0,license='test') for i in range(5)]
        tracks += [dict(file=str(i+5),mood='energetic',tags='Bouncy Humorous',onset=0,license='test') for i in range(5)]
        with patch('music.catalog',return_value=tracks),patch('music.choose_track',side_effect=lambda tracks,mood:tracks[0]) as choose:
            item=select_music('unused',Clip(0,10,'',0,''),[dict(start=0,end=10,text='Only one chance left. Do not fail.')],'challenge')
        self.assertEqual(item['vibe'],'suspense')
        self.assertTrue(all('Dark' in t['tags'] for t in choose.call_args.args[0]))

    def test_creator_tags_require_source_evidence(self):
        self.assertIn('#MrBeast',hashtags([],'challenge','MrBeast challenge'))
        self.assertNotIn('#MrBeast',hashtags(['#MrBeast'],'challenge','A local challenge'))
        self.assertEqual(len(hashtags([],'challenge','MrBeast challenge')),7)

    def test_delivery_preserves_copy_and_escapes_markup_and_filenames(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            upload=dict(title='<script>alert(1)</script>',description='First paragraph.\n\nMusic credit.',hashtags=['#Shorts'],file=str(root/'A & B.youtube.txt'))
            path=write_delivery(root,dict(clips=[dict(path=str(root/'A & B.mp4'),youtube=upload)]))
            text=Path(path).read_text(encoding='utf-8')
            self.assertNotIn('<script>',text)
            self.assertIn('&lt;script&gt;',text)
            self.assertIn('A%20%26%20B.mp4',text)
            with (root/'upload-index.csv').open(encoding='utf-8-sig',newline='') as handle:
                rows=list(csv.reader(handle))
            self.assertEqual(rows[1][2],upload['description'])
