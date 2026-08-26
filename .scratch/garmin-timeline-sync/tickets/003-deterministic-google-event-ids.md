---
id: "003"
title: Google Calendar deterministic event IDs — format rules and re-insert semantics
parent: map
labels: [wayfinder:research]
status: closed
assignee: "research-agent"
blocked-by: []
---

## Question

Q9 makes deterministic event IDs load-bearing: they are the *entire* reason this design needs no persisted state, which in turn is what satisfies the Q3 privacy line by construction. If they don't work as assumed, the design loses its foundation.

Against Google Calendar API primary documentation:

1. What are the exact **format constraints** on a caller-supplied event `id`? Confirm the character set (base32hex — lowercase `a-v` and `0-9`), the length bounds, and uniqueness scope (per calendar? per account?).
2. Given a Garmin activity ID (numeric) and a sleep record key (likely a date), what **encoding** produces a conforming ID deterministically? Note that a natural prefix like `garmin-activity-` contains characters outside base32hex — establish what actually works.
3. What happens on `events.insert` with an **id that already exists**? Is it a 409 error, a silent no-op, or an overwrite? Establish the correct call pattern for "create or update" — whether that is `events.update`, `events.import`, or insert-then-catch-409.
4. Does re-inserting or updating an event that a **user has since edited** clobber their edit, and does it move the event in the UI or send notifications?
5. What happens to a deterministic ID after an event is **deleted** — is the ID reusable, or tombstoned? This decides whether a deleted event silently fails to re-sync forever.

Point 3 and point 5 are the ones that can break the design; give them the most weight.

## Context

Findings will be captured at `.scratch/garmin-timeline-sync/research/003-deterministic-google-event-ids.md`.

## Resolution

Findings: `.scratch/garmin-timeline-sync/research/003-deterministic-google-event-ids.md`. Confidence: Q1–Q3 High (verbatim from the Events reference and the live Discovery Document), Q4–Q5 Medium (docs partly silent — see below).

**The design survives.** Deterministic IDs work, and Q9's no-state model holds.

1. **Format**: charset `a-v` lowercase plus `0-9`, length **5–1024**, unique **per calendar**. Confirmed identically in the human-readable reference and the machine-readable Discovery Document.
2. **Encoding**: a prefix like `garmin-activity-` fails twice — on the `-` and on letters past `v`. Recommended scheme: a single type-tag letter plus digits, no separators — `a12345678901` for an activity, `b20260825` for a sleep date. Namespacing comes free from the tag letter.
3. **Re-insert is HTTP 409, reason `duplicate`** — explicitly documented, with Google's own remediation being to update instead. Correct pattern: **insert → on 409 → patch**. `events.import` is the wrong tool: it is keyed on `iCalUID` rather than the caller's id, and has no `sendUpdates` parameter at all.
4. **Use `patch`, not `update`.** `update` is a full PUT that silently clobbers fields — including any edit the user made by hand. `patch` leaves unspecified fields unchanged, which is what a repeatedly-re-run sync needs. Set `sendUpdates=none`, but note the docs' own caveat that "some emails might still be sent." UI reordering and owner-side notification behaviour are **undocumented** — a live check during ticket 009 is the only way to be sure.
5. **Deletion is a soft tombstone** (`status: cancelled`), not a freed id. Re-inserting the same id hits the same 409. Tombstones "eventually disappear" with no API-documented retention; the consumer help centre cites a 30-day Trash window.

**Point 5 is a feature, not a problem, and it lands well against Q16.** Because the tombstone persists and returns 409, the job can *detect* that the user deleted an event rather than blindly resurrecting it — so the calendar remains the sole state, including the record of a deletion. And the ~30-day tombstone comfortably outlives the 7-day Sync Window, so a deletion inside the window is always visible as a 409, while an event deleted after the window is never revisited anyway. No state store needed. Ticket 005 must still decide the branch: revive the tombstone, or respect the deletion.
