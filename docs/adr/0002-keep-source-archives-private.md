# Keep source archives private

Garmin FIT files are retained in the private `zhengfran/running-fit-archive` repository rather than the public running-page repository. FIT preserves valuable source fidelity for future use, but it also contains precise routes, timestamps, health measurements, and recurring-location patterns that must not become part of public Git history; the public repository retains only normalized activity data and provider-qualified identity. The archive stores each source export at `garmin/<activity-id>.fit` and records its SHA-256 digest and byte size in a versioned manifest.

## Consequences

Publication is archive-first: a normalized Activity enters the public repository only after its FIT file has been committed and pushed successfully to the private Source Archive. A failed archive write leaves public history unchanged, and retries use provider-qualified identity to remain idempotent.

Source exports retain full route fidelity in the private archive. Public Routes continue through the existing location-mask and start/end redaction policy, with automated coverage ensuring Garmin ingestion cannot bypass it. The cutover sanitizes the current public database snapshot and all newly generated JSON and SVG artifacts, but does not rewrite historical Git commits that already contain earlier route data.
