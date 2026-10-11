# Write the Timeline into the LifeOS Time Log

The Timeline Sync now writes Activities and Sleep into one calendar: the owner's LifeOS Time Log, a Lyubishchev time ledger that the owner also fills by hand from a phone app and from Google Calendar. The two Timeline Calendars that the service account owned are no longer written to. They are left in place, untouched.

The Time Log has conventions of its own, and every Timeline Event follows them. Event colour is the LifeOS Area, and Sleep and Activities are Health (`colorId` 10, configurable through `TIME_LOG_AREA_COLOR_ID`). Events are timed and transparent, with `reminders.useDefault=false`. Under the owner's clarified 2026-10-11 title convention, Garmin entries use Area - Activity: "Health - Sleep", "Health - Run (10.2 km)" or "Health - Strength training". Distance is the actual Garmin distance rounded to one decimal kilometre, never a literal placeholder. Activity details start the description, followed by their measurements. This follows the Garmin exception in LifeOS ADR 0005; activity labels do not create LifeOS Projects. A Source Marker goes in `extendedProperties.private`: `{lifeos: "time-log/1", source: "garmin", garmin_kind, garmin_id}`.

## Consequences

Event ids are now the first 32 lowercase hex characters of `sha256("garmin:<kind>:<garmin id>")`. They are still deterministic and still base32hex, but now namespaced by source, so they cannot collide with hand-logged events or with another source. Events in the old calendars used `a<activityId>` and `b<YYYYMMDD>`. Those ids are not reused.

Because the calendar is shared with hand-logged entries, a `409` is no longer patched blindly. The existing event is read first:

- if it lacks the Source Marker, it is never edited;
- if the owner deleted it (a tombstone), it stays deleted. This refines ADR 0006: a Time Log deletion is the owner's decision about their own ledger, not drift to undo;
- otherwise an Activity stays as it is (append-only), and Sleep is patched (ADR 0008).

Overlap with a hand-logged event is accepted, because Time Log coverage is measured by the union of events.

The service account no longer owns the target calendar. The owner owns the Time Log and shares it with the service account with "Make changes to events". This removes the single point of failure that ADR 0009 worked around with co-ownership. The scope narrows from `calendar` to `calendar.events`.

## Migration (2026-10-11)

The history in the old Workouts and Sleep calendars was copied into the Time Log by a one-off, insert-only migration that rebuilt each `a<activityId>` / `b<YYYYMMDD>` event with this ADR's hashed ids, titles and marker: 63 inserted, 1 already present (commits 847477d, d990c51). After a checked dry run confirmed that the service account owned both calendars and that every event had a live, marked copy in the Time Log, both old calendars were deleted (1fcc2d7). The one-off scripts and workflow were then removed; they remain in git history. The `GCAL_SLEEP_CALENDAR_ID` and `GCAL_WORKOUTS_CALENDAR_ID` secrets are no longer read.
