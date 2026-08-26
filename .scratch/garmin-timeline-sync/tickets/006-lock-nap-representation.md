---
id: "006"
title: Lock nap representation and the Sleep-calendar event model
parent: map
labels: [wayfinder:grilling]
status: closed-out-of-scope
assignee: ""
blocked-by: ["002", "012"]
---

## Question

With ticket 002 answered, lock how sleep and naps become Timeline Events.

- Does one night of sleep become one event, or does Garmin's data force something else (split sleep, multiple segments)?
- How naps are represented given what 002 found — distinct events if Garmin distinguishes them, and what the fallback is if it does not.
- The title convention that distinguishes a nap from main sleep visually (Q17 keeps both on one calendar).
- How a sleep event that crosses midnight, or a nap that overlaps an activity, is handled.
- What identifies a sleep record for ID purposes (feeds ticket 005).

## Update from ticket 002

Ticket 002 found Garmin exposes **no per-nap start/end times** — only a daily `napTimeSeconds` aggregate. Q17's "naps titled distinctly on the Sleep calendar" assumed discrete nap events, and that assumption does not hold unless ticket 012 finds timing in `get_body_battery_events`.

If 012 comes back negative, this ticket must choose between:
- **Drop naps entirely.** Q1 wants a life-log of time spans; an aggregate with no timing cannot be one. This would move naps to the map's Out of scope.
- **Represent naps without timing** — e.g. an all-day event or a note appended to that night's sleep event description, recording "napped 45m" without saying when.
- **Derive nap timing from another signal** (body battery curve, activity gaps). Almost certainly not worth it for a personal log; note the cost before choosing it.

The user must make this call — it changes what they asked for.

## Closed — out of scope

Nap capture is dropped from the effort. Ticket 002 established Garmin exposes no per-nap start/end times, only a daily `napTimeSeconds` aggregate. The destination is a calendar of Timeline Events with real start and end times (Q1); an aggregate with no timing cannot be one, and the alternatives — an all-day marker, or a "napped 45m" note on the night's sleep event — record a fact without recording a *span*, which is not what this map is finding its way to.

Not a decision on the route, so this does not appear in the map's Decisions so far. Recorded under Out of scope instead.

Reopening would require redrawing the destination, and would be a fresh effort.
