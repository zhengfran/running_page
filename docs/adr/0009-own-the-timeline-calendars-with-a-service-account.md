# Own the Timeline Calendars with a service account

The Timeline Calendars are created and owned by a Google service account, which shares them to the personal account as co-owner. An OAuth refresh token was the obvious alternative and was rejected: it is bound to a user credential, so a password change or security event revokes it and the sync stops silently, which an unattended job running for years cannot tolerate. A service account key has no such coupling. Domain-wide delegation was never available here — the account is a personal one with no Workspace license.

## Consequences

The personal account is granted `owner` rather than `writer` on each Timeline Calendar. Writer would leave the service account as sole owner of the entire Timeline, so deleting it — a tidied-up cloud project, a billing lapse, an errant IAM change — would destroy years of irreplaceable history with no prior warning. Co-ownership costs nothing and removes that single point of failure.

Setup is not fully unattended even though operation is: the shared calendars appear in the personal account's interface only after a one-time click on an emailed invitation. This is a setup step, not recurring re-authentication.
