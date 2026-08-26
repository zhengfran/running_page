---
id: "009"
title: Provision the Google project, credentials, and Timeline Calendars
parent: map
labels: [wayfinder:task]
status: closed
assignee: "wayfinder-session"
blocked-by: ["004"]
---

## Question

Manual provisioning that must happen before any later decision can be validated against reality. Nothing to decide here — ticket 004 decided it — but the work blocks confirming the mechanism actually behaves as researched.

- Create or identify the Google Cloud project; enable the Calendar API.
- Create the credential that 004 chose.
- Create the two Timeline Calendars (Q17) and share them to `zhicheng.ink98@gmail.com` with write access.
- Store the credential and calendar IDs as GitHub secrets on `zhengfran/running_page`.

Record in the resolution: what was created, which secret names hold what, and the two calendar IDs' storage location. Later tickets depend on those facts.

## Live checks carried from closed tickets

Three things the documentation does not settle. Verify each once real credentials exist, and record the results — later tickets depend on them:

1. **From ticket 001**: does the share-acceptance click flow work normally for a calendar owned by a *service account*? Google's issue tracker thread on this was inaccessible.
2. **From ticket 005**: does `patch` with `{status: "confirmed"}` genuinely revive a tombstoned (`cancelled`) event? Load-bearing — the whole put-it-back decision rests on it, and failure reopens Q9's no-state model.
3. **From tickets 003 and 005**: is patching an already-confirmed event a true no-op — no UI reordering, no email to the calendar owner? The job patches the same sleep event up to seven days running.

## Checklist (HITL — requires console/CLI access the agent does not have)

Per the closed ticket [Lock the Google auth mechanism](./004-lock-google-auth-mechanism.md).

**1. Project and API**
```
gcloud projects create garmin-timeline-sync
gcloud config set project garmin-timeline-sync
gcloud services enable calendar-json.googleapis.com
```

**2. Service account and key**
```
gcloud iam service-accounts create timeline-sync --display-name "Garmin Timeline Sync"
gcloud iam service-accounts keys create ~/timeline-sync-key.json \
  --iam-account timeline-sync@garmin-timeline-sync.iam.gserviceaccount.com
```
No project IAM role binding is needed — the service account acts on its own calendars, not on project resources.

**3. Create the two Timeline Calendars, as the service account**

Use the throwaway script `../bootstrap_calendars.py`:
```
pip install google-auth google-api-python-client
python bootstrap_calendars.py provision ~/timeline-sync-key.json
```
It creates `Workouts` and `Sleep`, grants `zhicheng.ink98@gmail.com` `role: owner` on each (not `writer` — see ADR 0009), and prints the two calendar ids. Re-running is safe: it reuses a calendar that already exists rather than creating a duplicate.

**4. Accept the invitations.** Each grant emails an invitation link; click both once so the calendars appear in the UI. One-time only.

**5. Store the secrets** on `zhengfran/running_page`:
- `GOOGLE_SERVICE_ACCOUNT_JSON` — full contents of the key file
- `GCAL_WORKOUTS_CALENDAR_ID`, `GCAL_SLEEP_CALENDAR_ID` — the two ids from step 3

Then delete the local key file.

## Live checks to run while provisioned

The three carried from closed tickets, above. Record each result — the second is load-bearing and its failure reopens ADR 0006:

Checks 2 and 3 are automated by the same script:
```
python bootstrap_calendars.py verify ~/timeline-sync-key.json <workouts-calendar-id>
```
It inserts a probe event, re-inserts it (expecting 409), no-op patches it, deletes it, re-inserts the dead id (expecting 409 = tombstoned), then attempts revival via `patch {status: confirmed}` — step 6, the load-bearing one — and cleans up after itself.

Check 1 is manual: after step 4's invitation click, confirm the calendars appear in the UI as normal writable calendars, not read-only subscriptions.

## Resolution (provisioning complete; one manual check outstanding)

Executed 2026-08-26.

**Created**
- GCP project `garmin-timeline-sync`. No billing account was requested at any point.
- Calendar API (`calendar-json.googleapis.com`) enabled.
- Service account `timeline-sync@garmin-timeline-sync.iam.gserviceaccount.com`. No project IAM role binding — it acts only on its own calendars.
- Timeline Calendars `Workouts` and `Sleep`, both created **by and owned by the service account**, both shared to `zhicheng.ink98@gmail.com` with `role: owner` per ADR 0009.

**Secrets set** on `zhengfran/running_page`: `GOOGLE_SERVICE_ACCOUNT_JSON`, `GCAL_WORKOUTS_CALENDAR_ID`, `GCAL_SLEEP_CALENDAR_ID`. Local key file deleted.

### Live check results

**Ticket 001's central claim is now verified, not merely undocumented-and-probably-fine.** A service account on a personal Google account with no Workspace license created and owned two calendars, and `acl.insert` accepted `role: owner`. That was rated medium-high confidence precisely because it rested on an absence of prohibition; it is now a positive observed fact.

Six probes, all passing:

| # | Probe | Result |
|---|---|---|
| 1 | insert with caller-supplied id | ok |
| 2 | re-insert live event | 409 as documented |
| 3 | no-op patch on live event | ok — **`updated` timestamp did not change** |
| 4 | delete | ok |
| 5 | re-insert deleted id | 409 — tombstoned, as ticket 003 predicted |
| 6 | **revive tombstone via `patch {status: confirmed}`** | **`status=confirmed`** |

**Probe 6 is the load-bearing one and it passes. ADR 0006 holds** — deterministic ids give full idempotency with no state store, so no health data need ever touch a repository.

**Probe 3 came back stronger than hoped**: a no-op patch does not even bump the event's `updated` timestamp, so the seven-times-per-week re-patching of a sleep event is genuinely inert rather than merely harmless.

### Incidental finding — the charset rule is enforced, and it bit immediately

The first verification run failed with `400 Invalid resource id value` because the probe id used the prefix `z`. Base32hex stops at `v`. This is exactly the trap ticket 003 flagged, and it confirms Google rejects a non-conforming id outright rather than coercing it — so the `a`/`b` tag-letter scheme locked in ticket 005 is not merely conventional, it is required.

### Correction to ticket 001 — there is no invitation email

Ticket 001 concluded the recipient "must click the link in the email" to add a shared calendar, sourced from Google's **consumer** Help Center, which documents user-to-user sharing. **No email is sent for a service-account grant.** A service account has no mailbox and no consumer notification path, so `acl.insert` grants the permission silently.

The grant itself is correct and verified by `acl.list` — `zhicheng.ink98@gmail.com` holds `role: owner` on both Timeline Calendars, alongside the service account and each calendar's own self-rule.

The calendar is instead attached to the user's view manually: **Google Calendar → Settings → Add calendar → Subscribe to calendar**, pasting the calendar id. Despite the "Subscribe" wording this is not an ICS subscription — the existing `owner` ACL governs access.

This is precisely the gap ticket 001 flagged as undocumented for service-account-owned calendars, and it resolved against the assumption. Setup is therefore *more* hands-off than expected in one respect (no invitation round-trip) and less discoverable in another (the user must know the ids).

### Live check 1 — closed

Both Timeline Calendars added to the personal account's view by id and confirmed present. The `owner` ACL is verified at API level by `acl.list`, which is what governs access; the "Subscribe to calendar" wording in the UI does not make it an ICS subscription.

Standing caveat: if either calendar later proves read-only in the UI, `role: owner` is not being honoured through the add-by-id path and ADR 0009 needs revisiting. Nothing observed suggests that.
