---
id: "008"
title: Lock how the one-time 30-day backfill is triggered
parent: map
labels: [wayfinder:grilling]
status: closed
assignee: "wayfinder-session"
blocked-by: []
---

## Question

Q12 settled that the first run backfills 30 days and steady-state runs cover 7 (Q16). Nothing yet says how the job knows which it is — and Q9 forbids persisted state, so it cannot simply remember.

- How is the wide run triggered? A `workflow_dispatch` input carrying a window size is the obvious candidate, and it doubles as the escape hatch for importing more history later.
- Is the window a parameter with a default, rather than a first-run/steady-state distinction at all?
- What makes the wide run safe to re-run — deterministic IDs (Q9) should make it free, but confirm against ticket 003's findings on re-insert.
- What schedule the steady-state workflow runs on, given Q14 noted 00:00 UTC is too early for finalised sleep.

## Proposal (pre-worked, awaiting confirmation)

**There is no first-run/steady-state distinction.** The Sync Window is simply a parameter with a default — which is also the escape hatch Q12 asked for.

- The script takes `--days`, defaulting to **7** (Q16).
- The workflow's `schedule` trigger passes nothing, so scheduled runs use 7.
- `workflow_dispatch` exposes a `days` input, default 7. The one-time 30-day backfill is a dispatch with `days: 30`. Importing more history later is the same dispatch with a bigger number — no code change.
- **Safe to re-run by construction**: insert → 409 → patch is idempotent per the closed ticket [Lock the deterministic event ID scheme](./005-lock-event-id-scheme.md), so a wide run costs only API calls and can be repeated freely.

### Schedule

Worth noting that the schedule time barely affects correctness: with a 7-day window and last-sync-wins on sleep (Q10), a run that catches unfinalised sleep is corrected on each of the next six days. The window self-heals; the clock is an operational choice, not a correctness one.

So pick for tidiness — **14:00 UTC (22:00 Beijing)**. Well clear of `garmin_publication.yml` at 00:00 UTC, so the two jobs never contend for a Garmin login, which matters given ticket 002 found Garmin rate-limits *login* per-account with 48h+ soft-bans.

### Needs the user

- Confirm 14:00 UTC, or name a different hour.

## Resolution

Proposal above confirmed (Q23).

- **No first-run/steady-state distinction exists.** The Sync Window is a `--days` parameter defaulting to 7; scheduled runs pass nothing, `workflow_dispatch` exposes a `days` input. The one-time 30-day backfill is a dispatch with `days: 30`, and that same dispatch is the escape hatch Q12 asked for — importing more history later needs no code change.
- **Schedule: 14:00 UTC** (22:00 Beijing). Chosen for operational tidiness rather than correctness: the 7-day window with last-sync-wins self-heals, so a run catching unfinalised sleep is corrected on each of the next six days. What matters is staying clear of `garmin_publication.yml` at 00:00 UTC, because ticket 002 found Garmin rate-limits *login* per-account with 48h+ soft-bans — the two jobs must never contend for one.
