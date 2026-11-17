"""Accepted history must not weaken byte preservation for later edits."""
import contextlib
import io
from pathlib import Path
import runpy
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

class PreservationGateTests(unittest.TestCase):
    def run_gate(self, changed=None):
        read_bytes = Path.read_bytes
        def read(path):
            value = read_bytes(path)
            return value + b'\nUNAPPROVED_CHANGE\n' if path == ROOT / changed else value
        with patch.object(Path, 'read_bytes', side_effect=None, autospec=True) as reader:
            reader.side_effect = read
            with patch.object(Path, 'write_text'), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as outcome:
                    runpy.run_path(str(ROOT / 'scripts/audit-professional-96.py'), run_name='__main__')
        return outcome.exception.code

    def test_fixed_accepted_history_passes(self):
        self.assertFalse(self.run_gate('__unchanged__'))

    def test_later_intro_edit_is_rejected(self):
        self.assertTrue(self.run_gate('intro.html'))

    def test_other_original_file_edit_is_rejected(self):
        self.assertTrue(self.run_gate('beginner1.html'))

if __name__ == '__main__':
    unittest.main()
