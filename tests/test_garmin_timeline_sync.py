import datetime as dt
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"run_page/{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


calendar_client = load("timeline_calendar_client")
sync = load("garmin_timeline_sync")


# A synthetic activity carrying fields that must NEVER reach the calendar.
ACTIVITY = {
    "activityId": 12345678901,
    "activityName": "Morning Run",
    "activityType": {"typeKey": "running"},
    "startTimeGMT": "2026-08-25 06:30:00",
    "startTimeLocal": "2026-08-25 14:30:00",
    "duration": 3500.0,
    "movingDuration": 3400.0,
    "elapsedDuration": 3600.0,
    "distance": 10200.0,
    "averageHR": 148,
    "maxHR": 171,
    "calories": 720,
    "elevationGain": 84.0,
    # Everything below is excluded by the allowlist.
    "locationName": "Marina Bay",
    "startLatitude": 1.2831,
    "startLongitude": 103.8607,
    "polyline": "ktjrFoemeU~IorGq}DeB",
    "ownerDisplayName": "Zhicheng",
}

SLEEP = {
    "dailySleepDTO": {
        "calendarDate": "2026-08-25",
        "sleepStartTimestampGMT": 1761100200000,
        "sleepEndTimestampGMT": 1761128400000,
        "sleepTimeSeconds": 28200,
        "deepSleepSeconds": 5400,
        "lightSleepSeconds": 16200,
        "remSleepSeconds": 5400,
        "awakeSleepSeconds": 1200,
        "napTimeSeconds": 0,
        "avgSleepHRV": 62.0,
        "avgSpO2": 96.0,
        "avgRespirationValue": 14.2,
        "sleepScores": {"overall": {"value": 84, "qualifierKey": "GOOD"}},
    }
}


class StubEvents:
    def __init__(self, taken=()):
        self.taken = set(taken)
        self.calls = []

    def insert(self, calendarId, body, sendUpdates):
        self.calls.append(("insert", body.get("id"), body))
        if body["id"] in self.taken:
            raise FakeHttpError(409)
        self.taken.add(body["id"])
        return self

    def patch(self, calendarId, eventId, body, sendUpdates):
        self.calls.append(("patch", eventId, body))
        return self

    def execute(self):
        return {}


class FakeHttpError(Exception):
    def __init__(self, status):
        super().__init__(f"HTTP {status}")
        self.resp = type("Resp", (), {"status": status})()


class StubService:
    def __init__(self, events):
        self._events = events

    def events(self):
        return self._events


# --- id derivation -------------------------------------------------------


def test_activity_and_sleep_ids_conform_and_cannot_collide():
    activity = sync.activity_event_id(12345678901)
    sleep = sync.sleep_event_id("2026-08-25")
    assert activity == "a12345678901"
    assert sleep == "b20260825"
    assert activity[0] != sleep[0]
    for event_id in (activity, sleep):
        assert set(event_id) <= sync.ID_ALPHABET
        assert 5 <= len(event_id) <= 1024


@pytest.mark.parametrize("bad", ["z123456", "a-123456", "aWXYZ123", "a1"])
def test_non_base32hex_ids_are_rejected(bad):
    with pytest.raises(ValueError):
        sync.conforming_id(bad)


# --- the allowlist -------------------------------------------------------


def test_activity_event_excludes_location_and_route_fields():
    event = sync.activity_event(ACTIVITY)
    blob = f"{event.title}\n{event.description}"
    for leaked in ("Marina Bay", "1.2831", "103.8607", "ktjrFoemeU", "Zhicheng"):
        assert leaked not in blob
    assert "locationName" not in blob


def test_timeline_event_body_carries_only_allowlisted_keys():
    body = sync.activity_event(ACTIVITY).body()
    assert set(body) == {"summary", "description", "start", "end"}


def test_sleep_event_excludes_nap_aggregate():
    # Naps are out of scope: a daily total has no span to record.
    event = sync.sleep_event(SLEEP)
    assert "nap" not in event.description.lower()


# --- mapping -------------------------------------------------------------


def test_activity_end_uses_elapsed_not_moving_duration():
    event = sync.activity_event(ACTIVITY)
    assert event.start_utc == "2026-08-25T06:30:00Z"
    # 3600s elapsed, not 3400s moving and not 3500s duration.
    assert event.end_utc == "2026-08-25T07:30:00Z"


def test_activity_title_is_composed():
    assert sync.activity_event(ACTIVITY).title == "Running · 10.2 km"


def test_activity_without_distance_falls_back_to_type_name():
    event = sync.activity_event(
        {**ACTIVITY, "distance": 0, "activityType": {"typeKey": "strength_training"}}
    )
    assert event.title == "Strength Training"


def test_sleep_maps_epoch_millis_and_carries_score_in_title():
    event = sync.sleep_event(SLEEP)
    assert event.title == "Sleep · 84"
    assert event.start_utc.endswith("Z") and event.end_utc.endswith("Z")
    assert event.start_utc < event.end_utc


def test_sleep_ignores_local_timestamps_and_uses_gmt():
    payload = {"dailySleepDTO": {**SLEEP["dailySleepDTO"]}}
    payload["dailySleepDTO"]["sleepStartTimestampLocal"] = 1
    payload["dailySleepDTO"]["sleepEndTimestampLocal"] = 2
    assert sync.sleep_event(payload).start_utc == sync.sleep_event(SLEEP).start_utc


def test_unplaceable_records_are_skipped():
    assert sync.activity_event({**ACTIVITY, "startTimeGMT": None}) is None
    assert (
        sync.activity_event({**ACTIVITY, "elapsedDuration": 0, "duration": 0}) is None
    )
    assert sync.sleep_event({"dailySleepDTO": {"calendarDate": "2026-08-25"}}) is None
    assert sync.sleep_event({}) is None


# --- write semantics -----------------------------------------------------


def test_insert_succeeds_when_id_is_free():
    events = StubEvents()
    client = calendar_client.TimelineCalendarClient(
        None, "cal", service=StubService(events)
    )
    event = sync.activity_event(ACTIVITY)
    outcome = client.insert_or_patch(event.event_id, event.body(), event.patch_body())
    assert outcome == calendar_client.INSERTED
    assert [call[0] for call in events.calls] == ["insert"]


def test_conflict_falls_through_to_patch():
    event = sync.activity_event(ACTIVITY)
    events = StubEvents(taken={event.event_id})
    client = calendar_client.TimelineCalendarClient(
        None, "cal", service=StubService(events)
    )
    outcome = client.insert_or_patch(event.event_id, event.body(), event.patch_body())
    assert outcome == calendar_client.PATCHED
    assert [call[0] for call in events.calls] == ["insert", "patch"]


def test_activity_patch_carries_status_only_so_append_only_holds():
    patch = sync.activity_event(ACTIVITY).patch_body()
    assert patch == {"status": "confirmed"}


def test_sleep_patch_carries_content_and_revives_tombstone():
    patch = sync.sleep_event(SLEEP).patch_body()
    assert patch["status"] == "confirmed"
    assert patch["summary"] == "Sleep · 84"
    assert "start" in patch and "end" in patch


def test_non_conflict_errors_are_not_swallowed():
    class Boom(StubEvents):
        def insert(self, calendarId, body, sendUpdates):
            raise FakeHttpError(500)

    client = calendar_client.TimelineCalendarClient(
        None, "cal", service=StubService(Boom())
    )
    with pytest.raises(FakeHttpError):
        client.insert_or_patch("a1234567", {}, {})


# --- canary --------------------------------------------------------------


def test_zero_sleep_records_in_the_window_fails_loudly():
    dates = sync.window_dates(7, dt.date(2026, 8, 25))
    with pytest.raises(ValueError, match="No Sleep records"):
        sync.check_sleep_canary([], dates)


def test_canary_passes_when_any_sleep_record_exists():
    dates = sync.window_dates(7, dt.date(2026, 8, 25))
    sync.check_sleep_canary([sync.sleep_event(SLEEP)], dates)


def test_single_day_window_is_exempt_from_the_canary():
    # The most recent day may legitimately have no record yet.
    sync.check_sleep_canary([], sync.window_dates(1, dt.date(2026, 8, 25)))


def test_window_dates_span_the_requested_days():
    dates = sync.window_dates(7, dt.date(2026, 8, 25))
    assert len(dates) == 7
    assert max(dates) == dt.date(2026, 8, 25)
    assert min(dates) == dt.date(2026, 8, 19)
