"""One-off: copy the old Timeline Calendars into the LifeOS Time Log (ADR 0010).

Before ADR 0010 the sync wrote Activities to GCAL_WORKOUTS_CALENDAR_ID and
Sleep to GCAL_SLEEP_CALENDAR_ID, with ids `a<activityId>` and `b<YYYYMMDD>`.
This rebuilds each of those events in the Time Log format (hashed id, Area
colour, Source Marker, short title) and inserts it into TIME_LOG_CALENDAR_ID.

It never overwrites: an id already in the Time Log (the daily sync got there
first, or the owner deleted it) is left exactly as it is. It never deletes
anything; the old calendars stay as an archive until the owner removes them.
Events whose ids don't follow the old scheme are reported and skipped.
"""

import argparse
import datetime as dt
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from garmin_timeline_sync import (  # noqa: E402
    ACTIVITY,
    DEFAULT_AREA_COLOR_ID,
    MARKER,
    SLEEP,
    TimelineEvent,
    activity_event_id,
    pretty_type,
    rfc3339,
    sleep_event_id,
    valid_color_id,
)
from timeline_calendar_client import OUTCOMES, TimelineCalendarClient  # noqa: E402

OLD_ACTIVITY = re.compile(r"^a(\d+)$")
OLD_SLEEP = re.compile(r"^b(\d{4})(\d{2})(\d{2})$")
OLD_SLEEP_TITLE = re.compile(r"^Sleep\s*·\s*(\d+)\s*$")
OLD_ACTIVITY_TITLE = re.compile(r"^(?P<type>.+?)(?:\s*·\s*(?P<km>\d+(?:\.\d+)?) km)?$")


def activity_title(old_title):
    """'Running · 10.2 km' (old: the type key in title case) -> 'Run 10.2 km', as the daily sync writes it."""
    match = OLD_ACTIVITY_TITLE.match(old_title.strip())
    if not match:
        return old_title.strip() or "Workout"
    name = pretty_type(match.group("type").replace(" ", "_"))
    return f"{name} {match.group('km')} km" if match.group("km") else name


def _utc(when):
    return rfc3339(dt.datetime.fromisoformat(when.replace("Z", "+00:00")))


def convert(old, color_id=DEFAULT_AREA_COLOR_ID):
    """Rebuild one old Timeline event, or return None when it isn't one of ours."""
    start = (old.get("start") or {}).get("dateTime")
    end = (old.get("end") or {}).get("dateTime")
    if old.get("status") == "cancelled" or not start or not end:
        return None
    title = (old.get("summary") or "").strip()
    description = (old.get("description") or "").strip()

    if match := OLD_ACTIVITY.match(old.get("id", "")):
        garmin_id = match.group(1)
        return TimelineEvent(
            event_id=activity_event_id(garmin_id),
            kind=ACTIVITY,
            garmin_id=garmin_id,
            title=activity_title(title) if title else "Workout",
            start_utc=_utc(start),
            end_utc=_utc(end),
            description=description,
            mutable=False,
            color_id=color_id,
        )
    if match := OLD_SLEEP.match(old.get("id", "")):
        calendar_date = "-".join(match.groups())
        score = OLD_SLEEP_TITLE.match(title)
        if score and "Score:" not in description:
            # The old title carried the score; Time Log titles stay short.
            description = "\n".join(
                filter(None, [description, f"Score: {score.group(1)}"])
            )
        return TimelineEvent(
            event_id=sleep_event_id(calendar_date),
            kind=SLEEP,
            garmin_id=calendar_date,
            title="Sleep",
            start_utc=_utc(start),
            end_utc=_utc(end),
            description=description,
            mutable=True,
            color_id=color_id,
        )
    return None


def old_events(service, calendar_id):
    items, page = [], None
    while True:
        response = (
            service.events()
            .list(
                calendarId=calendar_id,
                singleEvents=True,
                maxResults=2500,
                pageToken=page,
            )
            .execute()
        )
        items += response.get("items", [])
        page = response.get("nextPageToken")
        if not page:
            return items


def migrate(events, calendar):
    """Insert only; an existing id (newer sync data, or owner-deleted) is never overwritten."""
    counts = {outcome: 0 for outcome in OUTCOMES}
    for event in events:
        counts[
            calendar.insert_or_patch(event.event_id, event.body(), None, MARKER)
        ] += 1
    return counts


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="Read and convert only; write nothing"
    )
    args = parser.parse_args(argv)

    color_id = valid_color_id(os.getenv("TIME_LOG_AREA_COLOR_ID"))
    calendar = TimelineCalendarClient(
        os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"), os.getenv("TIME_LOG_CALENDAR_ID")
    )
    service = calendar._service

    converted, skipped = [], 0
    for name in ("GCAL_WORKOUTS_CALENDAR_ID", "GCAL_SLEEP_CALENDAR_ID"):
        source = os.getenv(name)
        if not source:
            print(f"{name} is not set; skipping that calendar")
            continue
        items = old_events(service, source)
        found = [
            event for event in (convert(item, color_id) for item in items) if event
        ]
        skipped += len(items) - len(found)
        converted += found
        print(f"{name}: {len(items)} event(s) read, {len(found)} convertible")

    converted.sort(key=lambda event: event.start_utc)
    if converted:
        print(f"Range: {converted[0].start_utc} .. {converted[-1].end_utc}")
    for event in converted[:3] + converted[-3:]:
        print(f"  {event.start_utc}  {event.title}  -> {event.event_id}")

    if args.dry_run:
        print(
            f"Dry run: {len(converted)} event(s) would be copied, {skipped} skipped; nothing written"
        )
        return
    counts = migrate(converted, calendar)
    print(
        f"Migration: {skipped} skipped (not Timeline events), "
        + ", ".join(f"{counts[outcome]} {outcome}" for outcome in OUTCOMES)
    )


if __name__ == "__main__":
    main()
