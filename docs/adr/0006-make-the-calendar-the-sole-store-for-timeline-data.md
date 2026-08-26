# Make the calendar the sole store for Timeline data

Sleep timings and activity histories reveal home presence, routine, and health, and ADR 0002 already bars precise health data from the public repository. The Timeline Sync therefore writes nothing to any repository at all — no state file, no cursor, no synced-id list, in neither the public repository nor the private Source Archive. Idempotency comes instead from deterministic Timeline Event identifiers derived from the provider's own record identity, so re-running a sync is a no-op and the Timeline Calendar is its own state.

## Consequences

The privacy boundary is satisfied by construction rather than by discipline: there is no file that could accidentally accumulate health data, because the design has nowhere to put one. A sync is crash-safe and re-runnable from scratch at any Sync Window width.

The provider's calendar semantics become load-bearing. Deleting a Timeline Event leaves a tombstone that keeps rejecting re-insertion, which is what allows a deletion to be detected without local state; a run inside the Sync Window revives it, and the Timeline Calendar continues to mirror the provider. Should tombstone revival prove unavailable, the only remaining route to idempotency is a state store, which would reopen this decision and the privacy boundary with it.
