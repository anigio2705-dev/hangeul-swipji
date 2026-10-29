"""Independent guard: 160 markdown contract owners match the six HQ allocations.

This only verifies ownership metadata; it never promotes READY, CODE_VERIFIED,
test99 deployment, AI development calls, or representative approval.
Run: python -m unittest automation/test_hq_contract_owner_consistency.py -v
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "docs/HQ_160_DEVELOPMENT_CONTRACTS_20261029.md"

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
        owner = re.search(r"\b(11|12|13|14|15|16)\b", cell)
        if not owner:
            raise AssertionError(f"missing team owner #{number}: {cell!r}")
        found[number] = int(owner.group(1))
    return found

class ContractOwnerConsistency(unittest.TestCase):
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
