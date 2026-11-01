"""Regression checks for pinned original-160 clause extraction and fail-closed matching."""
import re
import unittest
import json
import copy
from pathlib import Path

def original_clause(ledger, number, expected_blob, actual_blob):
    if actual_blob != expected_blob:
        raise ValueError("LEDGER_BLOB_SHA_MISMATCH")
    matches = re.findall(r"(?m)^" + str(number) + r"\. \[ \] (.+)$", ledger)
    if len(matches) != 1:
        raise ValueError("TASK_NOT_IN_PINNED_LEDGER")
    return matches[0].strip()

def verify_binding_contract(ledger, binding, expected_blob, actual_blob):
    actual = original_clause(ledger, binding["task_id"], expected_blob, actual_blob)
    if actual != binding["original_contract"]:
        raise ValueError("ORIGINAL_CONTRACT_MISMATCH")
    return True

BLOB = "6590c0f27d87797201f4e7ab2cbe139c08615c29"
LEDGER = ("123. [ ] 결제 성공·실패·취소·시간 초과 시 예약과 잔여 수업 상태를 맞춘다.\n"
          "140. [ ] 회원·수업 증가에 따른 서버·화상·저장·알림 비용과 손익을 계산한다.\n")

class PinnedContractRegexTests(unittest.TestCase):
    def test_140_valid(self):
        self.assertEqual(original_clause(LEDGER, 140, BLOB, BLOB),
                         "회원·수업 증가에 따른 서버·화상·저장·알림 비용과 손익을 계산한다.")
    def test_123_valid(self):
        self.assertEqual(original_clause(LEDGER, 123, BLOB, BLOB),
                         "결제 성공·실패·취소·시간 초과 시 예약과 잔여 수업 상태를 맞춘다.")
    def test_modified_clause_rejected(self):
        binding_path = Path(__file__).with_name("task_pr_bindings.json")
        data = json.loads(binding_path.read_text(encoding="utf-8"))
        original = next(x for x in data["bindings"] if x["task_id"] == 140)
        self.assertEqual(original_clause(LEDGER, 140, BLOB, BLOB), original["original_contract"])
        tampered = copy.deepcopy(data)
        changed = next(x for x in tampered["bindings"] if x["task_id"] == 140)
        changed["original_contract"] = "위조된 계약"
        self.assertNotEqual(original_clause(LEDGER, 140, BLOB, BLOB), changed["original_contract"])
        with self.assertRaisesRegex(ValueError, "ORIGINAL_CONTRACT_MISMATCH"):
            verify_binding_contract(LEDGER, changed, BLOB, BLOB)
    def test_duplicate_task_number_rejected(self):
        with self.assertRaisesRegex(ValueError, "TASK_NOT_IN_PINNED_LEDGER"):
            original_clause(LEDGER + LEDGER.splitlines()[1] + "\n", 140, BLOB, BLOB)
    def test_blob_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "LEDGER_BLOB_SHA_MISMATCH"):
            original_clause(LEDGER, 140, BLOB, "wrong")

if __name__ == "__main__":
    unittest.main()
