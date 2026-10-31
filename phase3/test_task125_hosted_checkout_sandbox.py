"""#125 isolated hosted checkout handoff: no card storage or live payment."""
import unittest

from team14_hosted_checkout_sandbox import (
    preview_hosted_checkout, render_checkout_review_html,
)

URL = "https://checkout.sandbox.example.invalid/session/cs_test_abcdef12"


def make(**changes):
    values = dict(
        session_url=URL,
        booking_id="book_125",
        trusted_booking_id="book_125",
        authenticated_actor_id="learner_125",
        trusted_learner_id="learner_125",
        booking_evidence_verified=True,
        sandbox_enabled=True,
        request_fields={},
    )
    values.update(changes)
    return preview_hosted_checkout(**values)


class Task125HostedCheckoutTests(unittest.TestCase):
    def test_valid_mock_session_is_review_only(self):
        v = make()
        self.assertEqual("SANDBOX_REVIEW_ONLY", v["status"])
        for flag in ("card_data_collected", "card_data_stored",
                     "redirect_enabled", "real_payment_enabled",
                     "real_payout_enabled", "operating_db_connected"):
            self.assertIs(v[flag], False)

    def test_rejects_card_number_and_cvv(self):
        for field in ("card_number", "pan", "cvv", "cvc", "expiry",
                      "payment_method_data", "track_data", "CARD_NUMBER"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                make(request_fields={field: "4111111111111111"})

    def test_rejects_any_untrusted_request_field(self):
        with self.assertRaises(ValueError):
            make(request_fields={"redirect_url": URL})

    def test_requires_explicit_empty_request_fields(self):
        for fields in (None, [], "{}", 0):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                make(request_fields=fields)

    def test_rejects_non_sandbox_or_lookalike_hosts(self):
        urls = (
            "https://checkout.example.com/session/cs_test_abcdef12",
            "https://checkout.sandbox.example.invalid.evil.com/session/cs_test_abcdef12",
            "https://checkout.sandbox.example.invalid./session/cs_test_abcdef12",
            "https://evil@checkout.sandbox.example.invalid/session/cs_test_abcdef12",
            "https://checkout.sandbox.example.invalid:443/session/cs_test_abcdef12",
            "http://checkout.sandbox.example.invalid/session/cs_test_abcdef12",
            "//checkout.sandbox.example.invalid/session/cs_test_abcdef12",
        )
        for url in urls:
            with self.subTest(url=url), self.assertRaises(ValueError):
                make(session_url=url)

    def test_rejects_query_fragment_and_other_paths(self):
        for url in (
            URL + "?redirect=https://evil.example",
            URL + "#secret",
            URL + "/../pay",
            URL.replace("/session/", "/admin/"),
            URL.replace("cs_test_", "cs_live_"),
            URL + "%2f",
            URL + "\\evil",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                make(session_url=url)

    def test_rejects_invalid_url_types_and_controls(self):
        for url in (None, 4, "", URL + "\n", URL + "\t", "é" + URL, "a" * 300):
            with self.subTest(url=url), self.assertRaises(ValueError):
                make(session_url=url)

    def test_booking_id_mismatch_rejected(self):
        with self.assertRaises(PermissionError):
            make(booking_id="other_booking")

    def test_actor_not_learner_rejected(self):
        with self.assertRaises(PermissionError):
            make(authenticated_actor_id="other_user")

    def test_invalid_ids_rejected(self):
        for field in ("booking_id", "trusted_booking_id",
                      "authenticated_actor_id", "trusted_learner_id"):
            for invalid in ("", "../bad", "x" * 65, None, True):
                with self.subTest(field=field, invalid=invalid), self.assertRaises(ValueError):
                    make(**{field: invalid})

    def test_requires_verified_booking_evidence(self):
        for invalid in (False, 0, None, "true"):
            with self.subTest(value=invalid), self.assertRaises(PermissionError):
                make(booking_evidence_verified=invalid)

    def test_requires_strict_sandbox_flag(self):
        for invalid in (False, 1, None, "true"):
            with self.subTest(value=invalid), self.assertRaises(PermissionError):
                make(sandbox_enabled=invalid)

    def test_review_html_contains_no_session_token(self):
        v = make()
        rendered = render_checkout_review_html(v)
        self.assertIn("격리 결제 화면", rendered)
        self.assertNotIn("cs_test_abcdef12", rendered)
        self.assertNotIn("<form", rendered)
        self.assertNotIn("<input", rendered)
        self.assertNotIn("<a ", rendered)
        self.assertIn("Content-Security-Policy", rendered)

    def test_review_rejects_activated_payment(self):
        for flag in ("redirect_enabled", "real_payment_enabled",
                     "card_data_stored", "card_data_collected",
                     "real_payout_enabled", "operating_db_connected"):
            v = make()
            v[flag] = True
            with self.subTest(flag=flag), self.assertRaises(ValueError):
                render_checkout_review_html(v)

    def test_review_rejects_forged_host(self):
        v = make()
        v["provider_host"] = "evil.example"
        with self.assertRaises(ValueError):
            render_checkout_review_html(v)

    def test_review_rejects_forged_session_url(self):
        v = make()
        v["hosted_checkout_url"] = "https://evil.example/session/cs_test_abcdef12"
        with self.assertRaises(ValueError):
            render_checkout_review_html(v)

    def test_review_rejects_forged_booking_id(self):
        v = make()
        v["booking_id"] = "<script>"
        with self.assertRaises(ValueError):
            render_checkout_review_html(v)

    def test_review_requires_exact_safe_state(self):
        v = make()
        v["status"] = "LIVE_PAYMENT"
        with self.assertRaises(ValueError):
            render_checkout_review_html(v)


if __name__ == "__main__":
    unittest.main()
