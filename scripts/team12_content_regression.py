#!/usr/bin/env python3
"""Non-destructive team12 educational structure and audio state regression."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class Team12Regression(unittest.TestCase):
    def test_seven_course_resume_deep_links(self):
        dashboard = (ROOT / "dashboard.html").read_text(encoding="utf-8")
        self.assertIn("window.HSTeam12Resume.nextLesson(state)", dashboard)
        self.assertIn('window.addEventListener("storage"', dashboard)
        self.assertIn('document.addEventListener("visibilitychange"', dashboard)
        self.assertIn('"?unit="+nextUnit', dashboard)
        for name in ("intro", "beginner1", "beginner2", "intermediate1",
                     "intermediate2", "advanced1", "advanced2"):
            page = (ROOT / (name + ".html")).read_text(encoding="utf-8")
            self.assertIn('new URLSearchParams(location.search).get("unit")', page, name)
            self.assertIn('/^[0-9]+$/.test(requested)', page, name)
            self.assertIn('n>=1&&n<=units.length', page, name)
            self.assertIn('unit=n-1;tab=0;reviewMode=false', page, name)

    def test_audio_418_scope_reconciliation(self):
        """399 composed cells + 19 consonant signs = 418 only if HQ confirms scope."""
        plan = json.loads((ROOT / "docs/team12/recording-plan-399.json").read_text(encoding="utf-8"))
        cells = plan["cells"]
        self.assertEqual(len(cells), 399)
        self.assertEqual(len({c["syllable"] for c in cells}), 399)
        consonants = {c["consonant"] for c in cells}
        vowels = {c["vowel"] for c in cells}
        self.assertEqual(len(consonants), 19)
        self.assertEqual(len(vowels), 21)
        self.assertEqual(len(cells) + len(consonants), 418)
        self.assertEqual(sum(c["status"] == "missing" for c in cells), 354)
        self.assertEqual(sum(c["status"] == "held" for c in cells), 26)
        self.assertEqual(sum(c["status"] == "ready_unapproved" for c in cells), 19)
        self.assertEqual(len(cells), sum(plan["counts"].values()))

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
        consonants = "\u3131\u3132\u3134\u3137\u3138\u3139\u3141\u3142\u3143\u3145\u3146\u3147\u3148\u3149\u314a\u314b\u314c\u314d\u314e"
        vowels = "\u314f\u3150\u3151\u3152\u3153\u3154\u3155\u3156\u3157\u3158\u3159\u315a\u315b\u315c\u315d\u315e\u315f\u3160\u3161\u3162\u3163"
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
        self.assertIn("field('\uc0c8\uc5ec \uc720\ud615','role',state.team12ProviderRole||''", app)
        self.assertIn("state.view='discover'", app)
        self.assertIn("data-team12-handoff", home)
        self.assertIn("scripts/team12_learning_handoff.js", home)
        self.assertIn("['partner','\ud68c\ud654 \ud30c\ud2b8\ub108 \ucc3e\uae30']", handoff)
        self.assertIn("['teacher','\uc804\ubb38 \uac15\uc0ac \ucc3e\uae30']", handoff)
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
        self.assertIn("field('\uc0c8\uc5ec \uc720\ud615','role',state.team12ProviderRole||''", app)

    def test_dashboard_to_provider_booking_discovery_contract(self):
        dashboard = (ROOT / "dashboard.html").read_text(encoding="utf-8")
        self.assertIn('href="./learn.html"', dashboard)
        self.assertIn('data-team12-provider="partner"', dashboard)
        self.assertIn('data-team12-provider="teacher"', dashboard)
        self.assertIn('scripts/team12_provider_links.js', dashboard)
        self.assertIn('href="./index.html#teaching-platform"', dashboard)

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
