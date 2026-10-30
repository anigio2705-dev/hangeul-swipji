# Supabase / Jitsi integration boundary — 2026-10-26

## What exists

The runnable 3rd-phase pilot uses Python + SQLite locally. It does **not** use Supabase Auth or persist its transactions to Supabase. Existing `speaking-config.js`, `public.profiles`, `public.matches`, the existing Jitsi flow, and all 2nd-phase files remain unchanged. The parent agent inspected the existing project's policies read-only; no production user data was copied into this pilot.

`supabase-preview.sql` is a **design proposal**, not an applied or hosted-database-verified migration. It has an explicit install gate; `hs3` must remain outside the Supabase Data API's exposed schemas. There are no end-user grants and no exposed security-definer functions. Dormant own/participant SELECT policies describe the future access boundary; RLS is not a substitute for grants or server authorization.

## Isolated validation before any integration

1. Create a disposable test project/database, with no production Auth users or copied personal data. Inspect its version, schema, default privileges, extension installation schema, and Data API exposure settings.
2. Enable `btree_gist` in `extensions` within that disposable project. Its UUID GiST operator class is required by the overlap exclusions. This preview assumes `auth.users`, `auth.uid()`, `anon`, and `authenticated` exist as in Supabase; plain PostgreSQL needs test stubs. A later isolated PGlite PostgreSQL test now executes the complete proposal with explicit Auth fixtures; no hosted Supabase application was performed. See AUTH-TESTING.md.
3. Explicitly set `hs3.allow_preview_install` to `isolated-test-only` in that session, then run the preview once inside a disposable database. A second install is intentionally rejected by `create schema hs3` rather than silently accepting a divergent schema.
4. Test anonymous denial, authenticated cross-user denial, own-participant read boundaries using SET ROLE/JWT test fixtures, teacher approval escalation rejection, no browser ledger writes, concurrent learner/provider overlap, slot uniqueness, callback replay, refund races, and settlement idempotency. Run security advisors and inspect all grants and functions.
5. Only after the adapter and tests exist, generate a real migration using the current Supabase CLI workflow; do not rename this preview into a migration or claim it is production ready. The live 2nd-phase project must not be its test target.

## Required server adapter

| Boundary | Required implementation before live use |
|---|---|
| Identity | Verify Supabase JWT signature/issuer/audience/expiry or current verified user using current official SDK/API; reject anonymous identities for paid adult pilot. Map `auth.uid()` to the new `hs3.profiles.user_id`. Do not infer identity from request body. |
| Admin | Server-controlled `app_metadata` plus a current server-side authorization record; never `user_metadata`, self-selected role, or nickname. Require MFA and check revocation/current sessions for sensitive operations. JWT claims can remain stale until refresh. |
| Provider approval | Verified identity/age/safety and qualifications evidence kept separately from public profile. A partner must not be described as a qualified teacher. A test administrator clicking approve is not real identity validation. |
| Database | Use an isolated least-privilege server role. Keep `hs3` private. Expose allowlisted server routes, not direct browser table writes. A service key bypasses RLS: if one is ever used, server authorization must independently constrain every query; never ship it to clients. |
| Catalog | Return approved provider projections without private evidence/contact data. Return learner material separately from teacher guide/answers. Maintain content version and SHA-256. A booked unit snapshot must remain immutable even after catalog edits. |
| Booking | One transaction locks availability, checks approval and future time, validates unit duration and price snapshot, inserts booking and **both** participant claims, and logs the action. Exclusion constraints prevent overlapping active claims but do not create missing claims or verify their equality to booking times; adapter tests must cover this. |
| Completion | Trusted conference-server attendance evidence, required duration, both parties' confirmation, open-dispute gate, manual review where needed. A browser join event or self-attestation is insufficient proof of actual teaching. |
| Payment | Licensed marketplace provider sandbox; server-created intent and signed callback with replay protection, amount/currency/account/mode reconciliation, exactly-once state transition. Browser success messages cannot mark a payment captured. Live wallet, card storage, cash payout, and automatic reward transfers remain absent. |
| Settlement | Lock booking/disputes/payment/refund rows in one transaction; require verified completion, policy cooling-off/review conditions, and no hold. Snapshot agreed integer amounts/rates, preserve earned compensation, separately model conditional incentives. Apply append-only balanced ledger entries and unique event keys. Refunds append reversals; never edit historical entries. |
| Referrals | One immutable direct referrer per referred person, no self-referral/cycles/recruitment fees, rewards only against verified completed, non-refunded paid service. Add no downline or recursive payout. Even a single-level model requires legal classification and provider approval before cash activation. |
| Audit | Server role gets INSERT/SELECT, not UPDATE/DELETE on ledger/audit. Add transaction-level audit coverage for every state change. Store minimal identifiers and evidence references, not raw sensitive IDs or secrets; define retention/access and immutable external backup. DB owner can still alter data; “immutable” cannot mean owner-proof. |
| Disputes | Evidence, accessible reason, investigation, decision, appeal and re-review, ledger hold and compensation protection. Admin cannot resolve a case without a reason; all changes audited. |

The preview schema expresses storage constraints and deny-by-default client access. It does **not** implement the required transaction procedures, append-only server-role grants, signed payment callbacks, reference-proof age checks, migration orchestration, or full legal rules. Those are explicit integration blockers, not silently completed features.

## Jitsi

The local pilot may generate the same random test-room link for both booked participants. Public `meet.jit.si` is an external demonstration facility; a leaked link may permit outsiders, moderator login/availability may vary, and local server attendance cannot prove conference attendance. Do not record video/audio or submit sensitive data in these test rooms.

Production requires an approved authenticated Jitsi deployment (or approved vendor) with server-signed short-lived room-scoped tokens, participant identity binding, room expiry, moderator controls, abuse reporting, confirmed attendance webhooks, and an explicit cross-border processing/retention assessment. Verify vendor terms and data locations. The pilot's random-room link is not a replacement for this security architecture.

## Official documentation checked

- [Supabase changelog](https://supabase.com/changelog.md): read 2026-10-26. Relevant announced change: older TLS 1.2 CBC ciphers are scheduled to be disabled on project HTTP APIs on 2026-11-10; ensure the eventual adapter/runtime supports modern TLS. [Announcement](https://supabase.com/changelog/cbc-tls-ciphers-deprecated).
- [Securing your API](https://supabase.com/docs/guides/api/securing-your-api): grants control object access; RLS controls rows; default grants can expose new objects.
- [Row Level Security](https://supabase.com/docs/guides/database/postgres/row-level-security): retrieved via official MCP documentation search 2026-10-26; `auth.uid()` ownership, authenticated-role limitations, security-invoker views, user-editable metadata risks, and JWT freshness.
- [Custom schemas](https://supabase.com/docs/guides/api/using-custom-schemas): consult when designing a future deliberately exposed API schema; `hs3` is intentionally private in this proposal.

No claim of Supabase deployment, migration success, RLS execution testing, payment-provider integration, or real two-party Jitsi attendance verification is made by these files.


Round2 update: see AUTH-TESTING.md for actual local PostgreSQL/RLS results and the optional isolated Supabase Auth adapter. The hosted development branch request failed; no production mutation occurred. Local SQLite transactions are still the runnable platform storage. These checks do not establish real Supabase Auth/PostgREST integration.
