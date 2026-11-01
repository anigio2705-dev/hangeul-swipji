"""B/15 independent exact-product-SHA adversarial checks for original #121.

Target product SHA: ca9d427de0588e3298f53b824076338feecb22d5
This file is B-only QA; it does not select a provider or authorize money.
"""
import copy
import sqlite3
import socket
import unittest
from unittest.mock import patch

from team14_provider_candidate_comparison import compare_provider_candidates


BASE = dict(merchant_country="KR", merchant_entity="company",
            charge_currency="KRW", recipient_country="US",
            payout_currency="USD", recipient_type="individual")


def compare(**overrides):
    args = dict(BASE)
    args.update(overrides)
    return compare_provider_candidates(**args)


class IndependentTask121AdversarialQA(unittest.TestCase):
    def assert_closed(self, response):
        self.assertEqual(response["task"], 121)
        self.assertEqual(response["status"], "CANDIDATE_COMPARISON_ONLY")
        self.assertIsNone(response["selection"])
        self.assertIs(response["external_due_diligence_required"], True)
        for key in ("real_money_enabled", "legal_tax_approval",
                    "operating_db_connected", "provider_api_called"):
            self.assertIs(response[key], False, key)
        self.assertEqual(len(response["candidates"]), 3)
        for row in response["candidates"]:
            for key in ("merchant_eligibility_verified",
                        "recipient_eligibility_verified",
                        "country_currency_coverage_verified",
                        "provider_contract_signed", "can_charge",
                        "can_payout", "ready_for_production"):
                self.assertIs(row[key], False, (row["provider_id"], key))
            self.assertIn("VERIFY_LEGAL_TAX_AND_REPRESENTATIVE_APPROVAL",
                          row["unverified_gates"])
            self.assertIn("VERIFY_RECIPIENT_KYC_KYB_TAX_AND_BANK_OR_WALLET_SCHEMA",
                          row["unverified_gates"])

    def test_01_korean_company_us_individual_not_eligible_by_default(self):
        result = compare()
        self.assert_closed(result)
        self.assertEqual(result["request"]["merchant_country"], "KR")
        self.assertEqual(result["request"]["recipient_country"], "US")
        self.assertTrue(result["request"]["cross_border"])
        self.assertTrue(result["request"]["currency_conversion_to_review"])

    def test_02_all_candidates_distinct_and_no_provider_selected(self):
        result = compare()
        self.assertEqual({r["provider_id"] for r in result["candidates"]},
                         {"stripe_connect", "adyen_marketplaces",
                          "airwallex_connected"})
        self.assert_closed(result)

    def test_03_general_capabilities_never_imply_country_eligibility(self):
        for merchant in ("KR", "US", "JP", "ZZ"):
            for recipient in ("KR", "US", "ZZ"):
                with self.subTest(merchant=merchant, recipient=recipient):
                    result = compare(merchant_country=merchant,
                                     recipient_country=recipient)
                    self.assert_closed(result)
                    self.assertTrue(all(r["unverified_gates"]
                                        for r in result["candidates"]))

    def test_04_unsupported_checkout_is_a_gap_not_a_payment_permission(self):
        result = compare(required_capabilities=("hosted_checkout",))
        air = next(r for r in result["candidates"]
                   if r["provider_id"] == "airwallex_connected")
        self.assertEqual(air["capability_gaps_to_investigate"],
                         ["hosted_checkout"])
        self.assertEqual(air["comparison_priority"], "REVIEW_WITH_GAPS")
        self.assert_closed(result)

    def test_05_full_general_match_still_cannot_charge_or_payout(self):
        result = compare(required_capabilities=("marketplace_split",))
        self.assertTrue(all(r["comparison_priority"] == "REVIEW_FIRST"
                            for r in result["candidates"]))
        self.assert_closed(result)

    def test_06_cross_border_gate_independent_of_currency(self):
        result = compare(charge_currency="USD", payout_currency="USD")
        self.assertTrue(result["request"]["cross_border"])
        self.assertFalse(result["request"]["currency_conversion_to_review"])
        for r in result["candidates"]:
            self.assertIn("VERIFY_CROSS_BORDER_RESTRICTIONS",
                          r["unverified_gates"])
            self.assertNotIn("VERIFY_FX_RATE_AND_CONVERSION_COST",
                             r["unverified_gates"])
        self.assert_closed(result)

    def test_07_fx_gate_independent_of_border(self):
        result = compare(recipient_country="KR", payout_currency="USD")
        self.assertFalse(result["request"]["cross_border"])
        self.assertTrue(result["request"]["currency_conversion_to_review"])
        for r in result["candidates"]:
            self.assertIn("VERIFY_FX_RATE_AND_CONVERSION_COST",
                          r["unverified_gates"])
            self.assertNotIn("VERIFY_CROSS_BORDER_RESTRICTIONS",
                             r["unverified_gates"])
        self.assert_closed(result)

    def test_08_domestic_same_currency_still_requires_all_approvals(self):
        result = compare(recipient_country="KR", payout_currency="KRW")
        self.assert_closed(result)
        self.assertFalse(result["request"]["cross_border"])
        self.assertFalse(result["request"]["currency_conversion_to_review"])

    def test_09_invalid_country_and_currency_rejected_closed(self):
        for field, bad in (
            ("merchant_country", ["kr", "KOR", "K", "KR\\n", "../KR", "", None, 1, True]),
            ("recipient_country", ["us", "USA", "U", "US\\n", "", None, False]),
            ("charge_currency", ["krw", "KR", "KRWW", "USD\\n", "", None, 1]),
            ("payout_currency", ["usd", "US", "USDD", "USD\\n", "", None, True]),
        ):
            for value in bad:
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ValueError):
                        compare(**{field: value})

    def test_10_business_form_and_recipient_type_are_not_free_text(self):
        for field, bad in (
            ("merchant_entity", ["individual", "Company", "bank", "", None, True, 1]),
            ("recipient_type", ["company", "bank", "person", "", None, True, 1]),
        ):
            for value in bad:
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ValueError):
                        compare(**{field: value})

    def test_11_all_allowed_entity_recipient_combinations_stay_unverified(self):
        for entity in ("sole_proprietor", "company", "nonprofit"):
            for recipient in ("individual", "business"):
                with self.subTest(entity=entity, recipient=recipient):
                    self.assert_closed(compare(merchant_entity=entity,
                                               recipient_type=recipient))

    def test_12_empty_unknown_duplicate_and_nonstring_capabilities_fail(self):
        for caps in ([], (), "", "hosted_checkout", None, {},
                     ["unknown"], ["hosted_checkout", "hosted_checkout"],
                     ["hosted_checkout", True], [None], [0]):
            with self.subTest(caps=caps):
                with self.assertRaises(ValueError):
                    compare(required_capabilities=caps)

    def test_13_capability_input_order_does_not_change_decision(self):
        a = compare(required_capabilities=["marketplace_split",
                                           "cross_border_payout"])
        b = compare(required_capabilities=("cross_border_payout",
                                           "marketplace_split"))
        self.assertEqual(a, b)
        self.assert_closed(a)

    def test_14_mutating_one_response_cannot_poison_next_comparison(self):
        first = compare()
        original = copy.deepcopy(first)
        first["candidates"][0]["can_payout"] = True
        first["candidates"][0]["unverified_gates"].clear()
        first["request"]["merchant_country"] = "XX"
        self.assertEqual(compare(), original)
        self.assert_closed(compare())

    def test_15_caller_capability_list_not_modified(self):
        caps = ["marketplace_split", "hosted_checkout"]
        original = copy.deepcopy(caps)
        result = compare(required_capabilities=caps)
        self.assertEqual(caps, original)
        self.assertEqual(result["request"]["required_capabilities"],
                         sorted(original))
        self.assert_closed(result)

    def test_16_sensitive_fields_and_approval_spoofing_rejected(self):
        for key in ("bank_account", "tax_id", "identity_document",
                    "provider_approved", "kyc_passed", "live_payment",
                    "api_key", "recipient_email", "webhook_secret"):
            with self.subTest(key=key):
                with self.assertRaises(TypeError):
                    compare(**{key: "forged"})

    def test_17_no_external_network_or_sqlite_connection(self):
        with patch.object(socket, "create_connection",
                          side_effect=AssertionError("network called")), \
             patch.object(sqlite3, "connect",
                          side_effect=AssertionError("db called")):
            result = compare()
        self.assert_closed(result)

    def test_18_official_links_are_research_only_and_https(self):
        result = compare()
        for row in result["candidates"]:
            self.assertGreaterEqual(len(row["official_docs"]), 1)
            self.assertTrue(all(url.startswith("https://")
                                for url in row["official_docs"]))
            self.assertIn("VERIFY_PROVIDER_CONTRACT_FEES_REFUNDS_AND_RECONCILIATION",
                          row["unverified_gates"])
        self.assert_closed(result)


if __name__ == "__main__":
    unittest.main()
