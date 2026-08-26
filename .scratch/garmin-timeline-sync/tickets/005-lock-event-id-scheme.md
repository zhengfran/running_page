---
id: "005"
title: Lock the deterministic event ID scheme
parent: map
labels: [wayfinder:grilling]
status: closed
assignee: "wayfinder-session"
blocked-by: ["003"]
---

## Question

With ticket 003 answered, lock the ID scheme.

- The exact derivation from a Garmin activity ID to a conforming Google event ID, and from a sleep or nap record to one.
- Namespace separation so an activity ID and a sleep record can never collide, given both calendars and all Timeline Event kinds.
- The create-or-update call pattern, per 003's finding.
- The behaviour when a deterministic ID is unavailable because the event was deleted, if 003 shows IDs are tombstoned. This may force a state-bearing fallback, which would reopen Q9 and Q3 — flag it loudly if so.

## Resolution

Locked against ticket 003's findings.

### ID scheme

Google's charset is `a-v` plus `0-9`, length 5–1024, unique per calendar — so no separators and no letters past `v`.

| Timeline Event kind | ID | Example |
|---|---|---|
| Activity | `a` + Garmin activity id (digits) | `a12345678901` |
| Sleep | `b` + `YYYYMMDD` of the sleep record's `calendarDate` | `b20260825` |

The leading tag letter is the namespace: it makes an activity id and a sleep date incapable of colliding even though uniqueness is only scoped per calendar and the two kinds live on different Timeline Calendars today. Both forms clear the 5-character minimum (`a` + 11 digits = 12; `b` + 8 digits = 9).

Sleep is keyed on `calendarDate` rather than the sleep start timestamp deliberately — the start time is revisable by Garmin (Q10), and an ID derived from a revisable field would produce a duplicate event instead of an update the moment Garmin adjusted the boundary.

### Call pattern — and the deletion decision

**Decision: a deleted event is put back on the next run.** The calendar mirrors Garmin; a deletion inside the Sync Window loses to the mirror.

Both kinds start with `events.insert` carrying the deterministic id, and branch on 409 `duplicate`. Neither path needs a `get`, because patching `status` is idempotent:

- **Activity** — on 409, `patch` with **only** `{status: "confirmed"}`. Content is never rewritten, honouring Q10's append-only rule for activities; a tombstone is revived; an already-confirmed event is untouched.
- **Sleep** — on 409, `patch` with the full field set **plus** `{status: "confirmed"}`. This is Q10's last-sync-wins and the revival, in one call.

All calls set `sendUpdates=none`.

**Consequence worth naming**: deleting a synced event by hand is futile inside the 7-day Sync Window — it returns the next morning. Past the window the job never revisits it, so the deletion sticks. That is a coherent and predictable rule, and it is the one chosen; the alternative (respecting deletions) was rejected as it makes the calendar's contents depend on an invisible history of user actions.

### Carried to ticket 009 for live verification

Ticket 003 rated two points medium-confidence, both because Google's docs are silent rather than contradictory:

1. That patching `status` from `cancelled` back to `confirmed` actually revives a tombstoned event — the mechanism is logical and community-corroborated, but has no official worked example. **This is load-bearing for the decision above.** If it fails, the fallback is a different id derivation for the retry, which would reintroduce state and reopen Q9 — flag loudly if so.
2. That patching an already-`confirmed` event with `{status: "confirmed"}` is a true no-op that neither reorders the event in the UI nor emails the owner.
