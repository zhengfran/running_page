# Use a staged Garmin publication pipeline

The Strava-to-Garmin cutover uses a focused pipeline with explicit discovery, boundary filtering, FIT download, archive verification, normalization, validation, and publication stages. It reuses the Garmin client and FIT parsing capabilities but remains separate from the legacy `garmin_sync.py`, whose full-history, timestamp-identity, generic-title behavior conflicts with the accepted cutover invariants and would be risky to retrofit for every provider use case.

## Consequences

Tests can exercise each stage with synthetic metadata and FIT fixtures, including retries and partial failures. The daily workflow publishes only a fully validated batch and never treats downloading, archiving, or normalization alone as successful Publication.
