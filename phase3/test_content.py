"""Checks the actual pilot curriculum rather than mocked server fixtures."""
import json
from pathlib import Path
import unittest
from collections import Counter

class CurriculumTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data=json.loads((Path(__file__).parent/'content.json').read_text())
        cls.units=data['units'] if isinstance(data,dict) else data
    def test_complete_role_linked_materials_and_answer_explanations(self):
        self.assertEqual(12,len(self.units))
        self.assertEqual(36,sum(len(x['assessment']) for x in self.units))
        for unit in self.units:
            for key in ('id','title','level','version','objectives','vocabulary','grammar','reading','dialogue','homework','assessment','teacherGuide','learnerGuide'):
                self.assertTrue(unit[key],(unit['id'],key))
            self.assertEqual(30,unit['durationMinutes'])
            self.assertEqual({'listening','speaking','reading','writing','roleplay'},set(unit['activities']))
            for item in unit['assessment']:
                self.assertTrue(all(item.get(k) for k in ('question','answer','explanation')),unit['id'])
    def test_assessment_evidence_is_present_in_declared_source(self):
        for unit in self.units:
            self.assertTrue(unit['objectivesEn']);self.assertTrue(unit['learnerGuideEn']);self.assertTrue(unit['performanceTask'])
            for item in unit['assessment']:
                source=unit['reading']+' '+' '.join(unit['dialogue']) if item['sourceType']=='reading_dialogue' else unit[item['sourceType']]
                if isinstance(source,list):source=' '.join(source)
                elif isinstance(source,dict):source=' '.join(str(v) for v in source.values())
                self.assertTrue(item['evidence']);self.assertTrue(item['scoringNote'])
                for quote in item['evidence']:self.assertIn(quote,source,(unit['id'],item['question']))
    def test_independent_readings_and_internal_level_progression(self):
        self.assertEqual(12,len({x['id'] for x in self.units}))
        self.assertEqual(12,len({x['reading'] for x in self.units}))
        levels=['A0','A1','A2','B1','B2','C1']
        self.assertEqual(Counter({k:2 for k in levels}),Counter(x['level'] for x in self.units))
        means=[sum(len(x['reading'].split()) for x in self.units if x['level']==l)/2 for l in levels]
        self.assertEqual(sorted(means),means) # Internal editorial measure, not CEFR certification.

if __name__=='__main__':unittest.main()
