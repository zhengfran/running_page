---
id: "012"
title: Inspect a live Garmin account for per-nap timing
parent: map
labels: [wayfinder:task]
status: closed-out-of-scope
assignee: ""
blocked-by: []
---

## Question

Ticket 002 established that `python-garminconnect` exposes **no per-nap records** — only `dailySleepDTO.napTimeSeconds`, a daily aggregate with no timing. The one unexplored lead is `get_body_battery_events(cdate)`, whose docstring claims its events "can include sleep, recorded activities, auto-detected activities, and naps." The library gives no field names, so this can only be settled against a real response.

Nothing to decide here — this is the fact-gathering that unblocks ticket 006.

Do, against the real account:
- Call `get_body_battery_events(cdate)` for a date on which a nap was actually taken (pick a date where `napTimeSeconds > 0` — find one first via `get_sleep_data`).
- Capture the raw response shape. Determine whether individual nap events appear with their own start and end timestamps, what marks an event as a nap versus sleep or an activity, and the timestamp units and timezone.
- Also check `get_sleep_data` for that same date for any nested per-nap structure the Pydantic model in `typed.py` might not cover — the model may be incomplete rather than the API.

**Note on credentials.** `GARMIN_TOKENS_JSON` lives only in GitHub Actions secrets, not on the local machine, so this likely needs either a local `get_garmin_tokens.py` run or a throwaway `workflow_dispatch` job that prints the shape. **Do not commit any captured response** — it is health data, and ADR 0002 / Q3 govern.

Record in the resolution: whether per-nap timing exists, and if so the exact field names. If it does not exist, say so plainly — ticket 006 then has to choose between dropping naps and representing them without timing.

## Closed — out of scope

This ticket existed only to unblock ticket 006, which is now out of scope. The `get_body_battery_events` lead is not worth chasing on its own.
