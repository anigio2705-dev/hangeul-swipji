#!/usr/bin/env python3
"""Non-destructive team12 educational structure and audio state regression."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class Team12Regression(unittest.TestCase):
    def test_professional_96_unique_and_linked(self):
        data = json.loads((ROOT / "phase3/curriculum-96.json").read_text(encoding="utf-8"))
        stages = data["stages"]
        self.assertEqual(len(stages), 4)
        lessons = [lesson for stage in stages for lesson in stage["lessons"]]
        self.assertEqual([len(stage["lessons"]) for stage in stages], [24] * 4)
        self.assertEqual(len(lessons), 96)
        for field in ("slot", "unitId"):
            values = [lesson.get(field) for lesson in lessons]
            self.assertTrue(all(values), field)
            self.assertEqual(len(values), len(set(values)), field)
        self.assertTrue(all(lesson.get("status") == "authored" for lesson in lessons))

    def test_pilot_units_reference_professional_curriculum(self):
        curriculum = json.loads((ROOT / "phase3/curriculum-96.json").read_text(encoding="utf-8"))
        pilot = json.loads((ROOT / "phase3/content.json").read_text(encoding="utf-8"))
        ids = {lesson["unitId"] for stage in curriculum["stages"] for lesson in stage["lessons"]}
        units = pilot["units"]
        self.assertEqual(len(units), 12)
        self.assertEqual(len({unit["id"] for unit in units}), len(units))
        self.assertTrue(all(unit["id"] in ids for unit in units))

    def test_hangul_manifest_no_synthetic_or_approved_without_review(self):
        manifest = json.loads((ROOT / "hangul-audio-manifest.json").read_text(encoding="utf-8"))
        for word, entry in manifest["recordings"].items():
            self.assertEqual(entry.get("kind"), "human", word)
            self.assertTrue(entry.get("sourceUrl"), word)
            self.assertTrue(entry.get("author"), word)
            self.assertTrue(entry.get("license"), word)
            self.assertNotEqual(entry.get("listeningReview", {}).get("status"), "approved", word)

if __name__ == "__main__":
    unittest.main()
