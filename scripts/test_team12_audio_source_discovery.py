"""Deterministic human audio source discovery tests; no network or downloads."""
import unittest
from team12_audio_source_discovery import candidate, discover, exact_target

def page(title, license_name="CC BY-SA 4.0", author="Speaker"):
    return {"title": title, "imageinfo": [{"url": "https://upload.wikimedia.org/wikipedia/commons/a/a/a.ogg",
        "descriptionurl": "https://commons.wikimedia.org/wiki/File:Example",
        "extmetadata": {"LicenseShortName": {"value": license_name},
                        "Artist": {"value": author},
                        "LicenseUrl": {"value": "https://creativecommons.org/licenses/by-sa/4.0"}}}]}

class SourceDiscoveryTests(unittest.TestCase):
    def test_exact_label_only(self):
        self.assertTrue(exact_target("File:Ko-고.ogg", "고"))
        self.assertTrue(exact_target("File:LL-Q9176 (kor)-Speaker-고.wav", "고"))
        for title in ("File:Ko-고기.ogg", "File:Ko-광고.ogg", "File:Ko-고.mp3",
                      "File:LL-Q9176 (eng)-Speaker-고.wav", "File:Ko-고.ogg/other"):
            self.assertFalse(exact_target(title, "고"), title)

    def test_only_attributed_free_license_candidates(self):
        self.assertIsNotNone(candidate(page("File:Ko-고.ogg"), "고"))
        self.assertIsNone(candidate(page("File:Ko-고.ogg", "CC BY-NC 4.0"), "고"))
        self.assertIsNone(candidate(page("File:Ko-고.ogg", author=""), "고"))
        self.assertIsNone(candidate(page("File:Ko-고기.ogg"), "고"))
        unsafe=page("File:Ko-고.ogg")
        unsafe["imageinfo"][0]["url"]="http://evil.invalid/a.ogg"
        self.assertIsNone(candidate(unsafe, "고"))

    def test_priority_and_no_false_completion(self):
        entries=[{"character":ch,"status":"missing"} for ch in ("가","라","고","하","노")]
        entries.append({"character":"누","status":"held"})
        result=discover({"recording_inventory":entries},3,
                        query=lambda ch:[{"character":ch,"status":"review"}])
        self.assertEqual(result["searched"],["고","노","라"])
        self.assertEqual(result["inventory_missing"],5)
        self.assertEqual(result["new_recordings_imported"],0)
        self.assertEqual(result["listening_approved"],0)

    def test_network_failure_is_visible_not_a_negative_result(self):
        def fail(ch):
            if ch=="고": raise TimeoutError("timeout")
            return []
        result=discover({"recording_inventory":[{"character":"고","status":"missing"},
                 {"character":"노","status":"missing"}]},2,query=fail)
        self.assertEqual(result["candidate_count"],0)
        self.assertEqual(result["failed_queries"],[{"character":"고","error":"TimeoutError"}])
        with self.assertRaises(ValueError):
            discover({"recording_inventory":[]},41)

if __name__=="__main__":
    unittest.main()
