import unittest
from hq_six_developers import apply_patch, validate_candidate

class BoundedPatchTests(unittest.TestCase):
    def test_single_unique_patch_and_valid_python(self):
        original = "def calculate_total(value):\n    return value + 1\n" + ("# meaningful existing code context\n" * 5)
        changed = apply_patch(original, {
            "old": "return value + 1",
            "new": "return value + 2",
            "reason": "fix arithmetic",
        })
        self.assertIn("return value + 2", changed)
        validate_candidate(original, changed, "example.py")

    def test_ambiguous_or_null_patch_rejected(self):
        original = "def a():\n    return 123\ndef b():\n    return 123\n"
        with self.assertRaisesRegex(ValueError, "unambiguous"):
            apply_patch(original, {"old": "    return 123", "new": "    return 456"})
        with self.assertRaisesRegex(ValueError, "Null"):
            apply_patch(original, {"old": "def a():\n    return 123",
                                   "new": "def a():\n    return '" + chr(0) + "'"})

    def test_team15_collision_gate_cannot_be_weakened_by_ai(self):
        original = ("changes = {'11': {'shared.py'}, '13': {'shared.py'}}\n"
                    "failures = []\n"
                    "common = ['shared.py']\n"
                    "if common:\n"
                    "    failures.append('overlap')\n"
                    "# preserve existing verification\n")
        weakened = original.replace(
            "    failures.append('overlap')",
            "    if 'shared.py' in []:\n        failures.append('overlap')")
        with self.assertRaisesRegex(ValueError, "Collision gate weakening forbidden"):
            validate_candidate(original, weakened, "scripts/team15_independent_gate.py")
        safe = original.replace("# preserve existing verification",
                                "# preserve existing verification and audit every collision")
        validate_candidate(original, safe, "scripts/team15_independent_gate.py")

    def test_truncated_or_whole_file_patch_rejected(self):
        with self.assertRaisesRegex(ValueError, "large"):
            apply_patch("x" * 10000, {"old": "x" * 5000, "new": "y" * 5000})
        with self.assertRaisesRegex(ValueError, "unambiguous"):
            apply_patch("def a():\n    return 123\n", {
                "old": "def a():\n    return 123",
                "new": "def a():\n    return 123"})

if __name__ == "__main__":
    unittest.main()
