# Charting decisions — Garmin Timeline Sync

Settled in the charting grill. Each row is a decision, not a proposal.

| # | Question | Decision |
|---|---|---|
| Q1 | What is the calendar for? | Retrospective life-log. Not scheduling, not busy-blocking. |
| Q2 | Calendar as destination or rendering? | Second independent output of a Garmin ingest. Shares only the Garmin login with the publication pipeline. |
| Q3 | Privacy line | ADR 0002 governs. No sleep/nap data in any repo — not `data.db`, not `activities.json`, not a state file. Code and secrets may live in the public repo; data may not. |
| Q4 | What counts as an event? | Every Garmin activity type (not just Runs), plus sleep, plus naps. The `is_only_running` filter is publication policy and must not leak here. |
| Q5 | Destination shape | Locked spec + build-ready plan. Planning, not building. |
| Q6 | Code and credentials housing | This repo. `GARMIN_TOKENS_JSON` + email/password self-heal already work here and are exercised daily; duplicating them elsewhere means two rotation points. |
| Q7 | Google account type | Personal `zhicheng.ink98@gmail.com`. No Workspace, so no domain-wide delegation. |
| Q8 | Manual re-auth tolerance | Zero. Must run for years untouched. |
| Q9 | Idempotency | Deterministic event IDs derived from Garmin IDs. No persisted state anywhere — the calendar is the state. Satisfies Q3 by construction. |
| Q10 | Response to Garmin revisions | Last-sync-wins for sleep and naps (Garmin finalises stages and detects naps late). Append-only for activities. ADR 0004 governs *published* history; a private calendar is neither published nor immutable. |
| Q11/Q12 | History and window | 7-day rolling sync window in steady state; 30-day backfill on first run only. Window bounds how long an event stays open to revision, not how much calendar history exists — events accumulate forever. |
| Q13 | Google auth route | Service-account-owned calendars, shared to the personal Gmail with write access. Chosen because it has no coupling to the user credential — a password change cannot revoke it. **Pending research**; OAuth-app-in-production is the designed fallback. |
| Q14 | Workflow placement | New, separate workflow. Failure isolation (a Google outage must never abort an archive push) and timing (00:00 UTC is too early for finalised sleep). |
| Q15 | Event body detail | Times, titles, and summary metrics (sleep score, duration, distance, pace, avg HR). No routes, no precise location — the one class ADR 0002 treats as categorically different. |
| Q16 | Missed-run recovery | 7-day window. Deterministic IDs make re-writes free, so a wide window costs nothing and buys tolerance for failed runs plus late nap detection. |
| Q17 | Calendar set | Two: "Workouts" and "Sleep". Naps go on Sleep, titled distinctly. Separate calendars are the only way Google allows independent visibility/colour toggling. |
| Q18 | Timezone | Write the UTC instant, no timezone override. Garmin gives a UTC offset, not an IANA zone name, and offset-to-zone inference would be wrong sometimes in exchange for correctness on rare travel weeks. |
| Q19 | Failure detection | Actions' built-in failure email, plus the job fails loudly on zero sleep records in the window. Zero sleep is definitionally a bug, never a valid state — a free, high-signal canary against silent parse failures. |
| Q20 | Client | New client. `GarminPublicationClient` guards the archive-first invariant; sleep-fetching code must not live inside it. ADR 0005 made this exact call once already. |

## Vocabulary consequence

`CONTEXT.md` defines **Publication** as admission into the *public running history* and lists *Sync* under `_Avoid_`. That guidance was scoped to Publication. This pipeline genuinely is a **Sync**, not a Publication, and naming it so is what keeps the two flows distinct. New terms needed: **Timeline Event**, **Sync Window**, **Timeline Calendar**.

## Amendments

- **Q4 and Q17 amended (naps dropped).** Q4 scoped naps in and Q17 placed them on the Sleep calendar, titled distinctly. Ticket 002 then established Garmin exposes no per-nap timing. Nap capture is now Out of scope; the Sleep Timeline Calendar carries main sleep only. Activities and sleep are unaffected.
