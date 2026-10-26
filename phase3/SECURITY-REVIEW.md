# Phase 3 independent security review

Review date: 2026-10-26 (Asia/Seoul). Scope: new local Python/SQLite test server only. No production database writes, money movement, penetration test of the deployed site, or proof of Supabase RLS execution is claimed.

## Adversarial checks executed

`python -m unittest -v test_security` — **6 tests passed** (HTTP-level tests on an ephemeral localhost port and a temporary SQLite database).

- Registration cannot self-assign admin; client profile updates cannot elevate role or approval; non-admin approval requests are rejected.
- An unrelated user cannot pay, join, complete, write homework, give feedback, or dispute another booking. Unrelated users see no foreign booking records.
- Completion and settlement before required class verification are rejected.
- Foreign-Origin state changes and foreign Host requests are rejected. Source files, SQL, configuration, environment files, and path-traversal attempts are not served.
- Adult-consent and password-length guards reject missing/incorrect inputs. This tests a consent declaration, **not identity or age verification**.
- Duplicate test charges do not duplicate ledger entries. Repeated refund decisions are rejected; a test refund creates an opposite immutable entry. SQL update/delete of ledger and audit are rejected by triggers.
- The same slot cannot be booked twice. Public teacher listings contain neither email nor password hash. Learner unit responses omit the teacher guide.

Each test creates separate accounts and records in a disposable local database. No seeded records are presented as genuine customers or completed education services.

## Findings corrected during review

The initial implementation did not snapshot teaching content or rate policy per booking, included refunded lesson ratings, and did not expose an actual appeal or rescheduling flow. The backend implementation subsequently added immutable unit/rate snapshots, excluded refunded ratings, an appeal endpoint, and participant-consented rescheduling. Source inspection confirmed those changes; their wider state-transition coverage belongs to `test_server.py` and final integration checks.

Attendance credit initially included the early/late room-entry allowance. It now clamps credited seconds to the booked interval. Independent participant counters and administrator evidence remain required. Browser heartbeats are not proof that a person attended a Jitsi session.

## Production blockers retained

- The server binds localhost and uses Python's development HTTP server. Do not expose it publicly. Production needs TLS, secure cookies, reverse-proxy hardening, request timeouts, bounded concurrency, per-account/per-IP signup/login protection, monitoring, and recovery procedures.
- Local password accounts are not production Supabase Auth integration. Email ownership, identity/age verification, guardians, teacher credential validation, sanctions, and authorized administrative provisioning need separate implementation and verification.
- Jitsi public test rooms do not have platform-bound participant authorization. Provider-side events/signatures, room access control, and measured overlapping attendance must be validated before commercial use.
- Database triggers protect application writes but not an operating-system/database owner. Production audit records need separate write-limited archival, access monitoring, and backups.
- Test ledger reversals do not constitute lawful recovery of earned instructor pay. No live payout/referral/payment endpoints are available. Legal, payment-provider, and security approvals remain prerequisites.
- Proposed Supabase SQL is a separate, unapplied design. Passing SQLite tests does not validate PostgreSQL permissions, RLS, concurrency, or deployment.
- Six adversarial tests are focused regression evidence, not an exhaustive security certification.
