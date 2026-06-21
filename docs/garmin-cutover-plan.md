# Garmin Source Cutover Plan

## Goal

Replace Strava with Garmin Global as the Activity Source for Runs beginning strictly after `2026-06-05 11:01:14 UTC`. Retain the 1,065 existing Strava Activities, including historical non-running Activities, without re-importing Garmin history.

## Invariants

- Existing Activities retain Strava identity and their non-route data.
- Only Garmin Runs after the Cutover Boundary may be added.
- Activity identity is the pair of Activity Source and Source Activity ID.
- A Garmin Run is published only after its FIT export is committed and pushed to `zhengfran/running-fit-archive`.
- Source Archive entries and published Activities are append-only during routine synchronization.
- Full routes exist only in the private Source Archive. The public database, JSON, and SVGs contain Public Routes processed by the existing redaction policy.
- Garmin UTC and recorded local start times are both preserved; UTC determines boundary membership and local time determines calendar grouping.
- Garmin Connect supplies first-import names and source identity; FIT supplies measurements, route data, and archival provenance.

## Pipeline

```text
discover -> boundary filter -> download FIT -> archive and verify
         -> push private archive -> normalize -> validate -> publish
```

The pipeline is retry-safe. Archive failure leaves public history unchanged. A failure after archive push retries from the verified archive without rewriting it.

## Rollout

1. Keep `RUN_TYPE: pass` while implementing and validating the cutover.
2. Test each pipeline stage with synthetic Garmin metadata and FIT-shaped fixtures.
3. Run one manual archive-first synchronization.
4. Verify the release gate below against Garmin Connect.
5. Enable daily synchronization at `00:00 UTC` only after manual approval.

## Release Gate

- All 1,065 Legacy Activities remain and are identified as Strava.
- Every new Activity is a Garmin Run strictly after the Cutover Boundary.
- Every Garmin Activity maps to a checksummed FIT file in the private archive.
- No duplicate start times are introduced around the boundary.
- Distance, time, heart rate, route, UTC start, local start, and title match a sample in Garmin Connect.
- Public route data is redacted before persistence and generation.
- Tests, frontend build, and generated SVGs succeed.

## Rollback

Freeze ingestion, revert the public data commit, and investigate. FIT exports already committed to the private Source Archive remain there; routine rollback never deletes source evidence.
