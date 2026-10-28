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

    def test_399_board_cells_have_explicit_missing_and_held_states(self):
        manifest = json.loads((ROOT / "hangul-audio-manifest.json").read_text(encoding="utf-8"))
        records = manifest["recordings"]
        consonants = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
        vowels = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
        counts = {"ready_unapproved": 0, "held": 0, "missing": 0}
        for i, _ in enumerate(consonants):
            for j, _ in enumerate(vowels):
                word = chr(0xAC00 + (i * 21 + j) * 28)
                entry = records.get(word)
                state = "missing" if entry is None else ("held" if entry.get("disabled") else "ready_unapproved")
                counts[state] += 1
                if entry:
                    self.assertEqual(entry.get("listeningReview", {}).get("status"), "pending", word)
        self.assertEqual(sum(counts.values()), 399)
        self.assertEqual(counts, {"ready_unapproved": 19, "held": 26, "missing": 354})

    def test_learner_to_provider_handoff_contract(self):
        app = (ROOT / "phase3/app.js").read_text(encoding="utf-8")
        home = (ROOT / "index.html").read_text(encoding="utf-8")
        handoff = (ROOT / "scripts/team12_learning_handoff.js").read_text(encoding="utf-8")
        self.assertIn("state.team12ProviderRole=role", app)
        self.assertIn("sessionStorage.getItem('hs-team12-provider-intent')", app)
        self.assertIn("sessionStorage.removeItem('hs-team12-provider-intent')", app)
        self.assertIn("field('참여 유형','role',state.team12ProviderRole||''", app)
        self.assertIn("state.view='discover'", app)
        self.assertIn("data-team12-handoff", home)
        self.assertIn("scripts/team12_learning_handoff.js", home)
        self.assertIn("['partner','회화 파트너 찾기']", handoff)
        self.assertIn("['teacher','전문 강사 찾기']", handoff)
        self.assertNotIn("/api/bookings", handoff)
        self.assertNotIn("/api/payments", handoff)

    def test_free_learning_progress_to_booking_discovery_links(self):
        learn = (ROOT / "learn.html").read_text(encoding="utf-8")
        links = (ROOT / "scripts/team12_provider_links.js").read_text(encoding="utf-8")
        app = (ROOT / "phase3/app.js").read_text(encoding="utf-8")
        self.assertIn('href="./dashboard.html"', learn)
        self.assertIn('data-team12-provider="partner"', learn)
        self.assertIn('data-team12-provider="teacher"', learn)
        self.assertIn('scripts/team12_provider_links.js', learn)
        self.assertIn("sessionStorage.setItem('hs-team12-provider-intent', role)", links)
        self.assertIn("sessionStorage.getItem('hs-team12-provider-intent')", app)
        self.assertIn("field('참여 유형','role',state.team12ProviderRole||''", app)

    def test_audio_ui_missing_and_playing_event_contract(self):
        core = (ROOT / "hangul-core.js").read_text(encoding="utf-8")
        self.assertIn("return {status:'missing',missing}", core)
        self.assertIn("return {status:'held',missing}", core)
        self.assertIn("sound.onplaying=()=>", core)
        self.assertIn("sound.onerror=()=>", core)
        self.assertIn("new URL(records[word].src, document.baseURI)", core)

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
