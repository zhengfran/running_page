---
labels: [wayfinder:map]
tracker: local-markdown
tickets: ./tickets/
---

# Garmin Timeline Sync

## Destination

A locked, build-ready spec for **Garmin Timeline Sync**: a second, independent output of the Garmin account that mirrors activities, sleep, and naps onto Google Calendar as timed Timeline Events. The map is done when every decision below is made and someone can go build it without further design questions.

Planning only — this map produces decisions and a spec, not a running pipeline.

## Notes

**Domain**: personal quantified-self pipeline in a public `running_page` fork. Read `CONTEXT.md` and `docs/adr/` before any ticket — this repo has a deliberate, ADR-backed privacy model and the Timeline Sync must not disturb it.

**Skills every session should consult**: `/grilling` and `/domain-modeling` for decision tickets; `/research` for research tickets.

**Standing constraints, settled during charting** (see Decisions so far for the full table):
- ADR 0002 governs: no sleep/nap data lands in any repo, public or private. The calendar is the only store.
- The existing `garmin_publication.yml` and `GarminPublicationClient` are not to be modified. ADR 0005 set the precedent for a separate pipeline.
- Zero persisted state: deterministic event IDs make the calendar its own state.

**Tracker convention** (local markdown): each ticket is a file in `./tickets/`. Frontmatter carries `status`, `labels`, `assignee`, `blocked-by`. A ticket is *unblocked* when every id in `blocked-by` has `status: closed`. The *frontier* is every ticket that is `status: open`, unblocked, and has an empty `assignee`. Claim by setting `assignee` before doing any work.

## Decisions so far

- [Charting: destination and design constraints](./decisions/charting.md) — 20 decisions locked in the charting grill; see that file for the full table.
- [Garmin sleep and nap data — endpoints, shapes, and nap distinctness](./tickets/002-garmin-sleep-and-nap-shapes.md) — sleep timings and metrics confirmed and usable (epoch-ms GMT fields; use GMT, `*Local` is double-offset on CN accounts). **Naps have no per-nap timing** — only a daily `napTimeSeconds` aggregate, which invalidates the nap half of Q4/Q17. All activity types confirmed available in one list call. Garmin rate-limits *login*, not fetches — which favours the wide Sync Window.
- [Can a service account own a Google Calendar on a personal account?](./tickets/001-service-account-calendar-ownership.md) — **Yes; Q13 stands.** SA can create and own calendars with no Workspace license; `acl.insert` role `writer` gives native sync, not ICS. One-time manual click needed to add it to the UI (setup only, not recurring). No current Google restriction applies — the 0GB SA storage policy does not cover Calendar. Fallback confirmed healthy: the 7-day refresh-token expiry is Testing-status only.
- [Google Calendar deterministic event IDs](./tickets/003-deterministic-google-event-ids.md) — **Design survives; Q9's no-state model holds.** Charset `a-v0-9`, length 5–1024, unique per calendar; scheme is a type-tag letter plus digits (`a<activityId>`, `b<date>`). Re-insert returns 409 `duplicate`, so the pattern is insert → 409 → **patch** (never `update`, which clobbers user edits). Deleted ids are tombstoned and keep returning 409 — which *preserves* the no-state model by making a user's deletion detectable.
- [Lock the deterministic event ID scheme](./tickets/005-lock-event-id-scheme.md) — IDs are `a<garminActivityId>` and `b<YYYYMMDD>`; the tag letter is the namespace. Sleep keys on `calendarDate`, never on the revisable start timestamp. Pattern is insert → 409 → patch, with no `get` needed: activities patch `{status:confirmed}` only (append-only preserved), sleep patches full content plus status (last-sync-wins). **A deleted event is put back on the next run** — the calendar mirrors Garmin, and a deletion inside the Sync Window loses to the mirror.
- [Lock the Google auth mechanism and credential storage](./tickets/004-lock-google-auth-mechanism.md) — service account with a JSON key, in a **new dedicated GCP project**, scope `auth/calendar`. Secrets: `GOOGLE_SERVICE_ACCOUNT_JSON`, `GCAL_WORKOUTS_CALENDAR_ID`, `GCAL_SLEEP_CALENDAR_ID`. **ACL grant is `role: owner`, not `writer`** — correcting ticket 001, so the calendars survive deletion of the service account.
- [Lock the Garmin-to-Timeline-Event field mapping](./tickets/007-lock-field-mapping.md) — composed titles (`Running · 10.2 km`, `Sleep · 84`); `elapsedDuration` sets an activity's end, not `movingDuration`; `*GMT` fields throughout. Exclusion is enforced by an **allowlist mapper** — the raw Garmin dict never reaches the calendar layer, so future Garmin fields cannot leak by default.
- [Lock how the one-time 30-day backfill is triggered](./tickets/008-lock-backfill-trigger.md) — no first-run/steady-state distinction: a `--days` parameter defaulting to 7, with `workflow_dispatch` exposing `days` (the backfill is `days: 30`, and the same dispatch is the escape hatch for importing more history later). Schedule **14:00 UTC**, clear of the publication job's Garmin login.
- [Record the Timeline Sync vocabulary and ADRs](./tickets/010-record-domain-vocabulary-and-adrs.md) — `CONTEXT.md` gains a `## Timeline` cluster (Timeline Event, Sleep, Timeline Calendar, Timeline Sync, Sync Window); the Publication-vs-Sync clash is resolved in both entries; `Sleep`'s definition records why naps are absent. Four new ADRs, `0006`–`0009`.
- [Provision the Google project, credentials, and Timeline Calendars](./tickets/009-provision-google-credentials.md) — **done and verified live.** Project `garmin-timeline-sync`, service account, both Timeline Calendars owned by it and shared to the personal account as `owner`; three secrets set on `zhengfran/running_page`. All six probes passed — critically, **reviving a tombstoned event via `patch {status: confirmed}` works, so ADR 0006 holds** and no state store is needed. Two corrections to ticket 001: service-account calendar ownership is now observed fact rather than inference, and **no invitation email is sent** for an SA grant (calendars are added by id instead).
- [Assemble the build-ready spec](./tickets/011-assemble-build-ready-spec.md) — **the destination.** `docs/garmin-timeline-sync-plan.md`. Test-strategy fog resolved: unit tests only, mapper-first, with positive assertions that excluded fields stay absent.

## Not yet specified

- **Whether Timeline Sync should ever read the private FIT archive** instead of re-fetching from Garmin. Cheaper and offline-capable, but couples two pipelines ADR 0007 deliberately separated. Not needed for the destination; noted only as a possible later optimisation.
- **Whether activity Timeline Events should link back** to anything on the public running page, and what that would leak. Deliberately left unspecified — the spec is complete without it.

**The map is complete.** Every ticket is closed or out of scope, and `docs/garmin-timeline-sync-plan.md` is the handoff.

## Out of scope

- Showing sleep or nap data anywhere on the public running page. Ruled out at Q3 — ADR 0002 governs.
- Any change to the existing publication pipeline's behaviour, schedule, or client.
- Two-way sync (calendar edits flowing back to Garmin).
- Predicted or future sleep blocks for scheduling/busy purposes. Ruled out at Q1 — this is a retrospective log, and predicted sleep is a different product.
- **Nap capture, entirely.** Garmin exposes no per-nap start/end times — only a daily `napTimeSeconds` aggregate (ticket 002). The destination is a calendar of real time spans, and an aggregate cannot be one. Amends Q4 and Q17. See [Lock nap representation](./tickets/006-lock-nap-representation.md) and [Inspect a live Garmin account for per-nap timing](./tickets/012-inspect-body-battery-events-for-naps.md), both closed out of scope.
- Reconstructing nap timing from body-battery curves or activity gaps — the effort is disproportionate for a personal log, and the result would be a guess presented as a record.
