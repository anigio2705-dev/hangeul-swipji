"""Regression checks for stale and missing CI evidence, using a disposable git repo."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('ci_evidence', Path(__file__).with_name('ci-evidence.py'))
evidence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evidence)

class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'repo'
        self.root.mkdir()
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        subprocess.run(['git', '-c', 'user.name=CI Fixture', '-c', 'user.email=fixture@example.invalid',
                        'commit', '--allow-empty', '-qm', 'fixture'], cwd=self.root, check=True)
        self.output = Path(self.temp.name) / 'evidence'
        self.root_patch = patch.object(evidence, 'ROOT', self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    def write(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
        return path

    def manifest(self):
        return json.loads((self.output / 'manifest.json').read_text())

    def test_failed_job_does_not_publish_old_browser_success(self):
        stale = self.write('phase3/browser-results.json', {'checks': ['old success']})
        evidence.prepare('phase3', self.output)
        self.assertFalse(stale.exists())
        self.assertEqual(evidence.collect('phase3', self.output, 'failure'), 0)
        report = self.manifest()
        self.assertFalse(report['evidence_complete'])
        self.assertEqual(report['files'], [])
        self.assertIn('phase3/browser-results.json', report['missing_required'])

    def test_success_without_browser_evidence_fails(self):
        evidence.prepare('phase3', self.output)
        self.write('phase3/postgres-results.json', {'checks': ['fresh database']})
        self.assertEqual(evidence.collect('phase3', self.output, 'success'), 1)
        self.assertFalse(self.manifest()['evidence_complete'])

    def test_fresh_artifacts_are_bound_to_checkout_and_job(self):
        evidence.prepare('phase3', self.output)
        for name in evidence.REQUIRED['phase3']:
            self.write(name, {'checks': ['fresh']})
        self.assertEqual(evidence.collect('phase3', self.output, 'success'), 0)
        report = self.manifest()
        self.assertTrue(report['evidence_complete'])
        self.assertEqual(len(report['checkout_sha']), 40)
        self.assertEqual(len(report['files']), 2)
        self.assertTrue(all(len(item['sha256']) == 64 for item in report['files']))
        self.assertEqual(report['context'], evidence.context())

    def test_different_run_cannot_claim_existing_evidence(self):
        evidence.prepare('phase3', self.output)
        with patch.dict('os.environ', {'GITHUB_RUN_ID': 'different-run'}):
            with self.assertRaisesRegex(RuntimeError, 'CI_EVIDENCE_CONTEXT_CHANGED'):
                evidence.collect('phase3', self.output, 'success')

    def test_green_job_with_late_browser_error_is_rejected(self):
        evidence.prepare('phase3', self.output)
        self.write('phase3/postgres-results.json', {'checks': ['fresh database']})
        self.write('phase3/browser-results.json', {'checks': ['earlier pass'],
                    'errors': ["Cannot read properties of undefined (reading 'dispose')"]})
        self.assertEqual(evidence.collect('phase3', self.output, 'success'), 1)
        self.assertFalse(self.manifest()['evidence_complete'])
        self.assertEqual(self.manifest()['reports_with_errors'], ['phase3/browser-results.json'])

if __name__ == '__main__':
    unittest.main()
