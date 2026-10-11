"""One-off: delete the two pre-ADR-0010 Timeline calendars after their migration.

Deletion is permanent, so it only happens when every check passes:

- the calendar is one of GCAL_WORKOUTS_CALENDAR_ID / GCAL_SLEEP_CALENDAR_ID,
  is not the Time Log, and is owned by this service account;
- every Timeline event in it has a live copy in the Time Log (the migration's
  hashed id, carrying the Garmin Source Marker).

Otherwise it deletes nothing and exits non-zero. --dry-run runs the checks only.
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from garmin_timeline_sync import MARKER  # noqa: E402
from migrate_timeline_to_time_log import convert, old_events  # noqa: E402

# calendars.delete needs the full scope; the daily sync keeps calendar.events.
SCOPES = ["https://www.googleapis.com/auth/calendar"]


def build(service_account_json):
    from google.oauth2 import service_account
    from googleapiclient.discovery import build as discovery_build

    credentials = service_account.Credentials.from_service_account_info(
        json.loads(service_account_json), scopes=SCOPES
    )
    return discovery_build(
        "calendar", "v3", credentials=credentials, cache_discovery=False
    )


def missing_from_time_log(service, old_calendar_id, time_log_id):
    """Old Timeline events with no live, marked copy in the Time Log (empty = safe)."""
    missing = []
    for item in old_events(service, old_calendar_id):
        event = convert(item)
        if event is None:
            if item.get("status") != "cancelled":
                missing.append(f"{item.get('id')} (not a Timeline event)")
            continue
        try:
            copy = (
                service.events()
                .get(calendarId=time_log_id, eventId=event.event_id)
                .execute()
            )
        except Exception:  # noqa: BLE001 - 404 and friends all mean "not safely copied"
            missing.append(item["id"])
            continue
        private = (copy.get("extendedProperties") or {}).get("private") or {}
        if copy.get("status") == "cancelled" or any(
            private.get(k) != v for k, v in MARKER.items()
        ):
            missing.append(item["id"])
    return missing


def check(service, calendar_id, time_log_id):
    """Return a list of reasons not to delete this calendar."""
    if calendar_id == time_log_id:
        return ["it is the Time Log"]
    role = (
        service.calendarList().get(calendarId=calendar_id).execute().get("accessRole")
    )
    problems = [] if role == "owner" else [f"service account is {role}, not owner"]
    missing = missing_from_time_log(service, calendar_id, time_log_id)
    if missing:
        problems.append(
            f"{len(missing)} event(s) not in the Time Log, e.g. {missing[:3]}"
        )
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="Run every check; delete nothing"
    )
    args = parser.parse_args(argv)

    time_log_id = os.environ["TIME_LOG_CALENDAR_ID"]
    service = build(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    targets = {
        name: os.getenv(name)
        for name in ("GCAL_WORKOUTS_CALENDAR_ID", "GCAL_SLEEP_CALENDAR_ID")
    }

    verdicts = {}
    for name, calendar_id in targets.items():
        if not calendar_id:
            print(f"{name}: not set; nothing to delete")
            continue
        summary = (
            service.calendars().get(calendarId=calendar_id).execute().get("summary")
        )
        problems = check(service, calendar_id, time_log_id)
        verdicts[name] = (calendar_id, problems)
        print(
            f"{name} ({summary!r}): "
            + ("safe to delete" if not problems else "KEEP: " + "; ".join(problems))
        )

    if any(problems for _, problems in verdicts.values()):
        print("Not deleting anything: at least one check failed.")
        sys.exit(1)
    if args.dry_run:
        print(f"Dry run: {len(verdicts)} calendar(s) would be deleted; nothing deleted")
        return
    for name, (calendar_id, _) in verdicts.items():
        service.calendars().delete(calendarId=calendar_id).execute()
        print(f"{name}: deleted")


if __name__ == "__main__":
    main()
