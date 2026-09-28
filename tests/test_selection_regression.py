"""Preserve ranking, diversity, boundaries and titles across selector optimizations."""
import unittest
from selector import select_clips


class SelectionRegressionTests(unittest.TestCase):
    def test_hour_of_dialogue_keeps_all_ten_ranked_choices(self):
        phrases = ['Why this challenge changes everything.',
                   'The players have twenty minutes left.',
                   'Finally the winner completed the challenge.',
                   'Another contestant takes a difficult chance.']
        segments = [dict(start=i*4., end=i*4.+3.8, text=phrases[i%4], words=[])
                    for i in range(900)]
        clips = select_clips(segments, 10, 90, 3600, 'challenge')
        self.assertEqual(len(clips),10)
        self.assertTrue(all(a.end<=b.start for a,b in zip(clips,clips[1:])))
        self.assertTrue(all(58<=c.end-c.start<=120.3 for c in clips))
        self.assertTrue(all('challenge' in c.reason for c in clips))
        self.assertEqual([c.to_dict() for c in clips],
                         [c.to_dict() for c in select_clips(segments,10,90,3600,'challenge')])
