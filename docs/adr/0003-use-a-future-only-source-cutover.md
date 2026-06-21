# Use a future-only source cutover

Garmin becomes the Activity Source only for Runs starting strictly after `2026-06-05 11:01:14 UTC`; the 1,065 existing Activities remain provider-qualified Strava Activities, including their non-running activity types. Rebuilding Garmin history was rejected because provider IDs differ and the existing storage model would duplicate matching Activities rather than replace them safely.

## Consequences

Strava ingestion remains frozen until a manual cutover run proves that all Legacy Activities are unchanged, every new Activity is a post-boundary Garmin Run backed by a checksummed FIT export, no boundary duplicates exist, sampled metrics match Garmin Connect, and the frontend plus generated SVGs build successfully. The release fails closed if any invariant is violated.
