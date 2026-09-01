"""Mirror Garmin Activities and Sleep onto private Timeline Calendars.

Nothing here is written to disk. Timeline Event identity is derived from
Garmin's own record identity, so the calendar is the only state and no
health data reaches any repository. See docs/garmin-timeline-sync-plan.md.
"""

import argparse
import asyncio
import datetime as dt
import os
import sys
from dataclasses import dataclass

sys.path.insert(0, str(os.path.dirname(os.path.abspath(__file__))))

from timeline_calendar_client import TimelineCalendarClient  # noqa: E402

# Google accepts base32hex only: a-v and 0-9, length 5-1024, unique per
# calendar. A non-conforming id is rejected outright with
# "400 Invalid resource id value" rather than coerced.
ID_ALPHABET = set("abcdefghijklmnopqrstuv0123456789")
ACTIVITY_TAG = "a"
SLEEP_TAG = "b"

WORKOUTS = "workouts"
SLEEP = "sleep"


@dataclass(frozen=True)
class TimelineEvent:
    """The allowlist boundary.

    The mapper reads named Garmin fields into this record and the calendar
    client accepts only this record. A raw Garmin response never reaches the
    calendar layer, so a field added by a future Garmin release cannot leak
    by default — it is simply not read.
    """

    event_id: str
    calendar: str
    title: str
    start_utc: str
    end_utc: str
    description: str
    mutable: bool

    def body(self):
        return {
            "summary": self.title,
            "description": self.description,
            "start": {"dateTime": self.start_utc},
            "end": {"dateTime": self.end_utc},
        }

    def patch_body(self):
        # Activities are append-only: only status is written, so a tombstone
        # is revived without rewriting content. Sleep is last-sync-wins.
        if not self.mutable:
            return {"status": "confirmed"}
        return {**self.body(), "status": "confirmed"}


def conforming_id(event_id):
    if not 5 <= len(event_id) <= 1024:
        raise ValueError(f"Timeline Event id {event_id!r} has an invalid length")
    if set(event_id) - ID_ALPHABET:
        raise ValueError(f"Timeline Event id {event_id!r} is not base32hex")
    return event_id


def activity_event_id(activity_id):
    return conforming_id(ACTIVITY_TAG + str(activity_id).strip())


def sleep_event_id(calendar_date):
    return conforming_id(SLEEP_TAG + str(calendar_date).replace("-", "").strip())


def rfc3339(moment):
    return moment.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_garmin_gmt(value):
    """Garmin returns activity times as strings; the separator varies."""
    text = str(value).strip().replace("T", " ")
    if text.endswith("Z"):
        text = text[:-1].strip()
    parsed = dt.datetime.strptime(text[:19], "%Y-%m-%d %H:%M:%S")
    return parsed.replace(tzinfo=dt.timezone.utc)


def from_epoch_millis(value):
    return dt.datetime.fromtimestamp(int(value) / 1000, tz=dt.timezone.utc)


def humanize_seconds(seconds):
    total = int(round(float(seconds)))
    hours, remainder = divmod(total, 3600)
    minutes = remainder // 60
    return f"{hours}h {minutes:02d}m" if hours else f"{minutes}m"


def pretty_type(type_key):
    return str(type_key or "activity").replace("_", " ").title()


def _line(label, value):
    return f"{label}: {value}" if value is not None else None


def activity_event(activity):
    """Map one Garmin activity. Returns None when it cannot be placed in time."""
    activity_id = activity.get("activityId")
    start_raw = activity.get("startTimeGMT")
    if activity_id is None or not start_raw:
        return None

    # elapsedDuration, not movingDuration: a calendar block means time
    # occupied, and movingDuration would under-report a run with long pauses.
    seconds = activity.get("elapsedDuration") or activity.get("duration")
    if not seconds:
        return None

    start = parse_garmin_gmt(start_raw)
    end = start + dt.timedelta(seconds=float(seconds))

    type_name = pretty_type((activity.get("activityType") or {}).get("typeKey"))
    distance = activity.get("distance")
    title = type_name
    if distance:
        title = f"{type_name} · {float(distance) / 1000:.1f} km"

    moving = activity.get("movingDuration")
    lines = [
        _line("Distance", f"{float(distance) / 1000:.2f} km" if distance else None),
        _line("Elapsed", humanize_seconds(seconds)),
        _line("Moving", humanize_seconds(moving) if moving else None),
        _line("Avg HR", activity.get("averageHR")),
        _line("Max HR", activity.get("maxHR")),
        _line("Calories", activity.get("calories")),
        _line(
            "Elevation gain",
            (
                f"{float(activity['elevationGain']):.0f} m"
                if activity.get("elevationGain")
                else None
            ),
        ),
    ]

    return TimelineEvent(
        event_id=activity_event_id(activity_id),
        calendar=WORKOUTS,
        title=title,
        start_utc=rfc3339(start),
        end_utc=rfc3339(end),
        description="\n".join(line for line in lines if line),
        mutable=False,
    )


def sleep_event(payload):
    """Map one day of Garmin sleep. Returns None when there is no sleep."""
    daily = (payload or {}).get("dailySleepDTO") or {}
    start_raw = daily.get("sleepStartTimestampGMT")
    end_raw = daily.get("sleepEndTimestampGMT")
    calendar_date = daily.get("calendarDate")
    if not start_raw or not end_raw or not calendar_date:
        return None

    # The *Local fields are double-offset for CN and UTC+8 accounts, per the
    # library's own docstring. Always work from *GMT.
    start = from_epoch_millis(start_raw)
    end = from_epoch_millis(end_raw)

    scores = daily.get("sleepScores") or {}
    overall = scores.get("overall") or {}
    score = overall.get("value")

    title = f"Sleep · {score}" if score is not None else "Sleep"

    def stage(label, key):
        value = daily.get(key)
        return _line(label, humanize_seconds(value)) if value else None

    lines = [
        (
            _line("Asleep", humanize_seconds(daily["sleepTimeSeconds"]))
            if daily.get("sleepTimeSeconds")
            else None
        ),
        stage("Deep", "deepSleepSeconds"),
        stage("Light", "lightSleepSeconds"),
        stage("REM", "remSleepSeconds"),
        stage("Awake", "awakeSleepSeconds"),
        _line("Score", f"{score} ({overall.get('qualifierKey')})" if score else None),
        _line("Avg HRV", daily.get("avgSleepHRV")),
        _line("Avg SpO2", daily.get("avgSpO2")),
        _line("Avg respiration", daily.get("avgRespirationValue")),
    ]

    return TimelineEvent(
        event_id=sleep_event_id(calendar_date),
        calendar=SLEEP,
        title=title,
        start_utc=rfc3339(start),
        end_utc=rfc3339(end),
        description="\n".join(line for line in lines if line),
        mutable=True,
    )


def window_dates(days, today=None):
    today = today or dt.datetime.now(dt.timezone.utc).date()
    return [today - dt.timedelta(days=offset) for offset in range(days)]


def check_sleep_canary(events, dates):
    """Require every completed day in the window to have a Sleep record.

    The most recent day is excluded: it may legitimately have no record yet
    at the time the job runs. Checking only for *any* record lets a stale
    Garmin response make a run look healthy while newer days stop syncing.
    """
    if len(dates) < 2:
        return
    expected_ids = {sleep_event_id(date) for date in dates[1:]}
    received_ids = {event.event_id for event in events}
    missing_ids = expected_ids - received_ids
    if missing_ids:
        missing_dates = sorted(
            f"{event_id[1:5]}-{event_id[5:7]}-{event_id[7:9]}"
            for event_id in missing_ids
        )
        raise ValueError(
            "Missing Sleep records for completed day(s) in the "
            f"{len(dates)}-day Sync Window: {', '.join(missing_dates)}. "
            "Garmin's response shape has probably changed; refusing to "
            "report success."
        )


async def collect(client, days, today=None):
    dates = window_dates(days, today)
    earliest = min(dates)

    activities = []
    start = 0
    while True:
        batch = await client.get_activities(start=start, limit=100)
        if not batch:
            break
        activities.extend(batch)
        oldest = batch[-1].get("startTimeGMT")
        if not oldest or parse_garmin_gmt(oldest).date() < earliest:
            break
        start += len(batch)

    activity_events = []
    for activity in activities:
        start_raw = activity.get("startTimeGMT")
        if not start_raw or parse_garmin_gmt(start_raw).date() < earliest:
            continue
        event = activity_event(activity)
        if event:
            activity_events.append(event)

    sleep_events = []
    for date in dates:
        event = sleep_event(await client.get_sleep(date.isoformat()))
        if event:
            sleep_events.append(event)

    check_sleep_canary(sleep_events, dates)
    return activity_events + sleep_events


def write_events(events, calendars):
    counts = {"inserted": 0, "patched": 0}
    for event in events:
        outcome = calendars[event.calendar].insert_or_patch(
            event.event_id, event.body(), event.patch_body()
        )
        counts[outcome] += 1
    return counts


async def run(args):
    from garmin_timeline_client import GarminTimelineClient

    client = GarminTimelineClient(
        tokenstore=os.getenv("GARMIN_TOKENS_JSON"),
        is_cn=args.is_cn,
        email=os.getenv("GARMIN_EMAIL"),
        password=os.getenv("GARMIN_PASSWORD"),
    )
    try:
        events = await collect(client, args.days)
    finally:
        await client.aclose()

    service_account_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    calendars = {
        WORKOUTS: TimelineCalendarClient(
            service_account_json, os.getenv("GCAL_WORKOUTS_CALENDAR_ID")
        ),
        SLEEP: TimelineCalendarClient(
            service_account_json, os.getenv("GCAL_SLEEP_CALENDAR_ID")
        ),
    }
    counts = write_events(events, calendars)
    print(
        f"Timeline Sync over {args.days} day(s): "
        f"{counts['inserted']} inserted, {counts['patched']} patched"
    )


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--is-cn", action="store_true")
    return parser


def main():
    asyncio.run(run(build_parser().parse_args()))


if __name__ == "__main__":
    main()
