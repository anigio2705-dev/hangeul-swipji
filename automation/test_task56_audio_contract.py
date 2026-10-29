"""Independent team15-style mapping/acceptance gate for backlog #56.

This audits the source and acceptance contract; it does NOT approve any audio.
"""
import ast
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class Task56ContractTests(unittest.TestCase):
    def test_human_recording_standard_covers_all_six_required_dimensions(self):
        text = (ROOT / 'docs/team11/human-audio-acceptance-standards.md').read_text(encoding='utf-8')
        for term in ('## 화자', '## 발음', '## 속도', '## 무음', '## 파일 형식', '## 확보',
                     '## 저작권', '700ms', '44.1kHz', 'WAV', '라이선스', '보류'):
            with self.subTest(term=term):
                self.assertIn(term, text)
        self.assertIn('실제 녹음 확보·저작권 확인·청취 승인·공개 사용을 의미하지 않는다', text)

    def test_source_is_actual_audio_candidate_inventory_not_placement_or_payments(self):
        path = ROOT / 'scripts/find-human-audio-sources.py'
        source = path.read_text(encoding='utf-8')
        ast.parse(source, filename=str(path))
        self.assertIn('commons.wikimedia.org/w/api.php', source)
        self.assertIn('extmetadata', source)
        self.assertIn("'listeningApproved':False", source)
        self.assertIn('failedBatches', source)
        self.assertNotIn('api/payments', source)
        self.assertNotIn('phase3/learning.py', source)

    def test_mapping_preserves_canonical_owner_and_requires_independent_gate(self):
        registry = json.loads((ROOT / 'automation/hq_semantic_contract_paths.json').read_text(encoding='utf-8'))
        entry = registry['items']['56']
        self.assertEqual(entry['owner'], '12')
        self.assertIn('11', entry['support'])
        self.assertEqual(entry['source_paths'], ['scripts/find-human-audio-sources.py'])
        self.assertIn('automation/test_task56_audio_contract.py', entry['test_paths'])
        self.assertIn(entry['state'], ('CANDIDATE', 'READY', 'CODE_VERIFIED'))
        if entry['state'] == 'READY':
            self.assertEqual(entry['independent_team15'], 'PASS')
            self.assertIn('/actions/runs/', entry['independent_ci_url'])

if __name__ == '__main__':
    unittest.main()
