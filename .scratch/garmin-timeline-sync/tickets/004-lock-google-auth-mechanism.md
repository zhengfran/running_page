---
id: "004"
title: Lock the Google auth mechanism and credential storage
parent: map
labels: [wayfinder:grilling]
status: closed
assignee: "wayfinder-session"
blocked-by: ["001"]
---

## Question

With ticket 001 answered, lock the auth mechanism: service-account-owned calendars (Q13's choice) or the OAuth-in-production fallback.

Then settle what follows from it:
- Exactly which credential material exists, and which GitHub secrets hold it on `zhengfran/running_page`.
- Which Google Cloud project and API scopes.
- How the two Timeline Calendar IDs (Q17) reach the job — hardcoded, secret, or discovered by name at runtime.
- What the recovery procedure is if the credential does break despite Q8, and how the failure surfaces (relates to Q19).

## Proposal (pre-worked, awaiting confirmation)

Ticket 001 came back decisive, so the mechanism itself is settled: **service account**. What remains is mechanical, plus one design catch.

- **Mechanism**: service account, JSON key. No coupling to the user credential (Q8).
- **Scope**: `https://www.googleapis.com/auth/calendar`. Runtime only needs `calendar.events`, but the same credential does one-time calendar creation, so the broader scope avoids a second credential.
- **GitHub secrets** on `zhengfran/running_page`: `GOOGLE_SERVICE_ACCOUNT_JSON`, `GCAL_WORKOUTS_CALENDAR_ID`, `GCAL_SLEEP_CALENDAR_ID`.
- **Calendar IDs as secrets, not workflow env vars.** A calendar id grants no access on its own (the ACL does), but this repo is public and there is no reason to publish them. Cheap to keep private.
- **Recovery**: a lost or compromised key is rotated in GCP and the secret updated; the calendars and their history are unaffected.

### The catch — share as `owner`, not `writer`

Ticket 001 assumed `acl.insert` with `role: writer`. That leaves the **service account as sole owner of your entire calendar history**. If the SA is ever deleted — a tidied-up GCP project, a billing lapse, an accidental IAM change — the calendars it owns go with it, and years of life-log vanish. Nothing in the design would warn you first.

Granting your Gmail `role: owner` instead costs nothing and makes you a co-owner, so the calendars survive the service account entirely. Strictly better; recommend it.

### Needs the user

- Which Google Cloud project — a new dedicated one, or an existing project?

## Resolution

Proposal above confirmed in full (Q21, Q22).

- **Mechanism**: service account with a JSON key. No coupling to the user credential, satisfying Q8.
- **Google Cloud project**: a **new dedicated project**, so this service account's blast radius is exactly one thing.
- **Scope**: `https://www.googleapis.com/auth/calendar`.
- **ACL grant to `zhicheng.ink98@gmail.com`: `role: owner`, not `writer`.** This is the correction to ticket 001's assumption. Writer would leave the service account as sole owner of the entire life-log, so deleting the SA — a tidied project, a billing lapse, an IAM change — would destroy years of irreplaceable history with no prior warning. Co-ownership costs nothing and removes the single point of failure.
- **GitHub secrets** on `zhengfran/running_page`: `GOOGLE_SERVICE_ACCOUNT_JSON`, `GCAL_WORKOUTS_CALENDAR_ID`, `GCAL_SLEEP_CALENDAR_ID`. Calendar ids are secrets rather than workflow env vars — they grant no access alone, but this repo is public and publishing them buys nothing.
- **Recovery**: rotate the key in GCP and update the secret; calendars and history are unaffected. With `owner` on the Gmail account, they survive loss of the service account too.
