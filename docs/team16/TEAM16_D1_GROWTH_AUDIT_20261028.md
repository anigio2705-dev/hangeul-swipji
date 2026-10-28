# Team 16 — Initial growth audit / D1 handoff (2026-10-28)
Issue: #22. Branch: team16/global-growth-marketing-20261028. Base: main. **Status: CODE_DONE for isolated draft assets only; not deployed, not CI-passed, not staging-verified.**

## Evidence reviewed
- CEO-approved 6-team/15-day directive at hq/ceo-final-directive-15day-20261028.
- 160-item backlog at docs/platform-execution-backlog-20261027.
- Issue #22.
- main/index.html: meta title/description, learning CTA (hangul-basics.html), speaking CTA (speaking-platform.html), learning/reading/culture directories. Notices explicitly say speaking is in test mode and payments/bookings are preparing.
- main/index.html: no literal gtag, analytics, utm_, or hreflang string detected in the fetched homepage source. This does not prove absence across the entire app.
- 99 live server: external response/browser test not obtained in this session. Latest staging SHA unknown.
- Other teams' research reports: not fully collected; cross-team reconciliation pending.

## Readiness and blockers
Content and a home-to-speaking navigation path exist. Reliable acquisition-to-purchase instrumentation, tested international payments, server persistence, actual two-person call, verified booking/checkout, VN/JP localized end-to-end flows, privacy consent and durable attribution have NOT been proven. Paid ads must remain disabled. No fabricated traffic, CAC or LTV.

## Reusable assets
350 lessons, reading levels, K-content routes, home CTA, speaking-platform entry and existing language framework. Validate each on staging before using as paid campaign destination.

## First five days
D1: inventory pages and event contracts; landing drafts and attribution design. D2: coordinate consent/event capture with team 11 and learning CTA with team 12; test navigation and event assertions. D3: VN/JP content localization review and landing page navigation. D4: connect booking and test-payment confirmation events via teams 13/14; never record a payment from an unauthenticated client click. D5: joint evidence matrix with team 15, including browser network records, deployed SHA and test funnel counts.
Metrics: landing→learning-start→signup→lesson→speaking-CTA→booking→confirmed payment→repeat purchase. Segment by verified campaign/country after permission; never send email, phone, name, full query strings or personal learning records in analytics. Test and live transactions must be separate.

## Cross-team requests
11: server consent/storage/event endpoint, deduplication/attribution, deploy SHA. 12: lesson milestones & language QA. 13: confirmed booking event & CTA integration. 14: server-confirmed transaction events, refunds, margin computations. 15: independent verification and fraud/privacy test. Owner: external marketing accounts, ad spend, local translation/cultural review and live launch authorization only when necessary.

## Deliverables included
- growth/team16/funnel-events.js: strict event names, path sanitization, opt-in local dispatch only; no network calls or persistent tracking until authorized.
- growth/team16/landing-vi.html and landing-ja.html: standalone draft pages, preserved all core site files; noindex until service validation. Links use owned UTM, but no cross-domain attribution guarantee.
These assets are intentionally isolated, not linked into production index.html. Future deployment needs QA, language review and consent implementation.

## Acceptance gate
[ ] Static files inspected by CI or browser (no claim yet)
[ ] VN/JP translator approval
[ ] staging 99 SHA equals intended deployment
[ ] responsive navigation
[ ] privacy consent and server-side event collector approved
[ ] analytics contains one consented event per action, no PII
[ ] booking/payment events backed by authenticated server confirmation
[ ] test and live metrics distinguishable
[ ] team 15 review
[ ] representative launch approval
Backlog mapping: 50, 143-148, 151, 153-160. No item marked DONE without evidence.

## Financial guardrail
At 10,000 KRW normal 25-minute class, platform gross share is 2,500 KRW before processing, refunds, infra, video, support, marketing, tax, and any referral rewards. A CAC of 40 USD is an **unvalidated benchmark**, not affordable acquisition cost. Compute contribution-margin LTV before running paid campaigns.
