#!/usr/bin/env python3
"""Non-destructive team12 educational structure and audio state regression."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class Team12Regression(unittest.TestCase):
    def test_seven_course_resume_deep_links(self):
        dashboard_file = ROOT / "dashboard.html"
        self.assertTrue(dashboard_file.exists(), f"Missing file: {dashboard_file}")
        dashboard = dashboard_file.read_text(encoding="utf-8")
        self.assertIn("window.HSTeam12Resume.nextLesson(state)", dashboard)
        self.assertIn('window.addEventListener("storage"', dashboard)
        self.assertIn('document.addEventListener("visibilitychange"', dashboard)
        self.assertIn('"?unit="+nextUnit', dashboard)
        for name in ("intro", "beginner1", "beginner2", "intermediate1",
                     "intermediate2", "advanced1", "advanced2"):
            page_file = ROOT / (name + ".html")
            self.assertTrue(page_file.exists(), f"Missing file: {page_file}")
            page = page_file.read_text(encoding="utf-8")
            self.assertIn('new URLSearchParams(location.search).get("unit")', page, name)
            self.assertIn('/^[0-9]+$/.test(requested)', page, name)
            self.assertIn('n>=1&&n<=units.length', page, name)
            self.assertIn('unit=n-1;tab=0;reviewMode=false', page, name)

    def test_audio_418_scope_reconciliation(self):
        plan_file = ROOT / "docs/team12/recording-plan-399.json"
        self.assertTrue(plan_file.exists(), f"Missing file: {plan_file}")
        plan_content = plan_file.read_text(encoding="utf-8")
        try:
            plan = json.loads(plan_content)
        except json.JSONDecodeError as e:
            self.fail(f"Invalid JSON in {plan_file}: {e}")
        self.assertIn("cells", plan)
        cells = plan["cells"]
        self.assertIsInstance(cells, list)
        self.assertEqual(len(cells), 399)
        syllables = set()
        for c in cells:
            self.assertIsInstance(c, dict, "Each cell must be a dict")
            self.assertIn("syllable", c)
            syllable_value = c["syllable"]
            self.assertIsInstance(syllable_value, str, "syllable must be string")
            syllables.add(syllable_value)
        self.assertEqual(len(syllables), 399)
        consonants = set()
        vowels = set()
        for c in cells:
            self.assertIsInstance(c, dict, "Each cell must be a dict")
            self.assertIn("consonant", c)
            self.assertIn("vowel", c)
            consonant_value = c["consonant"]
            vowel_value = c["vowel"]
            self.assertIsInstance(consonant_value, str, "consonant must be string")
            self.assertIsInstance(vowel_value, str, "vowel must be string")
            consonants.add(consonant_value)
            vowels.add(vowel_value)
        self.assertEqual(len(consonants), 19)
        self.assertEqual(len(vowels), 21)
        self.assertEqual(len(cells) + len(consonants), 418)
        statuses = [c.get("status") for c in cells if isinstance(c, dict)]
        self.assertEqual(statuses.count("missing"), 354)
        self.assertEqual(statuses.count("held"), 26)
        self.assertEqual(statuses.count("ready_unapproved"), 19)
        self.assertIn("counts", plan)
        counts = plan["counts"]
        self.assertIsInstance(counts, dict, "counts should be a dict")
        total_counts = sum(v for v in counts.values() if isinstance(v, int))
        self.assertEqual(len(cells), total_counts)

    def test_professional_96_unique_and_linked(self):
        data_file = ROOT / "phase3/curriculum-96.json"
        self.assertTrue(data_file.exists(), f"Missing file: {data_file}")
        data_content = data_file.read_text(encoding="utf-8")
        try:
            data = json.loads(data_content)
        except json.JSONDecodeError as e:
            self.fail(f"Invalid JSON in {data_file}: {e}")
        self.assertIn("stages", data)
        stages = data["stages"]
        self.assertIsInstance(stages, list)
        self.assertEqual(len(stages), 4)
        lessons = [lesson for stage in stages for lesson in stage.get("lessons", []) if isinstance(lesson, dict)]
        self.assertEqual([len(stage.get("lessons", [])) for stage in stages], [24] * 4)
        self.assertEqual(len(lessons), 96)
        for field in ("slot", "unitId"):
            values = [lesson.get(field) for lesson in lessons]
            self.assertTrue(all(value is not None and value != '' for value in values), field)
            self.assertEqual(len(values), len(set(values)), field)
        self.assertTrue(all(lesson.get("status") == "authored" for lesson in lessons))

    def test_pilot_units_reference_professional_curriculum(self):
        curriculum_file = ROOT / "phase3/curriculum-96.json"
        pilot_file = ROOT / "phase3/content.json"
        self.assertTrue(curriculum_file.exists(), f"Missing file: {curriculum_file}")
        self.assertTrue(pilot_file.exists(), f"Missing file: {pilot_file}")
        curriculum_content = curriculum_file.read_text(encoding="utf-8")
        pilot_content = pilot_file.read_text(encoding="utf-8")
        try:
            curriculum = json.loads(curriculum_content)
        except json.JSONDecodeError as e:
            self.fail(f"Invalid JSON in {curriculum_file}: {e}")
        try:
            pilot = json.loads(pilot_content)
        except json.JSONDecodeError as e:
            self.fail(f"Invalid JSON in {pilot_file}: {e}")
        ids = {lesson["unitId"] for stage in curriculum.get("stages", []) for lesson in stage.get("lessons", []) if isinstance(lesson, dict) and isinstance(lesson.get("unitId"), (str, int))}
        units = pilot.get("units", [])
        self.assertIsInstance(units, list, "units should be list")
        self.assertEqual(len(units), 12)
        unit_ids = {unit.get("id") for unit in units if unit and unit.get("id") is not None}
        self.assertEqual(len(unit_ids), len(units))
        self.assertTrue(all(unit.get("id") in ids for unit in units if unit))

    def test_399_board_cells_have_explicit_missing_and_held_states(self):
        manifest_file = ROOT / "hangul-audio-manifest.json"
        self.assertTrue(manifest_file.exists(), f"Missing file: {manifest_file}")
        manifest_content = manifest_file.read_text(encoding="utf-8")
        try:
            manifest = json.loads(manifest_content)
        except json.JSONDecodeError as e:
            self.fail(f"Invalid JSON in {manifest_file}: {e}")
        records = manifest.get("recordings", {})
        self.assertIsInstance(records, dict, "recordings should be a dict")
        consonants = "\u3131\u3132\u3134\u3137\u3138\u3139\u3141\u3142\u3143\u3145\u3146\u3147\u3148\u3149\u314a\u314b\u314c\u314d\u314e"
        vowels = "\u314f\u3150\u3151\u3152\u3153\u3154\u3155\u3156\u3157\u3158\u3159\u315a\u315b\u315c\u315d\u315e\u315f\u3160\u3161\u3162\u3163"
        counts = {"ready_unapproved": 0, "held": 0, "missing": 0}
        for i, _ in enumerate(consonants):
            for j, _ in enumerate(vowels):
                word = chr(0xAC00 + (i * 21 + j) * 28)
                entry = records.get(word)
                # Validate entry if it exists and is dict
                if entry is not None and not isinstance(entry, dict):
                    self.fail(f"Entry for {word} must be dict or None")
                state = "missing" if entry is None else ("held" if entry.get("disabled") else "ready_unapproved")
                counts[state] += 1
                if entry:
                    listening_review = entry.get("listeningReview", {})
                    self.assertIsInstance(listening_review, dict, f"listeningReview must be dict for {word}")
                    self.assertEqual(
                        listening_review.get("status"), "pending", word
                    )
        self.assertEqual(sum(counts.values()), 399)
        self.assertEqual(counts, {"ready_unapproved": 19, "held": 26, "missing": 354})

    def test_learner_to_provider_handoff_contract(self):
        app_file = ROOT / "phase3/app.js"
        home_file = ROOT / "index.html"
        handoff_file = ROOT / "scripts/team12_learning_handoff.js"
        self.assertTrue(app_file.exists(), f"Missing file: {app_file}")
        self.assertTrue(home_file.exists(), f"Missing file: {home_file}")
        self.assertTrue(handoff_file.exists(), f"Missing file: {handoff_file}")
        app = app_file.read_text(encoding="utf-8")
        home = home_file.read_text(encoding="utf-8")
        handoff = handoff_file.read_text(encoding="utf-8")
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
        learn_file = ROOT / "learn.html"
        links_file = ROOT / "scripts/team12_provider_links.js"
        app_file = ROOT / "phase3/app.js"
        self.assertTrue(learn_file.exists(), f"Missing file: {learn_file}")
        self.assertTrue(links_file.exists(), f"Missing file: {links_file}")
        self.assertTrue(app_file.exists(), f"Missing file: {app_file}")
        learn = learn_file.read_text(encoding="utf-8")
        links = links_file.read_text(encoding="utf-8")
        app = app_file.read_text(encoding="utf-8")
        self.assertIn('href="./dashboard.html"', learn)
        self.assertIn('data-team12-provider="partner"', learn)
        self.assertIn('data-team12-provider="teacher"', learn)
        self.assertIn('scripts/team12_provider_links.js', learn)
        self.assertIn("sessionStorage.setItem('hs-team12-provider-intent', role)", links)
        self.assertIn("sessionStorage.getItem('hs-team12-provider-intent')", app)
        self.assertIn("field('\uc0c8\uc5ec \uc720\ud615','role',state.team12ProviderRole||''", app)

    def test_dashboard_to_provider_booking_discovery_contract(self):
        dashboard_file = ROOT / "dashboard.html"
        self.assertTrue(dashboard_file.exists(), f"Missing file: {dashboard_file}")
        dashboard = dashboard_file.read_text(encoding="utf-8")
        self.assertIn('href="./learn.html"', dashboard)
        self.assertIn('data-team12-provider="partner"', dashboard)
        self.assertIn('data-team12-provider="teacher"', dashboard)
        self.assertIn('scripts/team12_provider_links.js', dashboard)
        self.assertIn('href="./index.html#teaching-platform"', dashboard)

    def test_audio_ui_missing_and_playing_event_contract(self):
        core_file = ROOT / "hangul-core.js"
        self.assertTrue(core_file.exists(), f"Missing file: {core_file}")
        core = core_file.read_text(encoding="utf-8")
        self.assertIn("return {status:'missing',missing}", core)
        self.assertIn("return {status:'held',missing}", core)
        self.assertIn("sound.onplaying=()=>", core)
        self.assertIn("sound.onerror=()=>", core)
        self.assertIn("new URL(records[word].src, document.baseURI)", core)

    def test_hangul_manifest_no_synthetic_or_approved_without_review(self):
        manifest_file = ROOT / "hangul-audio-manifest.json"
        self.assertTrue(manifest_file.exists(), f"Missing file: {manifest_file}")
        manifest_content = manifest_file.read_text(encoding="utf-8")
        try:
            manifest = json.loads(manifest_content)
        except json.JSONDecodeError as e:
            self.fail(f"Invalid JSON in {manifest_file}: {e}")
        recordings = manifest.get("recordings", {})
        self.assertIsInstance(recordings, dict)
        for word, entry in recordings.items():
            self.assertIsInstance(entry, dict)
            self.assertEqual(entry.get("kind"), "human", word)
            self.assertTrue(entry.get("sourceUrl"), word)
            self.assertTrue(entry.get("author"), word)
            self.assertTrue(entry.get("license"), word)
            listening_review = entry.get("listeningReview", {})
            self.assertIsInstance(listening_review, dict, f"listeningReview must be dict for {word}")
            self.assertNotEqual(
                listening_review.get("status"), "approved", word
            )

if __name__ == "__main__":
    unittest.main()
