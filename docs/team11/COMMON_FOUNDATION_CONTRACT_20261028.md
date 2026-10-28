# Team 11 — common foundation contract (draft)

Status: isolated proposal, NOT a migration or approved public API. Base: integration/phase2-phase3-20261027, 2026-10-28. Do not merge without HQ review.

## Existing implementation and boundaries
- phase3/server.py: isolated Python HTTP test backend, SQLite, users, bookings, mock money, learning; not production.
- phase3/instant_matching.py: opt-in isolated queue and match with learner/partner roles; preserve without rewriting.
- phase3/test_staging.py: disposable DB HTTP boundary tests.
- GLOBAL_MASTER_PLAN.md and DEVELOPMENT_STATUS.md report free 350 units/1758 quizzes/600 readings, professional 96 lessons; reports do not substitute for full runtime verification.
- Legacy users.role is single-valued; this proposal does not silently reinterpret or migrate it.
- Legacy free-browser progress, staging SQLite, and historical Supabase assets are not one verified permanent identity store.

## Proposed entities (not yet created in database)
users(id PK opaque, auth_subject unique, created_at)
user_roles(user_id FK, role, status, unique(user_id,role))
teaching_profiles(id PK, user_id FK, kind enum conversation_partner|professional_teacher, approval_state, qualification_evidence_ref nullable)
learning_progress(id PK, user_id FK, content_id, content_version, completed_at, unique(user_id,content_id,content_version))
bookings(id PK, learner_id FK, teaching_profile_id FK, slot_id FK, status, currency, quoted_minor)
lessons(id PK, booking_id FK unique, attendance_state, feedback_ref)
transactions(id PK, booking_id FK, provider_reference unique nullable, currency, amount_minor, state, idempotency_key unique)
refunds(id PK, transaction_id FK, amount_minor, reason_code, state, idempotency_key unique)
referral_edges(id PK, referrer_user_id FK, referred_user_id FK, created_at, UNIQUE(referred_user_id), CHECK(referrer_user_id <> referred_user_id))
referral_events(id PK, edge_id FK, transaction_id FK nullable, event_type, state, policy_version nullable)
ledger_entries(id PK, transaction_id FK nullable, referral_event_id FK nullable, amount_minor signed, currency, entry_type, idempotency_key unique)

Do not encode payout rates, depths, or reward entitlement in the schema. For multilevel traversal use cycle detection, max depth as policy parameter, and immutable event snapshots. No recruitment-only payout.

## Proposed API v1 (not implemented routes)
GET /api/v1/me => account + role memberships (only self).
POST /api/v1/teaching-profiles => authenticated owner; review pending by default.
GET /api/v1/learning-progress => only self; teacher access requires scoped lesson permission.
POST /api/v1/bookings => authenticated learner; transactional slot check, UTC time, immutable quote.
POST /api/v1/transactions/mock => isolated test only, idempotency key required.
POST /api/v1/refunds/requests => owner or authorized operator; never auto-pay.
GET /api/v1/referrals/me => own edges/events; no unrelated identities.
All writes require server-side authentication, ownership, strict input validation, audit events, and consistent conflict codes (401 unauthenticated, 403 forbidden, 409 conflict). These routes are design contracts, not deployed endpoints.

## Ownership and dependency
Team11 owns phase3/common_contract.py, phase3/test_common_contract.py and docs/team11/**. Team12 owns educational content/progress UI; Team13 owns matching, booking, video runtime; Team14 owns pricing/payment/referral policy and financial execution; Team15 owns end-to-end QA, operations and release gates. Shared phase3/server.py, schema.sql, staging_server.py, root docs, and CI config require HQ-mediated serial integration. Do not alter another team's files or deploy.

## DB choices (decision pending)
A: disposable SQLite test DB: minimal cost, easy offline tests, NOT durable multi-instance production.
B: managed PostgreSQL: recurring provider cost, backups/PITR and RLS depend on chosen tier; better concurrency, migration required.
C: managed Supabase PostgreSQL: Auth/RLS/storage integration, project-specific pricing/quotas and backups must be verified.
Before migration: inventory existing data, create anonymized snapshot, verify restore on separate environment, version schema migrations, dry-run rollback, reconcile row counts and money ledgers. Never touch operational DB without approval.

## Self-Refine / Kill Critic gates
Prevent duplicate roles, self-referrals, privilege escalation through self-approval, accidental exposure of teacher-only materials, cross-user progress access, double booking, duplicated charge/refund, refund over original capture, referral cycles, payout without eligible completed transaction, and learning score affecting referral entitlement. Unit tests only cover pure validators; integration/security/migration tests remain outstanding.

## Pending HQ decisions
Canonical identity and auth migration; whether legacy role remains compatibility view; partner/teacher verification policy; approved database vendor/budget/backup RPO-RTO; data retention and privacy jurisdictions; referral legal review, depth, payout trigger and rates; cross-team schema change window. No production deployment or migration authorized.
