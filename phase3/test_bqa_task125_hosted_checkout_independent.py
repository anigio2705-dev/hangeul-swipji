"""B/15 independent exact-SHA QA for product #125 at
cacfd435a14efc71eefcd67d929619cabf6437ae.
Offline mock-only tests: no payment, network, credentials or real DB.
"""
import unittest
from unittest.mock import patch

from team14_hosted_checkout_sandbox import (
    preview_hosted_checkout, render_checkout_review_html,
)

HOST = "checkout.sandbox.example.invalid"
URL = "https://" + HOST + "/session/cs_test_abcdef12"


def review(**changes):
    args = dict(session_url=URL, booking_id="booking_125",
                trusted_booking_id="booking_125",
                authenticated_actor_id="learner_125",
                trusted_learner_id="learner_125",
                booking_evidence_verified=True, sandbox_enabled=True,
                request_fields={})
    args.update(changes)
    return preview_hosted_checkout(**args)


class IndependentHostedCheckoutSafetyTests(unittest.TestCase):
    def test_01_mock_positive_never_activates_payment(self):
        obj = review()
        self.assertEqual(obj["status"], "SANDBOX_REVIEW_ONLY")
        for key in ("card_data_collected", "card_data_stored",
                    "redirect_enabled", "real_payment_enabled",
                    "real_payout_enabled", "operating_db_connected"):
            self.assertIs(obj[key], False)

    def test_02_empty_query_delimiter_is_still_a_query_component(self):
        # urlsplit(url + '?').query == '', but the raw URL has a query marker.
        with self.assertRaises(ValueError):
            review(session_url=URL + "?")

    def test_03_empty_fragment_delimiter_is_still_a_fragment_component(self):
        # urlsplit(url + '#').fragment == '', but the raw URL has a fragment marker.
        with self.assertRaises(ValueError):
            review(session_url=URL + "#")

    def test_04_multiple_empty_delimiters_must_not_bypass_allowlist(self):
        for candidate in (URL + "?#", URL + "#?", URL + "??", URL + "##"):
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                review(session_url=candidate)

    def test_05_userinfo_port_and_host_aliases_rejected(self):
        for candidate in (
            "https://u@" + HOST + "/session/cs_test_abcdef12",
            "https://" + HOST + ":443/session/cs_test_abcdef12",
            "https://" + HOST + "./session/cs_test_abcdef12",
            "https://" + HOST + ".evil.invalid/session/cs_test_abcdef12",
            "https://" + HOST.upper() + "/session/cs_test_abcdef12",
        ):
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                review(session_url=candidate)

    def test_06_cross_booking_and_actor_denied(self):
        for change in ({"trusted_booking_id": "other"},
                       {"trusted_learner_id": "other"}):
            with self.subTest(change=change), self.assertRaises(PermissionError):
                review(**change)

    def test_07_truthy_fake_evidence_and_sandbox_denied(self):
        for key in ("booking_evidence_verified", "sandbox_enabled"):
            for bad in (1, "true", [], None):
                with self.subTest(key=key, bad=bad), self.assertRaises(PermissionError):
                    review(**{key: bad})

    def test_08_all_untrusted_payloads_denied(self):
        for bad in ({"PAN": "fake"}, {"payment_method_data": {}},
                    {"return_url": "https://evil.invalid"},
                    {"card_number": "4111111111111111"}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                review(request_fields=bad)

    def test_09_untrusted_identity_types_denied(self):
        for bad in (True, 1, None, "../escape", "a" * 65):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                review(authenticated_actor_id=bad)

    def test_10_review_html_never_exposes_url_or_active_controls(self):
        html = render_checkout_review_html(review())
        self.assertNotIn("cs_test_abcdef12", html)
        self.assertNotIn(URL, html)
        for forbidden in ("<form", "<input", "<a ", "location.href",
                          "<script", "fetch(", "action="):
            if forbidden == "action=":
                self.assertNotIn("<form action=", html)
            else:
                self.assertNotIn(forbidden, html)

    def test_11_preview_tamper_rejected(self):
        for key in ("redirect_enabled", "real_payment_enabled",
                    "real_payout_enabled", "card_data_collected",
                    "card_data_stored", "operating_db_connected"):
            item = review()
            item[key] = True
            with self.subTest(key=key), self.assertRaises(ValueError):
                render_checkout_review_html(item)

    def test_12_no_live_provider_or_actual_network(self):
        with patch("urllib.request.urlopen",
                   side_effect=AssertionError("unexpected network")):
            obj = review()
            self.assertEqual(obj["provider_host"], HOST)
            self.assertNotIn("checkout.stripe.com", str(obj))
            self.assertIn("결제 불가", render_checkout_review_html(obj))


if __name__ == "__main__":
    unittest.main()
