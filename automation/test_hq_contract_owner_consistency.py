"""Independent guard: 160 markdown contract owners match the six HQ allocations.

This only verifies ownership metadata; it never promotes READY, CODE_VERIFIED,
test99 deployment, AI development calls, or representative approval.
Run: python -m unittest automation/test_hq_contract_owner_consistency.py -v
"""
import json
import re
import unittest
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "docs/HQ_160_DEVELOPMENT_CONTRACTS_20261029.md"
REGISTRY = ROOT / "automation/hq_semantic_contract_paths.json"

def expected_owner(number):
    if 1 <= number <= 10 or 151 <= number <= 160:
        return 15
    if 11 <= number <= 20 or 31 <= number <= 40 or 131 <= number <= 140:
        return 11
    if 21 <= number <= 30 or 81 <= number <= 100:
        return 13
    if 41 <= number <= 70:
        return 12
    if 71 <= number <= 80 or 101 <= number <= 130:
        return 14
    if 141 <= number <= 150:
        return 16
    raise ValueError(f"invalid backlog number {number}")

def parse_contract_owners(source):
    found = {}
    for line in source.splitlines():
        match = re.match(r"^\|\s*(\d{1,3})\s*\|[^|]*\|([^|]*)\|", line)
        if not match:
            continue
        number, cell = int(match.group(1)), match.group(2)
        if number in found:
            raise AssertionError(f"duplicate contract #{number}")
        owner = re.search(r"(?<![0-9])(11|12|13|14|15|16)(?![0-9])", cell)
        if not owner:
            raise AssertionError(f"missing team owner #{number}: {cell!r}")
        found[number] = int(owner.group(1))
    return found


def inspect_registry_mappings(registry, root):
    """Check actual mapped paths and canonical ownership; never grant READY."""
    failures = []
    items = registry.get("items", {})
    if not isinstance(items, dict):
        return ["registry.items must be a dictionary"]
    for key, item in items.items():
        if not isinstance(key, str) or not key.isdigit() or not 1 <= int(key) <= 160:
            failures.append(f"invalid task id {key!r}")
            continue
        if not isinstance(item, dict):
            failures.append(f"task #{key} must be an object")
            continue
        if item.get("owner") != str(expected_owner(int(key))):
            failures.append(f"task #{key} has wrong primary owner")
        for field in ("source_paths", "test_paths"):
            values = item.get(field)
            if not isinstance(values, list) or not values:
                failures.append(f"task #{key} has no {field}")
                continue
            for value in values:
                if (not isinstance(value, str) or not value
                        or PurePosixPath(value).is_absolute()
                        or ".." in PurePosixPath(value).parts
                        or "\\\\" in value
                        or not (root / value).is_file()):
                    failures.append(f"task #{key} invalid or absent {field}: {value!r}")
    return failures

class ContractOwnerConsistency(unittest.TestCase):

    def test_all_registered_source_and_test_paths_exist_with_correct_owner(self):
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(inspect_registry_mappings(registry, ROOT), [])

    def test_registry_rejects_wrong_owner_and_missing_test_file(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "feature.py").write_text("pass\\n")
            registry = {"items": {"22": {"owner": "12",
                "source_paths": ["feature.py"], "test_paths": ["missing_test.py"]}}}
            failures = inspect_registry_mappings(registry, root)
            self.assertTrue(any("wrong primary owner" in x for x in failures))
            self.assertTrue(any("missing_test.py" in x for x in failures))

    def test_registry_rejects_path_traversal_and_empty_sources(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            registry = {"items": {"143": {"owner": "16",
                "source_paths": ["../outside.js"],
                "test_paths": []}}}
            failures = inspect_registry_mappings(registry, Path(folder))
            self.assertTrue(any("outside.js" in x for x in failures))
            self.assertTrue(any("no test_paths" in x for x in failures))

    def test_exactly_160_unique_contracts_with_canonical_owner(self):
        owners = parse_contract_owners(CONTRACTS.read_text(encoding="utf-8"))
        self.assertEqual(set(owners), set(range(1, 161)))
        for number in range(1, 161):
            with self.subTest(task=number):
                self.assertEqual(owners[number], expected_owner(number))

    def test_detects_wrong_first_owner_even_when_support_is_correct(self):
        owners = parse_contract_owners("| 31 | DB policy | 13 플랫폼 (11팀 지원) |\n")
        self.assertNotEqual(owners[31], expected_owner(31))

    def test_duplicate_contract_is_rejected(self):
        with self.assertRaisesRegex(AssertionError, "duplicate contract"):
            parse_contract_owners("| 31 | a | 11팀 |\n| 31 | b | 11팀 |\n")

    def test_missing_owner_is_rejected(self):
        with self.assertRaisesRegex(AssertionError, "missing team owner"):
            parse_contract_owners("| 31 | a | 담당 미정 |\n")

if __name__ == "__main__":
    unittest.main()
