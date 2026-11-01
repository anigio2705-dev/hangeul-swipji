"""Original task #140 A regression: monthly growth cost/margin with no live money."""
import copy
import unittest

from team14_growth_unit_economics import compare_growth_economics


def assumptions():
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


def calculate(cases=None, rates=None):
    return compare_growth_economics(
        assumptions=assumptions() if rates is None else rates,
        scenarios=[{"learners": 10, "teachers": 2}] if cases is None else cases)


class GrowthEconomicsTests(unittest.TestCase):
    def assert_isolated(self, result):
        self.assertEqual(140, result["task"])
        self.assertEqual("HYPOTHETICAL_REVIEW_ONLY", result["status"])
        self.assertEqual("ASSUMPTION_UNITS", result["currency"])
        for k in ("provider_quotes_verified", "pricing_policy_approved",
                  "real_money_enabled", "operating_db_connected",
                  "external_api_called", "deployment_approved"):
            self.assertIs(result[k], False, k)

    def test_explicit_monthly_arithmetic(self):
        r = calculate()
        row = r["scenarios"][0]
        self.assertEqual("20.0", row["completed_lessons"])
        self.assertEqual("600.0", row["video_minutes"])
        self.assertEqual("24", row["storage_gb"])
        self.assertEqual("40.0", row["notification_messages"])
        self.assertEqual("112.00", row["server_cost"])
        self.assertEqual("60.00", row["video_cost"])
        self.assertEqual("12.00", row["storage_cost"])
        self.assertEqual("10.00", row["notification_cost"])
        self.assertEqual("194.00", row["total_cost"])
        self.assertEqual("200.00", row["platform_revenue"])
        self.assertEqual("6.00", row["platform_profit_loss"])
        self.assertEqual("6.50", row["contribution_per_completed_lesson"])
        self.assertEqual(20, row["break_even_completed_lessons"])
        self.assert_isolated(r)

    def test_growth_scenarios_increase_volume_and_cost(self):
        rows = calculate([{"learners": 0, "teachers": 0},
                          {"learners": 10, "teachers": 2},
                          {"learners": 100, "teachers": 10}])["scenarios"]
        self.assertEqual(["0.0", "20.0", "200.0"],
                         [r["completed_lessons"] for r in rows])
        self.assertTrue(all(float(rows[i]["total_cost"]) <
                            float(rows[i+1]["total_cost"]) for i in range(2)))

    def test_zero_users_fixed_server_cost(self):
        r = calculate([{"learners": 0, "teachers": 0}])["scenarios"][0]
        self.assertEqual("100.00", r["total_cost"])
        self.assertEqual("-100.00", r["platform_profit_loss"])
        self.assertEqual(16, r["break_even_completed_lessons"])

    def test_no_revenue_never_claims_break_even(self):
        a = assumptions()
        a["platform_revenue_per_completed_lesson"] = "0"
        row = calculate(rates=a)["scenarios"][0]
        self.assertIsNone(row["break_even_completed_lessons"])
        self.assertLess(float(row["platform_profit_loss"]), 0)

    def test_zero_fixed_zero_contribution_break_even_zero(self):
        a = {k: "0" for k in assumptions()}
        row = calculate([{"learners": 0, "teachers": 0}], a)["scenarios"][0]
        self.assertEqual(0, row["break_even_completed_lessons"])
        self.assertEqual("0.00", row["total_cost"])

    def test_breakeven_ceiling_not_rounding_down(self):
        a = assumptions()
        a["fixed_server_monthly"] = "1"
        a["server_per_active_user_monthly"] = "0"
        a["storage_per_gb_monthly"] = "0"
        a["video_per_minute"] = "0"
        a["notification_per_message"] = "0"
        a["platform_revenue_per_completed_lesson"] = "0.30"
        row = calculate([{"learners": 0, "teachers": 0}], a)["scenarios"][0]
        self.assertEqual(4, row["break_even_completed_lessons"])

    def test_completion_rate_zero_no_variable_cost(self):
        a = assumptions()
        a["completion_rate"] = "0"
        row = calculate(rates=a)["scenarios"][0]
        self.assertEqual("0", row["completed_lessons"])
        self.assertEqual("0.00", row["video_cost"])
        self.assertEqual("0.00", row["notification_cost"])
        self.assertEqual("124.00", row["total_cost"])

    def test_completion_rate_one_all_lessons(self):
        a = assumptions()
        a["completion_rate"] = "1"
        row = calculate(rates=a)["scenarios"][0]
        self.assertEqual("40", row["completed_lessons"])

    def test_reject_float_bool_negative_nan_infinity(self):
        for bad in (0.1, True, -1, "-0.01", "NaN", "Infinity", "1e1000", None):
            with self.subTest(bad=bad):
                a = assumptions()
                a["video_per_minute"] = bad
                with self.assertRaises(ValueError):
                    calculate(rates=a)

    def test_reject_rate_over_one(self):
        a = assumptions()
        a["completion_rate"] = "1.000001"
        with self.assertRaises(ValueError):
            calculate(rates=a)

    def test_reject_unknown_missing_assumptions(self):
        a = assumptions()
        del a["video_per_minute"]
        with self.assertRaises(ValueError):
            calculate(rates=a)
        a = assumptions()
        a["approved_real_money"] = True
        with self.assertRaises(ValueError):
            calculate(rates=a)

    def test_reject_invalid_counts_and_unknown_scenario(self):
        for bad in (-1, 1.2, True, "10", None, 1000001):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                calculate([{"learners": bad, "teachers": 0}])
        with self.assertRaises(ValueError):
            calculate([{"learners": 1, "teachers": 0, "live_payout": True}])

    def test_reject_missing_or_oversized_scenarios(self):
        for bad in ([], [{}], "text", None, [1], [{"learners": 1}], 
                    [{"learners": 0, "teachers": 0}] * 31):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                calculate(bad)

    def test_no_mutation_deterministic(self):
        a = assumptions()
        cases = [{"learners": 10, "teachers": 2}]
        before_a, before_c = copy.deepcopy(a), copy.deepcopy(cases)
        self.assertEqual(calculate(cases, a), calculate(cases, a))
        self.assertEqual(before_a, a)
        self.assertEqual(before_c, cases)

    def test_precision_half_up_currency_only(self):
        a = assumptions()
        a["fixed_server_monthly"] = "0.005"
        a["server_per_active_user_monthly"] = "0"
        a["storage_per_gb_monthly"] = "0"
        a["video_per_minute"] = "0"
        a["notification_per_message"] = "0"
        row = calculate([{"learners": 0, "teachers": 0}], a)["scenarios"][0]
        self.assertEqual("0.01", row["server_cost"])
        self.assertEqual("0.01", row["total_cost"])

    def test_scenario_order_is_preserved(self):
        cases = [{"learners": 100, "teachers": 5},
                 {"learners": 1, "teachers": 1}]
        rows = calculate(cases)["scenarios"]
        self.assertEqual([100, 1], [x["learners"] for x in rows])


if __name__ == "__main__":
    unittest.main()
