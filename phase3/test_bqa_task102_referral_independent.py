"""B/15 independent adversarial QA for original #102.
Base: exact A product SHA 5adfa82c9d326b749b904261a10ca57f6fa0cb01.
This file tests only; never changes product, money, policy or operating data.
"""
import copy
import unittest
from team14_referral_comparison import compare_referral_options

NO_LIVE = ("identity_verified", "transaction_verified", "policy_approved",
           "legal_tax_approved", "can_create_reward", "can_payout",
           "can_modify_operating_db")

def option(**kwargs):
    x = dict(candidate_id="B_direct", max_depth=1, duration_days=14,
             eligible_events=["LESSON_COMPLETED"])
    x.update(kwargs)
    return x

def context(**kwargs):
    x = dict(referral_chain=["student", "direct", "grandparent"],
             referred_at_utc="2026-10-01T00:00:00Z",
             transaction_at_utc="2026-10-15T00:00:00Z",
             as_of_utc="2026-11-01T00:00:00Z",
             event="LESSON_COMPLETED", refund_pending=False,
             fixture_payment_evidence_present=True)
    x.update(kwargs)
    return x

def run(options=None, scenario=None):
    return compare_referral_options([option()] if options is None else options,
                                    context() if scenario is None else scenario)

class BQA102Independent(unittest.TestCase):
    def assert_no_live(self, r):
        self.assertIs(r["policy_approved"], False)
        self.assertIs(r["can_activate_real_money"], False)
        for row in r["results"]:
            for flag in NO_LIVE:
                self.assertIs(row[flag], False, flag)

    def test_01_direct_only_one_ancestor(self):
        r=run()
        self.assertEqual([1],r["results"][0]["hypothetical_depths"])
        self.assertEqual("DIRECT_ONLY",r["results"][0]["model"])
        self.assert_no_live(r)

    def test_02_multilevel_two_ancestors_but_no_more(self):
        r=run([option(max_depth=10)])
        self.assertEqual([1,2],r["results"][0]["hypothetical_depths"])
        self.assertEqual("MULTILEVEL",r["results"][0]["model"])
        self.assert_no_live(r)

    def test_03_ten_ancestors_bounded_by_depth(self):
        chain=["s"]+["r"+str(i) for i in range(10)]
        r=run([option(max_depth=10)],context(referral_chain=chain))
        self.assertEqual(list(range(1,11)),r["results"][0]["hypothetical_depths"])

    def test_04_comparison_does_not_select_or_authorize_policy(self):
        opts=[option(candidate_id="one",max_depth=1),
              option(candidate_id="two",max_depth=2),
              option(candidate_id="three",max_depth=10)]
        r=run(opts)
        self.assertEqual([1,2,2],[x["hypothetical_referrer_count"] for x in r["results"]])
        self.assert_no_live(r)

    def test_05_boundary_inclusive_exact_day(self):
        self.assertEqual("COMPARE_ONLY",run()["results"][0]["review_status"])

    def test_06_microsecond_after_expiry_denied(self):
        x=run(scenario=context(transaction_at_utc="2026-10-15T00:00:00.000001Z"))
        self.assertEqual([] ,x["results"][0]["hypothetical_depths"])
        self.assertIn("CANDIDATE_PERIOD_EXPIRED",x["results"][0]["review_reasons"])

    def test_07_zero_day_exact_same_instant_only(self):
        x=run([option(duration_days=0)],context(transaction_at_utc="2026-10-01T00:00:00Z"))
        self.assertEqual([1],x["results"][0]["hypothetical_depths"])
        y=run([option(duration_days=0)],context(transaction_at_utc="2026-10-01T00:00:00.000001Z"))
        self.assertEqual([],y["results"][0]["hypothetical_depths"])

    def test_08_refund_pending_blocks_hypothetical_matches(self):
        x=run(scenario=context(refund_pending=True))
        self.assertEqual(0,x["results"][0]["hypothetical_referrer_count"])
        self.assertIn("REFUND_PENDING",x["results"][0]["review_reasons"])
        self.assert_no_live(x)

    def test_09_missing_fixture_evidence_blocks_matches(self):
        x=run(scenario=context(fixture_payment_evidence_present=False))
        self.assertEqual("BLOCKED_FIXTURE",x["results"][0]["review_status"])
        self.assertEqual([],x["results"][0]["hypothetical_depths"])

    def test_10_event_mismatch_blocks_all_ancestors(self):
        x=run([option(eligible_events=["BOOKING_PAID"])])
        self.assertEqual(0,x["results"][0]["hypothetical_referrer_count"])
        self.assertIn("EVENT_NOT_IN_CANDIDATE",x["results"][0]["review_reasons"])

    def test_11_multiple_fail_reasons_sorted_and_no_live(self):
        x=run([option(duration_days=0,eligible_events=["MONTH_RENEWED"])],
              context(refund_pending=True,fixture_payment_evidence_present=False))
        row=x["results"][0]
        self.assertEqual(sorted(row["review_reasons"]),row["review_reasons"])
        self.assertEqual(4,len(row["review_reasons"]))
        self.assert_no_live(x)

    def test_12_invalid_chain_and_cycle_rejected(self):
        for chain in (["s"],["s","s"],["s","a","s"],["s","../x"],["s",False]):
            with self.subTest(chain=chain),self.assertRaises(ValueError):
                run(scenario=context(referral_chain=chain))

    def test_13_invalid_candidate_ids_or_duplicate_rejected(self):
        for opts in ([option(candidate_id="")],[option(candidate_id="../evil")],
                     [option(),option()]):
            with self.subTest(opts=opts),self.assertRaises(ValueError):
                run(opts)

    def test_14_numeric_bool_float_out_of_range_rejected(self):
        for bad in (dict(max_depth=True),dict(max_depth=0),dict(max_depth=11),
                    dict(duration_days=False),dict(duration_days=-1),
                    dict(duration_days=3651),dict(duration_days=1.5)):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                run([option(**bad)])

    def test_15_event_duplicates_unknown_types_rejected(self):
        for ev in ([],["LESSON_COMPLETED"]*2,["OTHER"],[None],
                   ["LESSON_COMPLETED",True],"LESSON_COMPLETED"):
            with self.subTest(ev=ev),self.assertRaises(ValueError):
                run([option(eligible_events=ev)])

    def test_16_timestamp_bad_calendar_offset_precision_rejected(self):
        for stamp in ("2026-02-30T00:00:00Z","2026-10-15T09:00:00+09:00",
                      "2026-10-15T00:00:00.1234567Z","2026-10-15",
                      "2026-10-15T23:59:60Z"):
            with self.subTest(stamp=stamp),self.assertRaises(ValueError):
                run(scenario=context(transaction_at_utc=stamp))

    def test_17_chronology_future_event_or_prior_referral_rejected(self):
        for kw in (dict(transaction_at_utc="2026-09-30T23:59:59Z"),
                   dict(as_of_utc="2026-10-14T23:59:59Z"),
                   dict(referred_at_utc="2026-10-16T00:00:00Z")):
            with self.subTest(kw=kw),self.assertRaises(ValueError):
                run(scenario=context(**kw))

    def test_18_boolean_spoofing_and_schema_extra_rejected(self):
        for kw in (dict(refund_pending=0),
                   dict(fixture_payment_evidence_present="true"),
                   dict(password="secret")):
            with self.subTest(kw=kw),self.assertRaises(ValueError):
                run(scenario=context(**kw))
        with self.assertRaises(ValueError):
            run([option(secret="bad")])

    def test_19_empty_none_oversized_rejected(self):
        for options in (None,[],[option(candidate_id=str(i)) for i in range(17)]):
            with self.subTest(options=options),self.assertRaises(ValueError):
                compare_referral_options(options,context())
        with self.assertRaises(ValueError):
            run(scenario=context(referral_chain=[str(i) for i in range(12)]))

    def test_20_input_immutable_and_identity_not_echoed(self):
        opts=[option(candidate_id="p",eligible_events=["LESSON_COMPLETED"])]
        sc=context(referral_chain=["private_student","private_referrer"])
        before=copy.deepcopy((opts,sc))
        x=run(opts,sc)
        self.assertEqual((opts,sc),before)
        self.assertNotIn("private_student",str(x))
        self.assertNotIn("private_referrer",str(x))
        self.assert_no_live(x)

    def test_21_year_9999_overflow_fails_closed_with_validation_error(self):
        # Even syntactically valid UTC must not leak an unhandled OverflowError
        # when the bounded candidate duration exceeds datetime's representable max.
        sc=context(referred_at_utc="9999-12-30T00:00:00Z",
                   transaction_at_utc="9999-12-30T00:00:00Z",
                   as_of_utc="9999-12-30T00:00:00Z")
        with self.assertRaises(ValueError):
            run([option(duration_days=3650)],sc)

if __name__=="__main__":
    unittest.main()
