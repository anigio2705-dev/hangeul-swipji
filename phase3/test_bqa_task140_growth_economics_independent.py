"""B/15 independent QA-only adversarial checks for #140 exact product SHA 7403afae456be96ad53fe3894c9c3f772c22e595.

No product changes. Validate output conservation, financial display integrity,
break-even boundaries, input isolation and permanent non-authorization.
"""
import copy
import unittest
from decimal import Decimal

from team14_growth_unit_economics import compare_growth_economics


def base():
    return {
        "fixed_server_monthly": "100",
        "server_per_active_user_monthly": "1",
        "video_per_minute": "0.10",
        "storage_gb_per_active_user": "2",
        "storage_per_gb_monthly": "0.5",
        "notification_per_message": "0.25",
        "messages_per_completed_lesson": "2",
        "minutes_per_completed_lesson": "30",
        "lessons_per_learner_monthly": "4",
        "completion_rate": "0.5",
        "platform_revenue_per_completed_lesson": "10",
    }


def run(rates=None, cases=None):
    return compare_growth_economics(
        assumptions=base() if rates is None else rates,
        scenarios=[{"learners": 10, "teachers": 2}] if cases is None else cases,
    )


class BIndependentGrowth140(unittest.TestCase):
    def test_reference_case_exact_decimal_accounting(self):
        r = run()["scenarios"][0]
        self.assertEqual(Decimal("20"), Decimal(r["completed_lessons"]))
        self.assertEqual(Decimal("194"), Decimal(r["total_cost"]))
        self.assertEqual(Decimal("200"), Decimal(r["platform_revenue"]))
        self.assertEqual(Decimal("6"), Decimal(r["platform_profit_loss"]))

    def test_cost_components_conserve_at_cent_precision(self):
        r = run()["scenarios"][0]
        parts = sum((Decimal(r[k]) for k in (
            "server_cost", "video_cost", "storage_cost", "notification_cost")), Decimal(0))
        self.assertEqual(parts, Decimal(r["total_cost"]))

    def test_subcent_cost_components_must_match_displayed_total(self):
        a = {k: "0" for k in base()}
        a["fixed_server_monthly"] = "0.005"
        a["video_per_minute"] = "0.005"
        a["minutes_per_completed_lesson"] = "1"
        a["lessons_per_learner_monthly"] = "1"
        a["completion_rate"] = "1"
        r = run(a, [{"learners": 1, "teachers": 0}])["scenarios"][0]
        displayed_sum = sum((Decimal(r[k]) for k in (
            "server_cost", "video_cost", "storage_cost", "notification_cost")), Decimal(0))
        self.assertEqual(displayed_sum, Decimal(r["total_cost"]),
                         "displayed cost components must reconcile with displayed total")

    def test_subcent_profit_must_reconcile_with_displayed_revenue_and_cost(self):
        a = {k: "0" for k in base()}
        a["fixed_server_monthly"] = "0.004"
        a["lessons_per_learner_monthly"] = "1"
        a["completion_rate"] = "1"
        a["platform_revenue_per_completed_lesson"] = "0.005"
        r = run(a, [{"learners": 1, "teachers": 0}])["scenarios"][0]
        self.assertEqual(Decimal(r["platform_revenue"]) - Decimal(r["total_cost"]),
                         Decimal(r["platform_profit_loss"]),
                         "displayed profit must reconcile with displayed revenue and cost")

    def test_only_teacher_growth_increases_fixed_cost_without_revenue(self):
        r = run(cases=[{"learners": 0, "teachers": 0},
                       {"learners": 0, "teachers": 50}])["scenarios"]
        self.assertEqual(Decimal(0), Decimal(r[1]["completed_lessons"]))
        self.assertGreater(Decimal(r[1]["total_cost"]), Decimal(r[0]["total_cost"]))
        self.assertEqual(Decimal(0), Decimal(r[1]["platform_revenue"]))

    def test_completion_zero_does_not_create_video_or_notifications(self):
        a = base()
        a["completion_rate"] = "0"
        r = run(a)["scenarios"][0]
        for key in ("completed_lessons", "video_minutes", "notification_messages",
                    "video_cost", "notification_cost", "platform_revenue"):
            self.assertEqual(Decimal(0), Decimal(r[key]), key)

    def test_completion_one_is_double_half_at_same_learners(self):
        a = base()
        half = Decimal(run(a)["scenarios"][0]["completed_lessons"])
        a["completion_rate"] = "1"
        full = Decimal(run(a)["scenarios"][0]["completed_lessons"])
        self.assertEqual(half * 2, full)

    def test_ceiling_break_even_boundary(self):
        a = {k: "0" for k in base()}
        a["fixed_server_monthly"] = "1"
        a["platform_revenue_per_completed_lesson"] = "0.3"
        self.assertEqual(4, run(a, [{"learners": 0, "teachers": 0}])
                         ["scenarios"][0]["break_even_completed_lessons"])

    def test_negative_contribution_no_break_even(self):
        a = base()
        a["platform_revenue_per_completed_lesson"] = "1"
        self.assertIsNone(run(a)["scenarios"][0]["break_even_completed_lessons"])

    def test_zero_fixed_and_zero_margin_break_even_zero(self):
        a = {k: "0" for k in base()}
        self.assertEqual(0, run(a, [{"learners": 0, "teachers": 0}])
                         ["scenarios"][0]["break_even_completed_lessons"])

    def test_storage_and_server_include_both_user_roles(self):
        a = base()
        rows = run(a, [{"learners": 1, "teachers": 0},
                       {"learners": 1, "teachers": 1}])["scenarios"]
        self.assertEqual(Decimal("2"), Decimal(rows[1]["server_cost"]) -
                         Decimal(rows[0]["server_cost"]))
        self.assertEqual(Decimal("1"), Decimal(rows[1]["storage_cost"]) -
                         Decimal(rows[0]["storage_cost"]))

    def test_reject_nan_infinity_negative_float_and_bool(self):
        for bad in ("NaN", "Infinity", "-Infinity", "-0.01", 0.5, True, None):
            with self.subTest(bad=bad):
                a = base()
                a["video_per_minute"] = bad
                with self.assertRaises(ValueError):
                    run(a)

    def test_reject_completion_above_one(self):
        a = base()
        a["completion_rate"] = "1.0000001"
        with self.assertRaises(ValueError):
            run(a)

    def test_reject_scenario_count_spoofing(self):
        for bad in (True, "10", -1, 1000001, 1.2, None):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                run(cases=[{"learners": bad, "teachers": 0}])

    def test_reject_unknown_assumption_and_scenario_fields(self):
        a = base()
        a["pricing_policy_approved"] = True
        with self.assertRaises(ValueError):
            run(a)
        with self.assertRaises(ValueError):
            run(cases=[{"learners": 1, "teachers": 0, "payout": True}])

    def test_maximum_thirty_cases_and_order(self):
        cases = [{"learners": i, "teachers": 0} for i in range(30)]
        rows = run(cases=cases)["scenarios"]
        self.assertEqual(list(range(30)), [r["learners"] for r in rows])
        with self.assertRaises(ValueError):
            run(cases=cases + [cases[0]])

    def test_inputs_unchanged_and_deterministic(self):
        a, cases = base(), [{"learners": 2, "teachers": 3}]
        before = copy.deepcopy((a, cases))
        self.assertEqual(run(a, cases), run(a, cases))
        self.assertEqual(before, (a, cases))

    def test_never_assert_provider_or_live_money_approval(self):
        result = run()
        self.assertEqual("HYPOTHETICAL_REVIEW_ONLY", result["status"])
        self.assertEqual("ASSUMPTION_UNITS", result["currency"])
        for key in ("provider_quotes_verified", "pricing_policy_approved",
                    "real_money_enabled", "operating_db_connected",
                    "external_api_called", "deployment_approved"):
            self.assertIs(result[key], False, key)


if __name__ == "__main__":
    unittest.main()
