# Qualify activity identity by source

Activity identifiers are owned by Strava or Garmin and are not globally unique, so each Activity is identified by its Activity Source together with its Source Activity ID. Existing records are identified as Strava Activities, future records retain Garmin's activity ID, and the existing `run_id` remains temporarily as a page-facing compatibility identifier so the source cutover does not force an unrelated frontend migration.

## Consequences

Every normalized Garmin Activity can be traced to its archived FIT file. Importers must preserve provider identity instead of replacing it with a timestamp-derived identifier, and uniqueness must be enforced across the source and source activity ID together.
