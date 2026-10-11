# Write the Timeline into the LifeOS Time Log

The Timeline Sync now writes Activities and Sleep into one calendar: the owner's LifeOS Time Log, a Lyubishchev time ledger that the owner also fills by hand from a phone app and from Google Calendar. The two Timeline Calendars that the service account owned are no longer written to. They are left in place, untouched.

The Time Log has conventions of its own, and every Timeline Event follows them. Event colour is the LifeOS Area, and Sleep and Activities are Health (`colorId` 10, configurable through `TIME_LOG_AREA_COLOR_ID`). Events are timed and transparent, with `reminders.useDefault=false`. Titles are short and have no Project prefix ("Sleep", "Run 10.2 km", "Strength training"). A Source Marker goes in `extendedProperties.private`: `{lifeos: "time-log/1", source: "garmin", garmin_kind, garmin_id}`.

## Consequences

Event ids are now the first 32 lowercase hex characters of `sha256("garmin:<kind>:<garmin id>")`. They are still deterministic and still base32hex, but now namespaced by source, so they cannot collide with hand-logged events or with another source. Events in the old calendars used `a<activityId>` and `b<YYYYMMDD>`. Those ids are not reused.

Because the calendar is shared with hand-logged entries, a `409` is no longer patched blindly. The existing event is read first:

- if it lacks the Source Marker, it is never edited;
- if the owner deleted it (a tombstone), it stays deleted. This refines ADR 0006: a Time Log deletion is the owner's decision about their own ledger, not drift to undo;
- otherwise an Activity stays as it is (append-only), and Sleep is patched (ADR 0008).

Overlap with a hand-logged event is accepted, because Time Log coverage is measured by the union of events.

The service account no longer owns the target calendar. The owner owns the Time Log and shares it with the service account with "Make changes to events". This removes the single point of failure that ADR 0009 worked around with co-ownership. The scope narrows from `calendar` to `calendar.events`.
