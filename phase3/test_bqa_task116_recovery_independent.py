"""B/15 QA-only #116 exact product SHA cbe2830d0d920737af010de470fe369f8242ff4d.

No live recovery, payout, legal cap, payment or operating DB authorization.
"""
import json
import pathlib
import unittest
from html.parser import HTMLParser
from team14_paid_referral_recovery_review import review_paid_referral_recovery


def review(**overrides):
    args = dict(gross_krw=100,
                allocations={"teacher": 60, "platform": 20,
                             "referral": 15, "benefit": 5},
                referral_weights=(3, 2, 1),
                refunds=(("full_refund", 100),),
                already_paid_referral_krw=12,
                available_balance_fixture_krw=3,
                future_settlement_fixture_krw=4,
                recovery_cap_fixture_krw=None)
    args.update(overrides)
    return review_paid_referral_recovery(**args)


class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


class BQA116RecoveryIndependent(unittest.TestCase):
    def assert_no_real_recovery(self, result):
        for key in ("automatic_clawback", "policy_approved",
                    "legal_recovery_approved", "real_money",
                    "payout_authorized", "operating_db_connected",
                    "recovery_cap_verified"):
            self.assertIs(result[key], False, key)
        for key in ("approved_recovery_krw", "actual_balance_debited_krw",
                    "actual_future_settlement_offset_krw",
                    "actual_recovered_krw"):
            self.assertEqual(result[key], 0, key)
        self.assertIs(result["simulation_only"], True)
        self.assertEqual([a["kind"] for a in result["alternatives"]],
                         ["existing_balance_review", "future_settlement_review",
                          "manual_recovery_limit_review"])
        self.assertTrue(all(a["illustrative_krw"] >= 0
                            for a in result["alternatives"]))
        self.assertTrue(all(a.get("actual_offset_krw",
                                  a.get("actual_recovered_krw")) == 0
                            for a in result["alternatives"]))

    def test_full_refund_has_three_nonbinding_options(self):
        x = review()
        self.assertEqual(x["potential_exposure_krw"], 12)
        self.assertEqual([a["illustrative_krw"] for a in x["alternatives"]],
                         [3, 4, 5])
        self.assertEqual(x["recommended_state"], "MANUAL_REVIEW_REQUIRED")
        self.assert_no_real_recovery(x)

    def test_zero_refund_and_zero_paid_both_no_action(self):
        for changes in ({"refunds": ()},
                        {"already_paid_referral_krw": 0}):
            with self.subTest(changes=changes):
                x = review(**changes)
                self.assertEqual(x["potential_exposure_krw"], 0)
                self.assertEqual(x["recommended_state"], "NO_ACTION")
                self.assertEqual(sum(a["illustrative_krw"]
                                     for a in x["alternatives"]), 0)
                self.assert_no_real_recovery(x)

    def test_fixture_cap_matrix_never_becomes_approved_cap(self):
        for cap in (0, 1, 5, 12, 100, None):
            with self.subTest(cap=cap):
                x = review(recovery_cap_fixture_krw=cap)
                ceiling = min(12, cap) if cap is not None else 12
                self.assertEqual(x["illustrative_recovery_ceiling_krw"], ceiling)
                self.assertEqual(x["not_in_illustrative_scope_krw"],
                                 12 - ceiling)
                self.assertEqual(sum(a["illustrative_krw"]
                                     for a in x["alternatives"]), ceiling)
                self.assert_no_real_recovery(x)

    def test_zero_balance_future_and_large_balance_partition(self):
        for balance, future in ((0, 0), (0, 12), (12, 0),
                                (1000, 1000), (1, 2), (2, 1)):
            with self.subTest(balance=balance, future=future):
                x = review(available_balance_fixture_krw=balance,
                           future_settlement_fixture_krw=future)
                amounts = [a["illustrative_krw"] for a in x["alternatives"]]
                self.assertEqual(sum(amounts), 12)
                self.assertLessEqual(amounts[0], balance)
                self.assertLessEqual(amounts[1], future)
                self.assert_no_real_recovery(x)

    def test_partial_refund_exposure_cannot_exceed_paid_amount(self):
        for refund in (1, 2, 10, 50, 99):
            with self.subTest(refund=refund):
                x = review(refunds=(("partial_refund", refund),))
                self.assertGreaterEqual(x["potential_exposure_krw"], 0)
                self.assertLessEqual(x["potential_exposure_krw"], 12)
                self.assert_no_real_recovery(x)

    def test_full_amount_cannot_be_mislabeled_partial_refund(self):
        with self.assertRaisesRegex(ValueError, "partial refund must leave"):
            review(refunds=(("partial_refund", 100),))

    def test_odd_krw_three_then_one_then_three_refund_regression(self):
        x = review(gross_krw=7,
                   allocations={"teacher": 0, "platform": 1,
                                "referral": 3, "benefit": 3},
                   referral_weights=(1, 1, 1),
                   refunds=(("partial_refund", 3),
                            ("partial_refund", 1),
                            ("full_refund", 3)),
                   already_paid_referral_krw=3,
                   available_balance_fixture_krw=1,
                   future_settlement_fixture_krw=1)
        self.assertEqual(x["potential_exposure_krw"], 3)
        self.assertEqual([a["illustrative_krw"] for a in x["alternatives"]],
                         [1, 1, 1])
        self.assert_no_real_recovery(x)

    def test_invalid_balance_future_cap_fixtures_fail_closed(self):
        bad = (-1, True, False, 1.5, "2", [], {}, 10**12 + 1)
        for field in ("available_balance_fixture_krw",
                      "future_settlement_fixture_krw",
                      "recovery_cap_fixture_krw"):
            for value in bad:
                with self.subTest(field=field, value=repr(value)):
                    with self.assertRaises(ValueError):
                        review(**{field: value})

    def test_referral_overpayment_and_over_refund_rejected(self):
        with self.assertRaises(ValueError):
            review(already_paid_referral_krw=16)
        with self.assertRaises(ValueError):
            review(refunds=(("partial_refund", 101),))
        with self.assertRaises(ValueError):
            review(refunds=(("partial_refund", 80),
                            ("partial_refund", 21)))

    def test_fixture_input_not_modified_and_json_safe(self):
        allocations = {"teacher": 60, "platform": 20,
                       "referral": 15, "benefit": 5}
        original = dict(allocations)
        x = review(allocations=allocations)
        self.assertEqual(allocations, original)
        self.assertEqual(json.loads(json.dumps(x)), x)
        self.assert_no_real_recovery(x)

    def test_output_mutation_cannot_poison_next_call(self):
        first = review()
        first["alternatives"][0]["illustrative_krw"] = 9999
        first["alternatives"].append({"kind": "forged"})
        second = review()
        self.assertEqual(len(second["alternatives"]), 3)
        self.assertEqual(second["alternatives"][0]["illustrative_krw"], 3)
        self.assert_no_real_recovery(second)

    def test_static_ui_three_disabled_actions_and_no_active_controls(self):
        html = pathlib.Path(__file__).with_name(
            "paid-referral-recovery-review.html").read_text(encoding="utf-8")
        parser = Tags()
        parser.feed(html)
        buttons = [a for tag, a in parser.tags if tag == "button"]
        self.assertEqual(len(buttons), 3)
        self.assertTrue(all("disabled" in b for b in buttons))
        self.assertFalse({"form", "script", "input", "iframe", "object",
                          "embed", "a", "img", "link"}.intersection(
                              tag for tag, _ in parser.tags))
        self.assertIn("회수", html)
        self.assertIn("정산", html)

    def test_ui_csp_blocks_scripts_forms_and_default_fetch(self):
        html = pathlib.Path(__file__).with_name(
            "paid-referral-recovery-review.html").read_text(encoding="utf-8")
        parser = Tags()
        parser.feed(html)
        policies = [a["content"] for tag, a in parser.tags if tag == "meta"
                    and a.get("http-equiv", "").lower() ==
                    "content-security-policy"]
        self.assertEqual(len(policies), 1)
        self.assertIn("default-src 'none'", policies[0])
        self.assertIn("form-action 'none'", policies[0])
        self.assertNotIn("onclick=", html.lower())


if __name__ == "__main__":
    unittest.main()
