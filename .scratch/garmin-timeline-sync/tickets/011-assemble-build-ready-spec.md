---
id: "011"
title: Assemble the build-ready spec
parent: map
labels: [wayfinder:task]
status: closed
assignee: "wayfinder-session"
blocked-by: ["009", "010"]
---

## Question

The destination. Assemble every locked decision into a single spec someone can build from without asking a design question.

Must cover: module layout and where the new Garmin client lives (Q20); the workflow file, its schedule and inputs (Q14, Q8-trigger); the fetch-to-event pipeline stages; the ID scheme; the field mapping and its exclusion enforcement; the failure and canary behaviour (Q19); and the test strategy — which is currently fog on the map and must be resolved or explicitly deferred here.

Verify before closing that nothing in the spec modifies `garmin_publication.yml`, `GarminPublicationClient`, or `garmin_publish.py`.

## Resolution

Spec written to `docs/garmin-timeline-sync-plan.md`, in the house style of `docs/garmin-cutover-plan.md` — Goal, Invariants, Layout, Pipeline, identity, write semantics, field mapping, Workflow, Failure, Test strategy, Rollout, Release Gate.

**Test strategy fog resolved, not deferred.** Unit tests only; CI never touches live Google or live Garmin. The highest-value target is the mapper, because it is where the allowlist is enforced — and the test is a *positive* assertion that excluded fields are absent even when the synthetic input contains them, rather than an absence of any test. Live behaviour (tombstone revival, 409-on-reinsert, inert no-op patch) was verified once during provisioning and deliberately not re-run in CI, where it would be flaky and would mutate a real calendar.

**Verified before closing**: the spec modifies nothing in the publication pipeline. `garmin_publication.yml`, `garmin_publish.py`, and `GarminPublicationClient` are untouched, and the Release Gate asserts their outputs are byte-for-byte unaffected.

The Rollout's step 4 — re-dispatching the 30-day backfill and confirming nothing duplicates — is the idempotency proof, and the cheapest possible check that ADR 0006 holds in production as it did on the probe.
