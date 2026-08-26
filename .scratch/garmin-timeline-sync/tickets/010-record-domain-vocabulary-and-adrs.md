---
id: "010"
title: Record the Timeline Sync vocabulary and ADRs
parent: map
labels: [wayfinder:task]
status: closed
assignee: "wayfinder-session"
blocked-by: ["004", "005", "006", "007", "008"]
---

## Question

Fold the locked decisions into this repo's domain documentation, using `/domain-modeling`.

- Add **Timeline Event**, **Sync Window**, and **Timeline Calendar** to `CONTEXT.md`, each with its `_Avoid_` line.
- Resolve the **Publication vs Sync** clash: `CONTEXT.md` currently lists *Sync* under `_Avoid_` for Publication. That guidance was scoped to Publication; Sync now has a legitimate, distinct meaning. Rewrite both entries so the distinction is explicit.
- Write the ADRs this warrants. Candidates: keeping health data out of every repo by making the calendar the sole store (Q3/Q9); treating the Timeline Sync as an independent output that shares only the Garmin login (Q2/Q14); last-sync-wins for revisable health data, against ADR 0004's append-only stance for published history (Q10).
- Cross-reference ADR 0002, 0004, and 0005 where this pipeline sits alongside or deliberately departs from them.

## Resolution

Written into the repo's real domain docs.

**`CONTEXT.md`** — new `## Timeline` cluster (kept as a subheading in the single root context rather than splitting the repo into multiple contexts, which the repo's size does not warrant): **Timeline Event**, **Sleep**, **Timeline Calendar**, **Timeline Sync**, **Sync Window**. The opening line now names both flows.

**Publication vs Sync clash resolved.** `Publication`'s `_Avoid_` listed *Sync*; it now reads `Timeline Sync (a distinct flow, see below), download`, and the `Timeline Sync` entry states the distinction directly — private, revisable, all activity types, against public, append-only, Runs alone. Neither term now silently claims the other's ground.

**Sleep's definition carries the nap finding**: naps are explicitly not Sleep, because the provider reports only a daily total with no timing, so a nap has no span to record. The glossary is where a future reader will look first when they wonder why naps are absent.

**Four ADRs**, each meeting the hard-to-reverse / surprising / real-trade-off bar:

- `0006-make-the-calendar-the-sole-store-for-timeline-data.md` — no state anywhere; deterministic ids; and the tombstone mechanism the whole thing rests on, with the reopening condition named.
- `0007-run-the-timeline-sync-as-an-independent-output.md` — separate workflow and client; continues ADR 0005's reasoning; records that logins, not fetches, are the rate-limited resource.
- `0008-let-later-syncs-overwrite-recorded-sleep.md` — the apparent conflict with ADR 0004, argued as a scope distinction rather than a departure. This is the one a future reader is most likely to flag as a contradiction, which is precisely why it is written down.
- `0009-own-the-timeline-calendars-with-a-service-account.md` — service account over OAuth, and the `owner`-not-`writer` grant that keeps the history alive if the service account dies.

Deliberately **not** given an ADR: the choice of `elapsedDuration` for an activity's end, the composed title formats, and the 14:00 UTC schedule. All are trivially reversible and none would surprise a reader — they live in the tickets and the spec.
