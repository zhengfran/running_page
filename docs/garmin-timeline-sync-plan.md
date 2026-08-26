# Garmin Timeline Sync Plan

## Goal

Mirror Garmin Activities of every type, and Sleep, onto two private Timeline Calendars as Timeline Events carrying real start and end times. The Timeline is a retrospective life-log, independent of the public running history and sharing only the Garmin credentials.

## Invariants

- No Timeline data is written to any repository. The Timeline Calendars are the sole store, and the only state (ADR 0006).
- Timeline Event identity is deterministic and derived from Garmin's own record identity, so every run is idempotent.
- Routes, coordinates, and `locationName` never leave the mapper. The calendar layer accepts only an allowlisted record.
- Sleep is rewritten from Garmin on every run inside the Sync Window; Activities are written once and never rewritten (ADR 0008).
- Naps are out of scope: Garmin reports a daily nap total with no timing, so a nap has no span to record.
- The publication pipeline is untouched. `garmin_publication.yml`, `garmin_publish.py`, and `GarminPublicationClient` are not modified (ADR 0007).
- The two workflows never contend for a Garmin login. Garmin rate-limits authentication per account, with soft-bans measured in days.

## Layout

```text
run_page/garmin_timeline_client.py    Garmin reads: activities, sleep
run_page/timeline_calendar_client.py  Google writes: insert / 409 / patch
run_page/garmin_timeline_sync.py      mapper, allowlist, CLI entry
.github/workflows/garmin_timeline_sync.yml
```

A new Garmin client rather than a generalized `GarminPublicationClient`: that class guards the archive-first invariant of ADR 0002, and widening it to serve the Timeline would put sleep-fetching code inside the thing protecting the archive.

## Pipeline

```text
resolve window -> fetch activities -> fetch sleep (per day)
               -> map to Timeline Events (allowlist)
               -> insert; on 409 patch
               -> canary check
```

Retry-safe at every stage. A failure part-way leaves already-written Timeline Events correct, and the next run reconciles the rest.

## Timeline Event identity

| Kind | Id | Example |
| --- | --- | --- |
| Activity | `a` + `activityId` | `a12345678901` |
| Sleep | `b` + `calendarDate` as `YYYYMMDD` | `b20260825` |

Google requires base32hex — `a`–`v` and `0`–`9` only, length 5–1024, unique per calendar — and rejects a non-conforming id with `400 Invalid resource id value` rather than coercing it. The tag letter is the namespace.

Sleep is keyed on `calendarDate`, never on its start timestamp: an id derived from a revisable field would create a duplicate Event the moment Garmin adjusted the boundary.

## Write semantics

Both kinds attempt `events.insert` with the deterministic id and branch on `409 duplicate`. Neither path needs a prior `get`, because patching `status` is idempotent.

- **Activity** — on 409, `patch` with `{status: "confirmed"}` only. Content is never rewritten; a tombstone is revived; a live Event is untouched.
- **Sleep** — on 409, `patch` with the full field set plus `{status: "confirmed"}`.

All calls set `sendUpdates=none`. `patch`, never `update`: `update` is a full PUT that silently clobbers a hand-made edit.

A Timeline Event deleted by hand inside the Sync Window is restored on the next run; past the window it is never revisited and the deletion stands.

## Field mapping

Times come from Garmin's `*GMT` fields throughout. The `*Local` fields are double-offset for CN and UTC+8 accounts, and Timeline Events carry the UTC instant with no timezone override.

**Activity → Workouts calendar**

| Part | Source |
| --- | --- |
| title | composed, e.g. `Running · 10.2 km`, from `activityType.typeKey` and `distance` |
| start | `startTimeGMT` |
| end | start + `elapsedDuration` |
| description | `distance`, `elapsedDuration`, `movingDuration`, `averageHR`, `maxHR`, `calories`, `elevationGain` |

`elapsedDuration` sets the end, not `movingDuration`: a calendar block means time occupied, and `movingDuration` would under-report a run with long pauses. Both stay in the description.

**Sleep → Sleep calendar**

| Part | Source |
| --- | --- |
| title | `Sleep · <score>` from `sleepScores.overall.value` |
| start | `dailySleepDTO.sleepStartTimestampGMT` (epoch ms) |
| end | `dailySleepDTO.sleepEndTimestampGMT` (epoch ms) |
| description | `sleepTimeSeconds`, `deepSleepSeconds`, `lightSleepSeconds`, `remSleepSeconds`, `awakeSleepSeconds`, `sleepScores.overall.value` and `.qualifierKey`, `avgSleepHRV`, `avgSpO2`, `avgRespirationValue` |

**Exclusion is an allowlist, not a filter.** The mapper reads only the field names above into a typed record, and the calendar client accepts only that record. The raw Garmin response never reaches the calendar layer, so a field added by a future Garmin release cannot leak by default.

## Workflow

- Schedule `01:00 UTC`, which is 09:00 Singapore. An hour clear of `garmin_publication.yml` at `00:00 UTC`, so the two jobs never contend for a Garmin login.
- `workflow_dispatch` exposes a `days` input. The script takes `--days`, defaulting to `7`.
- The one-time backfill is a dispatch with `days: 30`. Importing more history later is the same dispatch with a larger number, and needs no code change. There is no first-run versus steady-state distinction.
- Secrets: `GARMIN_TOKENS_JSON`, `GARMIN_EMAIL`, `GARMIN_PASSWORD`, `GOOGLE_SERVICE_ACCOUNT_JSON`, `GCAL_WORKOUTS_CALENDAR_ID`, `GCAL_SLEEP_CALENDAR_ID`.

The schedule barely affects correctness. Running shortly after waking will sometimes catch sleep that Garmin has not finished finalising, and that is fine: the record is rewritten on each of the next six days, because the window self-heals. What the clock does matter for is login contention, which is why the two jobs are kept apart.

## Failure

- The job fails loudly when the Sync Window yields **zero Sleep records**. Sleep happens nightly, so zero is definitionally a bug and never a valid state — a free canary against a silent parse failure after a Garmin API change.
- The most recent day in the window is excluded from that canary: it may legitimately have no Sleep record yet when the job runs.
- Everything else relies on GitHub Actions' own failure email. No separate monitoring service.

## Test strategy

Unit tests only. CI never touches live Google or live Garmin.

- **Mapper**, against synthetic Garmin responses — the highest-value target, because it is where the allowlist is enforced. Assert positively that excluded fields (`locationName`, coordinates, polylines) never appear in a mapped record, including when the synthetic input contains them.
- **Id derivation**, including base32hex conformance and the Activity/Sleep namespace separation.
- **Write semantics**, against a stub calendar client: insert succeeds; insert raising `409` falls through to `patch`; an Activity patch carries only `status`; a Sleep patch carries content plus `status`.
- **Canary**, that zero Sleep records in the window fails and that a missing most-recent day does not.

Live behaviour was verified once during provisioning, not in CI: tombstone revival, the 409 on re-insert, and that a no-op patch does not alter the Event's `updated` timestamp.

## Rollout

1. Implement and unit-test with the daily schedule absent from the workflow.
2. Dispatch once with `days: 3` and inspect both Timeline Calendars by hand.
3. Dispatch once with `days: 30` for the backfill.
4. Re-dispatch with `days: 30` and confirm nothing duplicates — the idempotency proof.
5. Enable the `01:00 UTC` schedule.

## Release Gate

- Both Timeline Calendars contain Events with correct start and end instants, spot-checked against Garmin Connect.
- Every Activity type present in the window appears, not Runs alone.
- No Timeline Event description contains a location name, coordinate, or route.
- A repeated backfill creates no duplicates.
- No file under `run_page/`, `src/`, `public/`, or the private archive has gained Timeline data.
- `garmin_publication.yml` and its outputs are byte-for-byte unaffected.
