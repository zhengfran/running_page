---
id: "001"
title: Can a service account own a Google Calendar on a personal account?
parent: map
labels: [wayfinder:research]
status: closed
assignee: "research-agent"
blocked-by: []
---

## Question

Q13 locked service-account-owned Timeline Calendars as the auth route, on the strength of having no coupling to the user credential. That choice is unverified and on the critical path.

Establish, against Google's primary documentation:

1. Can a service account with **no Google Workspace license** (the Google account here is a personal `@gmail.com`) create a secondary calendar via the Calendar API `calendars.insert`, and own it?
2. Can that service account then share the calendar to a personal Gmail address with write access via `acl.insert`, such that it appears as a normal, fully-syncing calendar in that user's Google Calendar UI — not an ICS subscription?
3. Has Google restricted or announced restrictions on any of the above? There has been tightening around service-account storage and calendar quotas; determine what is current.
4. **Fallback path**: for an OAuth desktop-app client whose Google Cloud app is in **"In production"** publishing status but **unverified**, with the sensitive `calendar.events` scope — what is the refresh-token lifetime? Confirm the 7-day expiry applies only to "Testing" status, and enumerate what else revokes a production refresh token (password change, inactivity period, user-count caps for unverified apps).

Answer must be decisive enough for ticket 004 to lock a mechanism.

## Context

Findings will be captured at `.scratch/garmin-timeline-sync/research/001-service-account-calendar-ownership.md`.

## Resolution

Findings: `.scratch/garmin-timeline-sync/research/001-service-account-calendar-ownership.md`.

**Q13's preferred design survives. Keep service-account-owned Timeline Calendars.**

1. **A service account can create and own calendars** via `calendars.insert` using only its own credentials — no domain-wide delegation, so the missing Workspace license is not a blocker. Google's docs discourage this on the grounds that SA ownership "can't be transferred"; that is a caveat about *transfer*, and this design wants permanent SA ownership anyway.
2. **`acl.insert` with `role: writer` gives genuine native two-way sync** — architecturally nothing like an ICS subscription. **But** ACL grant is decoupled from calendar-list visibility: the recipient must click the emailed link **once** to make the calendar appear in their UI. That is a one-time setup click, not recurring re-auth, so Q8 is satisfied. Whether that flow behaves identically for an *SA-owned* calendar is **explicitly undocumented** — the one relevant Google Issue Tracker thread was behind an auth wall. Treat as a live risk to verify during ticket 009.
3. **No current restriction blocks any of this.** The 2023 "service accounts get 0GB storage" change is a Drive/Docs/Photos/Gmail *storage* policy; Google's storage-accounting page does not list Calendar, and calendar entries do not count against it. The only 2026-dated change is a general rate-limit and future-billing restructuring, not an access ban. Rated medium-high rather than high — "nothing forbids this" is inherently a weaker claim than a positive one.
4. **Fallback is healthier than assumed.** The 7-day refresh-token expiry is confirmed verbatim (doc updated 2026-05-26) to apply **only to "Testing" + "External"** apps. A production app's token dies only from explicit revocation, 6-month inactivity, a password change *combined with Gmail scopes* (calendar-only scopes are not documented as affected), or the 100-live-token cap. An unverified production app can be used indefinitely by its own owner — Google's verification FAQ explicitly sanctions "you are the only user of your app."

**Why still prefer the service account**, given the fallback looks viable: the OAuth route's survival across a password change rests on an *absence* of documentation for calendar-only scopes, not a stated guarantee. The SA route has no dependency on the user credential at all, which is what Q8 actually demanded.
