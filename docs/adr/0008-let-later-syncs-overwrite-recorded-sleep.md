# Let later syncs overwrite recorded sleep

Within the Sync Window, a Timeline Event for Sleep is rewritten from the provider on every run, so the last sync wins. Activities remain append-only, matching ADR 0004. The asymmetry is deliberate: the provider genuinely revises sleep — finalising stages and adjusting boundaries hours after waking — while an activity's span does not drift once recorded.

## Consequences

This is not a departure from ADR 0004. That decision governs *published* history: a public, immutable record others may already have read, where a provider-side edit is not a Correction. A Timeline Calendar is private and unpublished, and its whole value is that it accurately records what happened, so deferring to the provider's latest word is the correct behaviour rather than a compromise of it.

A Timeline Event for Sleep is therefore identified by its calendar date, never by its start timestamp — an identifier derived from a revisable field would produce a duplicate Event the moment the provider adjusted the boundary, instead of updating the existing one.
