# Run the Timeline Sync as an independent output

The Timeline Sync is a separate workflow with its own schedule and its own provider client, sharing nothing with the publication pipeline but the Garmin credentials. Extending `garmin_publication.yml` or `GarminPublicationClient` was rejected: that pipeline is deliberately narrow, fails closed around the archive-first invariant of ADR 0002, and admits only Runs, whereas the Timeline admits every activity type plus Sleep.

## Consequences

A calendar or Google API failure cannot abort an archive push, and the two pipelines can be scheduled independently — which matters, because the publication job runs too early in the day for the provider to have finalised the previous night's sleep. This continues the reasoning of ADR 0005, which made the same separation once already rather than retrofitting a general-purpose client.

The two jobs must never contend for a provider login. Garmin rate-limits authentication per account, with reported soft-bans measured in days, so their schedules are kept well apart and the Sync Window is made wide rather than the fetch count small — extra fetches are cheap, extra logins are not.
