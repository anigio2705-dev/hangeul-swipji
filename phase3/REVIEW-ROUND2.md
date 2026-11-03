# Independent Kill Critic review — round 2

Scope: isolated phase3 code at `568b6a9`; no production DB or main edits. Reviewed actual HTTP authorization, booking/referral/payment/completion transitions and existing tests rather than repeating previously passed assertions.

## New reproduced defects

|Defect|Reproduction|Required behavior|
|---|---|---|
|No simultaneous conversation requirement|On a 60-minute slot, provider attends first30min and learner attends last30min, with no overlapping attendance. Each confirms; administrator enters evidence. Baseline changes status to completed.|Evidence must not override insufficient shared attendance. Block completion/settlement when measured overlapping time is inadequate. Browser heartbeats still cannot prove actual Jitsi media attendance.|
|Payment after an unpaid booking has ended|Create reserved booking, advance test clock beyond slot end, then POST pay-test. Baseline inserts a test charge.|Reject expired/past reservation before any charge and free abandoned unpaid holds under an explicit test policy.|
|Mutable direct referrer for initially unassigned user|User signs up without referral, books with referrerA, cancels, books with referrerB. Baseline accepts both and stores two direct referrers across bookings.|Bind the first accepted direct referrer atomically to the referred person, or explicitly use another legally reviewed attribution policy. Do not claim an immutable personal referrer while allowing transaction switching.|

`python -m unittest discover -s phase3 -p test_regressions.py -v` reproduced **3 failures** against baseline. These are expected regression failures before root fixes; they are not a completed validation result.

## Additional hardening observations

- Login attempts are currently keyed only by IP and cleared on any successful login. Eleven failed target-account guesses followed by a valid attacker-owned login can reset the limit. Add account+IP failure quotas and an aggregate IP quota that a different account cannot clear.
- Keep private teacher-guide authorization deliberate: the catalog strips guides for learners but permits self-selected teacher/partner roles to retrieve guides before provider approval. This may be an intentional teacher-recruitment preview; if guides are restricted professional material, approval/entitlement must also be checked. No restriction was assumed or silently added by this review.
- A provider approval withdrawal is not an account-suspension mechanism. Existing paid bookings can still be accessed; a separate suspension and earned-compensation/dispute policy is needed before production.
- Existing browser heartbeat plus manual administrator evidence is a local simulation boundary. It is not trusted conference-server attendance, identity verification, or educational service proof. Real PG/Jitsi/Supabase integration remains independently verifiable work.

Final regression status must be updated after the implementation changes and re-run. Never count these initial failures as passing tests.


Root correction: the3 initially failing regressions now pass after shared-interval intersection, unpaid hold expiration/late-charge guard, and first-booking direct-referrer binding. Per-account plus aggregate IP login quotas were also added and tested against cross-account reset. The independent baseline failures are retained above as evidence, not current failing status.
