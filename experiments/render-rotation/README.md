# Render rotation dry-run (isolated proposal)

Status: EXPERIMENT ONLY. No Render service created, no API calls, no GitHub workflow enabled, no production code changed.

## Aim
Validate a 4-minute handoff rotation C→D→A→B without touching existing 160-task A READY, B QA, C automation, or live website.

## Proposed schedule (UTC or local timezone to be explicitly configured)
minute 00 C; 04 D; 08 A; 12 B; 16 C; 20 D; 24 A; 28 B; 32 C; 36 D; 40 A; 44 B; 48 C; 52 D; 56 A; next hour 00 B, 04 C ...

Important: 4-minute intervals create a 16-minute cycle, but 60 is not divisible by 16. Do NOT reset at each hour, or the rotation will collide. Use a persistent cycle counter and a monotonic due timestamp (or a 16-minute schedule with state), not independent hourly cron entries.

## Dry run
1. Deploy a separate Render background worker or always-on service only after account/plan verification and owner approval of cost. Do not modify existing Render website/test service.
2. Run a no-API simulation with durable SQLite on a persistent disk (or external durable store) and UTC timestamps. Emit team, planned_at, actual_at, duration_ms, sequence, status.
3. Prevent duplicate ticks across restarts with unique sequence id and exclusive lease; record missed ticks; no catch-up flood.
4. Observe at least 64 minutes (four complete cycles) and restart once. Measure lateness, skipped ticks and any overlap.
5. Only then consider isolated API calls with explicit per-day spend cap and separate credential; Render hosting does not replace OpenAI API charges.

## Safety
No secrets in repo; no API calls in phase 1; no main merge; no auto deployment; no product writes; no payment; no Render service creation from this document. Owner review required before costs.
