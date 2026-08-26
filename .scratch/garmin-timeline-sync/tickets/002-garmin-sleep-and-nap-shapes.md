---
id: "002"
title: Garmin sleep and nap data — endpoints, shapes, and nap distinctness
parent: map
labels: [wayfinder:research]
status: closed
assignee: "research-agent"
blocked-by: []
---

## Question

Q17 assumes Garmin exposes naps as records distinguishable from main sleep. Q15 assumes summary metrics are available for event descriptions. Both are unverified.

Against the `python-garminconnect` source and Garmin Connect's API behaviour:

1. Which methods return **sleep** data, and what is the response shape? Identify precisely the fields giving sleep **start and end** as timestamps, and whether they are GMT, local, or both.
2. Are **naps** returned as distinct records, or folded into the daily sleep summary? If distinct, what marks them as naps and what gives their individual start/end times? If not distinct, what is the closest available representation?
3. What **summary metrics** come back for sleep — sleep score, stage durations, resting HR — that could populate a Timeline Event description (Q15)?
4. Does `get_activities` with `activitytype=None` return **all** activity types (Q4)? What summary metrics accompany each activity in the list response, without needing a per-activity detail fetch?
5. Note anything about rate limits or pagination that a 7-day window (Q16) plus a 30-day first-run backfill (Q12) would hit.

Do not assume the library's docstrings are accurate; prefer observed response shapes and the library source.

## Context

Findings will be captured at `.scratch/garmin-timeline-sync/research/002-garmin-sleep-and-nap-shapes.md`.

## Resolution

Findings: `.scratch/garmin-timeline-sync/research/002-garmin-sleep-and-nap-shapes.md` (371 lines, sourced verbatim from `cyberjunky/python-garminconnect` master, v0.3.12).

**Sleep — solid.** `get_sleep_data(cdate)` → `GET /wellness-service/wellness/dailySleepData/{displayName}`, one call per day. `dailySleepDTO` carries `sleepStartTimestampGMT` / `sleepEndTimestampGMT` (and `*Local`) as **epoch milliseconds**, confirmed by a Pydantic model in `typed.py` plus a real test fixture. Use the GMT fields: the library's own docstring warns `*Local` is double-offset for some CN/UTC+8 accounts — directly relevant here. Metrics available: `sleepTimeSeconds`, `deepSleepSeconds`, `lightSleepSeconds`, `remSleepSeconds`, `awakeSleepSeconds`, `avgSleepHRV`, `avgSpO2`, `avgRespirationValue`, and nested `sleepScores`. No resting HR inside sleep data.

**Naps — the design-breaking finding.** Garmin exposes **no per-nap records with individual start/end times** through this library. `dailySleepDTO.napTimeSeconds` is a daily aggregate total only — no count, no array, no timing. There is no `get_naps` method and no nap endpoint among ~150 `get_*` methods. The sole lead is a docstring on `get_body_battery_events(cdate)` claiming its events "can include ... naps" — with **zero field names in source**. Unverifiable without a live account response.

This invalidates the assumption behind Q4 and Q17 that naps could become discrete timed events. See ticket 012 and ticket 006.

**Activities — solid.** `get_activities(start, limit, activitytype=None)` omits the type filter and returns all types, confirmed from source rather than inferred. The list response carries `startTimeLocal`/`startTimeGMT`, `duration`/`movingDuration`/`elapsedDuration`, `distance`, `averageHR`/`maxHR`, `calories` — no per-activity detail fetch needed. Exact timestamp string format unconfirmed.

**Rate limits.** No numeric threshold documented. Aggressive rate limiting is on **login/SSO**, reported per-account, with 48h+ soft-bans — data fetches are comparatively low-risk. This argues for minimising logins, not minimising fetches, which supports the wide Sync Window (Q16). `get_activities_by_date` auto-paginates a date range; sleep has no equivalent, so a 30-day backfill costs 30 calls.

**Incidental correction to the ticket brief:** v0.3.12 has dropped `garth` entirely for a self-contained `client.py`. Also worth knowing for ticket 011 — this repo's `garmin_sync.py` hand-rolls its own `Garmin` class on `garth` + `httpx`; only `garmin_publication_client.py` uses the real library.
