---
id: "007"
title: Lock the Garmin-to-Timeline-Event field mapping
parent: map
labels: [wayfinder:grilling]
status: closed
assignee: "wayfinder-session"
blocked-by: ["002"]
---

## Question

With ticket 002 answered, lock exactly what each Timeline Event carries.

Q15 settled the policy: times, titles, and summary metrics; no routes, no precise location. Turn that into a concrete mapping.

- For an activity: which Garmin fields produce the title, and which metrics the description.
- For sleep: the same. (Naps are out of scope — see the map.)
- The explicit **exclusion list** — every field that must never reach Google, and the mechanism that enforces it rather than relying on the mapping being written carefully once.
- Note that `locationName` is present on Garmin activity metadata and is used by the publication pipeline; Q15 excludes it here.

## Proposal (pre-worked, awaiting confirmation)

Field names below are the confirmed ones from the closed ticket [Garmin sleep and nap data](./002-garmin-sleep-and-nap-shapes.md). Naps are out of scope.

### Activity Timeline Event → Workouts calendar

| Part | Source |
|---|---|
| id | `a` + `activityId` |
| title | `activityName`, falling back to `activityType.typeKey` when absent or generic |
| start | `startTimeGMT`, parsed as UTC |
| **end** | start + **`elapsedDuration`** |
| description | `distance`, `elapsedDuration`, `movingDuration`, `averageHR`, `maxHR`, `calories`, `elevationGain` |

**Why `elapsedDuration` and not `duration` or `movingDuration`**: Q1 wants a record of time *occupied*. `movingDuration` excludes pauses, so a run with a long traffic-light wait would render as a block shorter than the time you were actually out. `elapsedDuration` is the wall-clock span, which is what a calendar block means. Both are kept in the description so the distinction stays visible.

### Sleep Timeline Event → Sleep calendar

| Part | Source |
|---|---|
| id | `b` + `calendarDate` as `YYYYMMDD` |
| title | `Sleep` |
| start | `dailySleepDTO.sleepStartTimestampGMT` (epoch ms) |
| end | `dailySleepDTO.sleepEndTimestampGMT` (epoch ms) |
| description | `sleepTimeSeconds`, `deepSleepSeconds`, `lightSleepSeconds`, `remSleepSeconds`, `awakeSleepSeconds`, `sleepScores.overall.value` and `.qualifierKey`, `avgSleepHRV`, `avgSpO2`, `avgRespirationValue` |

Use the **`*GMT`** fields, never `*Local` — ticket 002 found the library's own docstring warns `*Local` is double-offset for CN/UTC+8 accounts, which is this account. Consistent with Q18 anyway.

### Exclusion enforcement

Q15 asked for a mechanism, not care taken once. The mechanism is an **allowlist**: the mapper reads only the field names listed above, by name, into a typed record, and the Google client accepts **only** that record. The raw Garmin response dict never reaches the calendar layer, so a new field appearing in a future Garmin API version cannot leak by default — it is simply not read.

Named exclusions this enforces: `locationName` (present on activity metadata and used by the publication pipeline; Q15 excludes it here), plus any route, polyline, or coordinate field.

### Needs the user

- `activityName` is frequently just the generic type ("Running", "Cycling"). Accept generic titles, or compose something richer such as `Running · 10.2 km`?
- Should the sleep event title carry the score — `Sleep` versus `Sleep · 84`?

## Resolution

Proposal above confirmed, with Q24 and Q25 settling the titles.

- **Activity title**: composed, not raw `activityName` — `Running · 10.2 km`. Garmin's `activityName` is usually the bare type, which would render a week as "Running / Running / Running"; a life-log scanned at a glance should show which run was the long one without opening it.
- **Sleep title**: carries the score — `Sleep · 84`.
- Everything else as proposed: `elapsedDuration` sets an activity's end (it is the wall-clock span; `movingDuration` would under-report a run with long pauses), `*GMT` fields throughout (`*Local` is double-offset on CN accounts per ticket 002), and the allowlist mapper as the exclusion mechanism.

Full field tables are in the Proposal section above.
