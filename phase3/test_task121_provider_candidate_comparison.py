"""#121 regression: candidate research is not country/provider eligibility."""
import copy
import unittest

from team14_provider_candidate_comparison import compare_provider_candidates


def compare(**overrides):
    request = {
        "merchant_country": "KR",
        "merchant_entity": "company",
        "charge_currency": "KRW",
        "recipient_country": "US",
        "payout_currency": "USD",
        "recipient_type": "individual",
    }
    request.update(overrides)
    return compare_provider_candidates(**request)


class Task121ProviderComparisonTests(unittest.TestCase):
    def assert_never_money(self, result):
        self.assertEqual(121, result["task"])
        self.assertEqual("CANDIDATE_COMPARISON_ONLY", result["status"])
        self.assertIsNone(result["selection"])
        self.assertTrue(result["external_due_diligence_required"])
        for key in ("legal_tax_approval", "real_money_enabled",
                    "operating_db_connected", "provider_api_called"):
            self.assertIs(result[key], False, key)
        for row in result["candidates"]:
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

    def test_three_named_candidates_and_official_sources(self):
        result = compare()
        self.assertEqual({"stripe_connect", "adyen_marketplaces",
                          "airwallex_connected"},
                         {row["provider_id"] for row in result["candidates"]})
        for row in result["candidates"]:
            self.assertEqual(2, len(row["official_docs"]))
            self.assertTrue(all(link.startswith("https://")
                                for link in row["official_docs"]))
        self.assert_never_money(result)

    def test_merchant_and_recipient_country_not_inferred_supported(self):
        for country in ("KR", "US", "JP", "ZZ"):
            with self.subTest(country=country):
                result = compare(merchant_country=country)
                self.assertEqual(country, result["request"]["merchant_country"])
                self.assert_never_money(result)

    def test_cross_border_requires_extra_gate(self):
        result = compare()
        self.assertTrue(result["request"]["cross_border"])
        for row in result["candidates"]:
            self.assertIn("VERIFY_CROSS_BORDER_RESTRICTIONS",
                          row["unverified_gates"])

    def test_domestic_comparison_omits_cross_border_gate(self):
        result = compare(recipient_country="KR", payout_currency="KRW")
        self.assertFalse(result["request"]["cross_border"])
        self.assertFalse(result["request"]["currency_conversion_to_review"])
        for row in result["candidates"]:
            self.assertNotIn("VERIFY_CROSS_BORDER_RESTRICTIONS",
                             row["unverified_gates"])
        self.assert_never_money(result)

    def test_fx_needed_requires_extra_gate(self):
        result = compare()
        self.assertTrue(result["request"]["currency_conversion_to_review"])
        for row in result["candidates"]:
            self.assertIn("VERIFY_FX_RATE_AND_CONVERSION_COST",
                          row["unverified_gates"])

    def test_equal_currency_omits_fx_gate(self):
        result = compare(payout_currency="KRW")
        self.assertFalse(result["request"]["currency_conversion_to_review"])
        for row in result["candidates"]:
            self.assertNotIn("VERIFY_FX_RATE_AND_CONVERSION_COST",
                             row["unverified_gates"])

    def test_provider_capability_gaps_are_not_authorization(self):
        result = compare()
        airwallex = next(x for x in result["candidates"]
                         if x["provider_id"] == "airwallex_connected")
        self.assertIn("hosted_checkout",
                      airwallex["capability_gaps_to_investigate"])
        self.assertEqual("REVIEW_WITH_GAPS", airwallex["comparison_priority"])
        self.assert_never_money(result)

    def test_single_capability_comparison(self):
        result = compare(required_capabilities=("cross_border_payout",))
        self.assertEqual(["cross_border_payout"],
                         result["request"]["required_capabilities"])
        self.assertTrue(all(x["comparison_priority"] == "REVIEW_FIRST"
                            for x in result["candidates"]))
        self.assert_never_money(result)

    def test_requested_capability_order_does_not_change_output(self):
        first = compare(required_capabilities=("hosted_checkout",
                                               "marketplace_split"))
        second = compare(required_capabilities=["marketplace_split",
                                                "hosted_checkout"])
        self.assertEqual(first, second)

    def test_duplicate_capabilities_rejected(self):
        with self.assertRaises(ValueError):
            compare(required_capabilities=["hosted_checkout",
                                           "hosted_checkout"])

    def test_unknown_and_bad_capabilities_rejected(self):
        for value in ([], (), "hosted_checkout", None,
                      ["money"], ["hosted_checkout", True], [None], {}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                compare(required_capabilities=value)

    def test_invalid_country_codes_rejected(self):
        for value in ("kr", "KOR", "K", "../KR", "", True, None, 11):
            with self.subTest(value=value), self.assertRaises(ValueError):
                compare(merchant_country=value)
            with self.subTest(recipient=value), self.assertRaises(ValueError):
                compare(recipient_country=value)

    def test_invalid_currency_codes_rejected(self):
        for value in ("krw", "KR", "KRWW", "USD\n", "", False, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                compare(charge_currency=value)
            with self.subTest(payout=value), self.assertRaises(ValueError):
                compare(payout_currency=value)

    def test_entity_and_recipient_types_rejected(self):
        for value in ("individual", "COMPANY", "bank", "", True, None):
            with self.subTest(entity=value), self.assertRaises(ValueError):
                compare(merchant_entity=value)
        for value in ("company", "bank", "", False, None):
            with self.subTest(recipient=value), self.assertRaises(ValueError):
                compare(recipient_type=value)

    def test_allowed_business_and_recipient_forms(self):
        for entity in ("sole_proprietor", "company", "nonprofit"):
            for recipient in ("individual", "business"):
                with self.subTest(entity=entity, recipient=recipient):
                    result = compare(merchant_entity=entity,
                                     recipient_type=recipient)
                    self.assertEqual(entity, result["request"]["merchant_entity"])
                    self.assertEqual(recipient, result["request"]["recipient_type"])
                    self.assert_never_money(result)

    def test_no_sensitive_account_tax_or_personal_fields_accepted(self):
        for key in ("bank_account", "tax_id", "identity_document",
                    "api_key", "account_number", "provider_approved"):
            with self.subTest(key=key), self.assertRaises(TypeError):
                compare(**{key: "secret"})

    def test_output_is_deterministic_and_independent(self):
        first = compare()
        second = compare()
        self.assertEqual(first, second)
        first["candidates"][0]["unverified_gates"].clear()
        self.assertNotEqual(first, second)
        self.assert_never_money(second)

    def test_request_not_mutated(self):
        capabilities = ["marketplace_split", "hosted_checkout"]
        original = copy.deepcopy(capabilities)
        compare(required_capabilities=capabilities)
        self.assertEqual(original, capabilities)


if __name__ == "__main__":
    unittest.main()
