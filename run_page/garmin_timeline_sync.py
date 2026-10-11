"""Mirror Garmin Activities and Sleep into the owner's LifeOS Time Log.

Nothing here is written to disk. Timeline Event identity is derived from
Garmin's own record identity, so the calendar is the only state and no
health data reaches any repository. See docs/garmin-timeline-sync-plan.md
and ADR 0010.
"""

import argparse
import asyncio
import datetime as dt
import hashlib
import json
import os
import sys
from dataclasses import dataclass

sys.path.insert(0, str(os.path.dirname(os.path.abspath(__file__))))

from timeline_calendar_client import OUTCOMES, TimelineCalendarClient  # noqa: E402

# Google accepts base32hex only: a-v and 0-9, length 5-1024, unique per
# calendar. A non-conforming id is rejected outright with
# "400 Invalid resource id value" rather than coerced. Lowercase hex is a
# subset, so a hash digest always conforms.
ID_ALPHABET = set("abcdefghijklmnopqrstuv0123456789")
ID_HEX_LENGTH = 32

SOURCE = "garmin"
ACTIVITY = "activity"
SLEEP = "sleep"

# The Source Marker. The Time Log is shared with hand-logged events, so the
# sync proves authorship through these private extended properties and never
# touches an event that lacks them.
MARKER = {"lifeos": "time-log/1", "source": SOURCE}

# LifeOS Area colour: Health is Google event colour 10 (Basil). An event
# without a colorId is reported as uncategorised, so one is always set.
DEFAULT_AREA_COLOR_ID = "10"
VALID_COLOR_IDS = {str(n) for n in range(1, 12)}

# Short, readable titles for the common Garmin activity types; anything else
# falls back to the type key in sentence case ("Strength training").
ACTIVITY_TITLES = {
    "running": "Run",
    "street_running": "Run",
    "track_running": "Track run",
    "treadmill_running": "Treadmill run",
    "trail_running": "Trail run",
    "indoor_running": "Indoor run",
    "virtual_run": "Virtual run",
    "cycling": "Ride",
    "road_biking": "Ride",
    "mountain_biking": "MTB ride",
    "gravel_cycling": "Gravel ride",
    "indoor_cycling": "Indoor ride",
    "virtual_ride": "Virtual ride",
    "walking": "Walk",
    "casual_walking": "Walk",
    "speed_walking": "Walk",
    "hiking": "Hike",
    "lap_swimming": "Pool swim",
    "open_water_swimming": "Open-water swim",
    "swimming": "Swim",
    "hiit": "HIIT",
    "yoga": "Yoga",
    "pilates": "Pilates",
}


@dataclass(frozen=True)
class TimelineEvent:
    """The allowlist boundary.

    The mapper reads named Garmin fields into this record and the calendar
    client accepts only this record. A raw Garmin response never reaches the
    calendar layer, so a field added by a future Garmin release cannot leak
    by default — it is simply not read.
    """

    event_id: str
    kind: str
    garmin_id: str
    title: str
    start_utc: str
    end_utc: str
    description: str
    mutable: bool
    color_id: str = DEFAULT_AREA_COLOR_ID

    def private_properties(self):
        return {**MARKER, "garmin_kind": self.kind, "garmin_id": self.garmin_id}

    def body(self):
        return {
            "summary": "Health",
            "description": f"{self.title}\n\n{self.description}",
            "start": {"dateTime": self.start_utc},
            "end": {"dateTime": self.end_utc},
            "colorId": self.color_id,
            # Time spent, not a commitment: never block free/busy, never ping.
            "transparency": "transparent",
            "reminders": {"useDefault": False},
            "extendedProperties": {"private": self.private_properties()},
        }

    def patch_body(self):
        # Activities are append-only: an existing one is never rewritten, so
        # there is nothing to patch. Sleep is last-sync-wins (ADR 0008).
        if not self.mutable:
            return None
        return self.body()


def conforming_id(event_id):
    if not 5 <= len(event_id) <= 1024:
        raise ValueError(f"Timeline Event id {event_id!r} has an invalid length")
    if set(event_id) - ID_ALPHABET:
        raise ValueError(f"Timeline Event id {event_id!r} is not base32hex")
    return event_id


def _hashed_id(kind, garmin_id):
    # Namespaced by source and kind, so a Garmin id can never collide with a
    # hand-logged event or with another source writing the same Time Log.
    key = f"{SOURCE}:{kind}:{garmin_id}"
    return conforming_id(hashlib.sha256(key.encode()).hexdigest()[:ID_HEX_LENGTH])


def activity_event_id(activity_id):
    return _hashed_id(ACTIVITY, str(activity_id).strip())


def sleep_event_id(calendar_date):
    return _hashed_id(SLEEP, str(calendar_date).strip())


def valid_color_id(color_id):
    color_id = str(color_id or DEFAULT_AREA_COLOR_ID).strip()
    if color_id not in VALID_COLOR_IDS:
        raise ValueError(f"Area colorId {color_id!r} is not a Google event colour")
    return color_id


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
    key = str(type_key or "activity").strip().lower()
    if key in ACTIVITY_TITLES:
        return ACTIVITY_TITLES[key]
    return key.replace("_", " ").capitalize()


def _line(label, value):
    return f"{label}: {value}" if value is not None else None


def activity_event(activity, color_id=DEFAULT_AREA_COLOR_ID):
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
        title = f"{type_name} {float(distance) / 1000:.1f} km"

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
        kind=ACTIVITY,
        garmin_id=str(activity_id).strip(),
        title=title,
        start_utc=rfc3339(start),
        end_utc=rfc3339(end),
        description="\n".join(line for line in lines if line),
        mutable=False,
        color_id=color_id,
    )


def sleep_event(payload, color_id=DEFAULT_AREA_COLOR_ID):
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

    # The score stays in the description: Time Log titles stay short.
    title = "Sleep"

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

    if end <= start:
        return None

    return TimelineEvent(
        event_id=sleep_event_id(calendar_date),
        kind=SLEEP,
        garmin_id=str(calendar_date).strip(),
        title=title,
        start_utc=rfc3339(start),
        end_utc=rfc3339(end),
        description="\n".join(line for line in lines if line),
        mutable=True,
        color_id=color_id,
    )


def window_dates(days, today=None):
    today = today or dt.datetime.now(dt.timezone.utc).date()
    return [today - dt.timedelta(days=offset) for offset in range(days)]


def check_sleep_canary(events, dates):
    """Detect a stalled Garmin sleep feed without rejecting a no-watch night.

    The most recent day is excluded: it may legitimately have no record yet
    at the time the job runs. A missing completed day is expected when the
    watch was not worn, so it is tolerated when Garmin has a record for the
    following day. A missing date *without* its following day's record is a
    leading-edge gap and still fails loudly rather than masking a stalled
    feed with an older, stale record. The one exception is the day before
    the most recent: its following day may simply not have synced yet, so
    that gap is undecidable until the next run, which catches a real stall.
    """
    if len(dates) < 2:
        return
    received_ids = {event.event_id for event in events}
    unexplained_dates = []
    for index, date in enumerate(dates[1:], start=1):
        if sleep_event_id(date) in received_ids:
            continue
        following_date = dates[index - 1]
        if sleep_event_id(following_date) in received_ids or index == 1:
            continue
        unexplained_dates.append(date.isoformat())

    if unexplained_dates:
        raise ValueError(
            "Missing Sleep records without a following-day record in the "
            f"{len(dates)}-day Sync Window: {', '.join(unexplained_dates)}. "
            "Garmin's response shape has probably changed; refusing to "
            "report success."
        )


async def collect(client, days, today=None, color_id=DEFAULT_AREA_COLOR_ID):
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
        event = activity_event(activity, color_id)
        if event:
            activity_events.append(event)

    sleep_events = []
    for date in dates:
        event = sleep_event(await client.get_sleep(date.isoformat()), color_id)
        if event:
            sleep_events.append(event)

    check_sleep_canary(sleep_events, dates)
    return activity_events + sleep_events


def write_events(events, calendar):
    counts = {outcome: 0 for outcome in OUTCOMES}
    for event in events:
        outcome = calendar.insert_or_patch(
            event.event_id, event.body(), event.patch_body(), MARKER
        )
        counts[outcome] += 1
    return counts


def preview(events):
    """One JSON line per event that would be written. No API is called."""
    lines = []
    for event in sorted(events, key=lambda e: e.start_utc):
        lines.append(
            json.dumps(
                {
                    "id": event.event_id,
                    "title": event.title,
                    "start": event.start_utc,
                    "end": event.end_utc,
                    "colorId": event.color_id,
                    "private": event.private_properties(),
                },
                ensure_ascii=False,
            )
        )
    return "\n".join(lines)


async def run(args):
    from garmin_timeline_client import GarminTimelineClient

    color_id = valid_color_id(os.getenv("TIME_LOG_AREA_COLOR_ID"))
    calendar = None
    if not args.dry_run:
        # Fail before the Garmin login, which is rate-limited per account.
        calendar = TimelineCalendarClient(
            os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"),
            os.getenv("TIME_LOG_CALENDAR_ID"),
        )

    client = GarminTimelineClient(
        tokenstore=os.getenv("GARMIN_TOKENS_JSON"),
        is_cn=args.is_cn,
        email=os.getenv("GARMIN_EMAIL"),
        password=os.getenv("GARMIN_PASSWORD"),
    )
    try:
        events = await collect(client, args.days, color_id=color_id)
    finally:
        await client.aclose()

    if args.dry_run:
        print(preview(events))
        print(f"Dry run over {args.days} day(s): {len(events)} event(s), none written")
        return

    counts = write_events(events, calendar)
    print(
        f"Timeline Sync over {args.days} day(s): "
        + ", ".join(f"{counts[outcome]} {outcome}" for outcome in OUTCOMES)
    )


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--is-cn", action="store_true")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the events that would be written; never call Google",
    )
    return parser


def main():
    asyncio.run(run(build_parser().parse_args()))


if __name__ == "__main__":
    main()
