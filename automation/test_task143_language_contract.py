"""#143 partial static gate: eight approved UI languages, not translation quality.

Runs without network, browser, production data, or model API calls.
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = ["ko", "en", "ja", "es", "ru", "zh-CN", "mn", "vi"]


def codes(source):
    match = re.search(r"\blanguages=(\[\[.*?\]\]);", source, re.S)
    if not match:
        raise ValueError("missing canonical language list")
    data = json.loads(match.group(1))
    if not all(isinstance(row, list) and len(row) == 2 for row in data):
        raise ValueError("invalid language tuples")
    result = [row[0] for row in data]
    if result != EXPECTED or len(set(result)) != len(result):
        raise ValueError("unsupported, duplicate, or missing approved language")
    return result


class Task143LanguageContract(unittest.TestCase):
    def test_exact_eight_supported_codes(self):
        source = (ROOT / "site-language.js").read_text(encoding="utf-8")
        self.assertEqual(codes(source), EXPECTED)
        self.assertIn("hs-site-language", source)
        self.assertIn("googtrans", source)

    def test_negative_missing_duplicate_and_extra(self):
        fixture = 'var KEY="x",languages=[["ko","Korean"],["en","English"],["ja","Japanese"],["es","Spanish"],["ru","Russian"],["zh-CN","Chinese"],["mn","Mongolian"],["vi","Vietnamese"]];'
        self.assertEqual(codes(fixture), EXPECTED)
        for altered in (
            fixture.replace('["vi","Vietnamese"]', '["en","English"]'),
            fixture.replace(',["vi","Vietnamese"]', ''),
            fixture.replace('["vi","Vietnamese"]', '["fr","French"]'),
        ):
            with self.subTest(altered=altered[-45:]):
                with self.assertRaises(ValueError):
                    codes(altered)

    def test_extended_selector_is_separate_unverified_surface(self):
        extra = (ROOT / "global-language.js").read_text(encoding="utf-8")
        self.assertIn("Français", extra)
        # This is a risk inventory, NOT proof that both selectors load together.
        self.assertNotEqual(extra, (ROOT / "site-language.js").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
