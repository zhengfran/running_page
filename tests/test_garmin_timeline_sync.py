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
    """An in-memory calendar keyed by event id; tombstones stay in place."""

    def __init__(self, existing=None):
        self.store = dict(existing or {})
        self.calls = []
        self._result = {}

    def insert(self, calendarId, body, sendUpdates):
        self.calls.append(("insert", body.get("id"), body))
        if body["id"] in self.store:
            raise FakeHttpError(409)
        self.store[body["id"]] = {**body, "status": "confirmed"}
        self._result = self.store[body["id"]]
        return self

    def get(self, calendarId, eventId):
        self.calls.append(("get", eventId, None))
        self._result = self.store[eventId]
        return self

    def patch(self, calendarId, eventId, body, sendUpdates):
        self.calls.append(("patch", eventId, body))
        self.store[eventId] = {**self.store[eventId], **body}
        self._result = self.store[eventId]
        return self

    def execute(self):
        return self._result

    def kinds(self):
        return [call[0] for call in self.calls]


class FakeHttpError(Exception):
    def __init__(self, status):
        super().__init__(f"HTTP {status}")
        self.resp = type("Resp", (), {"status": status})()


class StubService:
    def __init__(self, events):
        self._events = events

    def events(self):
        return self._events


def client_over(events):
    return calendar_client.TimelineCalendarClient(
        None, "time-log", service=StubService(events)
    )


def write(client, event):
    return client.insert_or_patch(
        event.event_id, event.body(), event.patch_body(), sync.MARKER
    )


# --- id derivation -------------------------------------------------------


def test_activity_and_sleep_ids_conform_and_cannot_collide():
    activity = sync.activity_event_id(12345678901)
    sleep = sync.sleep_event_id("2026-08-25")
    assert activity != sleep
    # The same Garmin number under the other kind is still a different id.
    assert sync.activity_event_id("2026-08-25") != sleep
    for event_id in (activity, sleep):
        assert set(event_id) <= sync.ID_ALPHABET
        assert 5 <= len(event_id) <= 1024


def test_ids_are_deterministic_and_pinned():
    # Pinned: changing the derivation would duplicate every event already
    # written to the Time Log.
    assert sync.activity_event_id(12345678901) == sync.activity_event_id(
        " 12345678901 "
    )
    assert sync.activity_event_id(12345678901) == "5a75670aee8daf017a0f717f5e81b498"


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
    assert set(body) == {
        "summary",
        "description",
        "start",
        "end",
        "colorId",
        "transparency",
        "reminders",
        "extendedProperties",
    }


# --- LifeOS Time Log conventions ----------------------------------------


@pytest.mark.parametrize(
    "event",
    [sync.activity_event(ACTIVITY), sync.sleep_event(SLEEP)],
    ids=["activity", "sleep"],
)
def test_body_follows_time_log_conventions(event):
    body = event.body()
    assert body["colorId"] == "10"  # Health / Basil
    assert body["transparency"] == "transparent"
    assert body["reminders"] == {"useDefault": False}
    # Timed, never all-day.
    assert "date" not in body["start"] and "date" not in body["end"]
    assert body["start"]["dateTime"].endswith("Z")
    assert body["summary"] == "Health"  # no Project selected
    assert body["description"] == f"{event.title}\n\n{event.description}"
    private = body["extendedProperties"]["private"]
    assert private["lifeos"] == "time-log/1"
    assert private["source"] == "garmin"
    assert private["garmin_kind"] == event.kind
    assert all(isinstance(value, str) for value in private.values())


def test_activity_marker_carries_the_garmin_id():
    private = sync.activity_event(ACTIVITY).private_properties()
    assert private["garmin_id"] == "12345678901"
    assert sync.sleep_event(SLEEP).private_properties()["garmin_id"] == "2026-08-25"


def test_area_color_is_configurable():
    assert sync.activity_event(ACTIVITY, color_id="9").body()["colorId"] == "9"
    assert sync.valid_color_id(None) == "10"
    assert sync.valid_color_id("") == "10"
    assert sync.valid_color_id(" 4 ") == "4"


@pytest.mark.parametrize("bad", ["0", "12", "basil", "10.0"])
def test_invalid_area_color_is_rejected(bad):
    with pytest.raises(ValueError):
        sync.valid_color_id(bad)


def test_calendar_id_is_required():
    with pytest.raises(ValueError):
        calendar_client.TimelineCalendarClient(None, "", service=object())


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
    assert sync.activity_event(ACTIVITY).title == "Run 10.2 km"


def test_activity_without_distance_falls_back_to_type_name():
    event = sync.activity_event(
        {**ACTIVITY, "distance": 0, "activityType": {"typeKey": "strength_training"}}
    )
    assert event.title == "Strength training"


@pytest.mark.parametrize(
    "type_key, title",
    [
        ("road_biking", "Ride 10.2 km"),
        ("lap_swimming", "Pool swim 10.2 km"),
        ("some_new_sport", "Some new sport 10.2 km"),
        (None, "Activity 10.2 km"),
    ],
)
def test_activity_titles_stay_short(type_key, title):
    event = sync.activity_event({**ACTIVITY, "activityType": {"typeKey": type_key}})
    assert event.title == title


def test_sleep_maps_epoch_millis_and_keeps_score_out_of_title():
    event = sync.sleep_event(SLEEP)
    assert event.title == "Sleep"
    assert "Score: 84 (GOOD)" in event.description
    assert event.start_utc.endswith("Z") and event.end_utc.endswith("Z")
    assert event.start_utc < event.end_utc


def test_sleep_with_non_positive_span_is_skipped():
    daily = {**SLEEP["dailySleepDTO"]}
    daily["sleepEndTimestampGMT"] = daily["sleepStartTimestampGMT"]
    assert sync.sleep_event({"dailySleepDTO": daily}) is None


def test_activity_crossing_midnight_keeps_exact_instants():
    event = sync.activity_event({**ACTIVITY, "startTimeGMT": "2026-08-25 15:30:00"})
    # 23:30 to 00:30 Singapore: one timed event, never split or all-day.
    assert event.start_utc == "2026-08-25T15:30:00Z"
    assert event.end_utc == "2026-08-25T16:30:00Z"


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
    outcome = write(client_over(events), sync.activity_event(ACTIVITY))
    assert outcome == calendar_client.INSERTED
    assert events.kinds() == ["insert"]


def test_rerun_is_idempotent_and_never_duplicates():
    events = StubEvents()
    client = client_over(events)
    batch = [sync.activity_event(ACTIVITY), sync.sleep_event(SLEEP)]
    first = sync.write_events(batch, client)
    second = sync.write_events(batch, client)
    assert first["inserted"] == 2
    assert second["inserted"] == 0
    assert second["unchanged"] == 1 and second["patched"] == 1
    assert len(events.store) == 2


def test_activity_conflict_is_append_only():
    event = sync.activity_event(ACTIVITY)
    events = StubEvents()
    client = client_over(events)
    write(client, event)
    changed = sync.activity_event({**ACTIVITY, "elapsedDuration": 4000.0})
    assert write(client, changed) == calendar_client.UNCHANGED
    assert "patch" not in events.kinds()
    assert events.store[event.event_id]["end"]["dateTime"] == "2026-08-25T07:30:00Z"


def test_sleep_conflict_patches_our_own_event_with_latest_content():
    event = sync.sleep_event(SLEEP)
    events = StubEvents()
    client = client_over(events)
    write(client, event)
    revised = {**SLEEP["dailySleepDTO"], "sleepEndTimestampGMT": 1761130200000}
    outcome = write(client, sync.sleep_event({"dailySleepDTO": revised}))
    assert outcome == calendar_client.PATCHED
    assert events.store[event.event_id]["end"]["dateTime"] == "2025-10-22T10:50:00Z"
    assert events.store[event.event_id]["colorId"] == "10"


def test_conflict_with_unmarked_event_is_never_edited():
    event = sync.sleep_event(SLEEP)
    hand_logged = {"id": event.event_id, "summary": "Sleep", "status": "confirmed"}
    events = StubEvents({event.event_id: hand_logged})
    outcome = write(client_over(events), event)
    assert outcome == calendar_client.SKIPPED_FOREIGN
    assert events.kinds() == ["insert", "get"]
    assert events.store[event.event_id] == hand_logged


def test_conflict_with_other_source_marker_is_never_edited():
    event = sync.sleep_event(SLEEP)
    other = {
        "id": event.event_id,
        "status": "confirmed",
        "extendedProperties": {
            "private": {"lifeos": "time-log/1", "source": "android"}
        },
    }
    events = StubEvents({event.event_id: other})
    assert write(client_over(events), event) == calendar_client.SKIPPED_FOREIGN
    assert "patch" not in events.kinds()


def test_event_deleted_by_the_owner_stays_deleted():
    event = sync.sleep_event(SLEEP)
    events = StubEvents()
    client = client_over(events)
    write(client, event)
    events.store[event.event_id]["status"] = "cancelled"
    assert write(client, event) == calendar_client.SKIPPED_DELETED
    assert "patch" not in events.kinds()
    assert events.store[event.event_id]["status"] == "cancelled"


def test_activity_patch_body_is_none_and_sleep_patch_carries_content():
    assert sync.activity_event(ACTIVITY).patch_body() is None
    patch = sync.sleep_event(SLEEP).patch_body()
    assert patch["summary"] == "Health"
    assert patch["description"].startswith("Sleep\n\n")
    assert patch["colorId"] == "10"
    assert "start" in patch and "end" in patch
    assert "status" not in patch  # a tombstone is never revived


def test_non_conflict_errors_are_not_swallowed():
    class Boom(StubEvents):
        def insert(self, calendarId, body, sendUpdates):
            raise FakeHttpError(500)

    with pytest.raises(FakeHttpError):
        client_over(Boom()).insert_or_patch("a1234567", {}, {}, sync.MARKER)


def test_preview_lists_events_without_a_calendar():
    lines = sync.preview([sync.sleep_event(SLEEP), sync.activity_event(ACTIVITY)])
    assert "Run 10.2 km" in lines and '"colorId": "10"' in lines


# --- canary --------------------------------------------------------------


def test_zero_sleep_records_in_the_window_fails_loudly():
    dates = sync.window_dates(7, dt.date(2026, 8, 25))
    with pytest.raises(ValueError, match="2026-08-19"):
        sync.check_sleep_canary([], dates)


def test_canary_rejects_missing_sleep_without_a_following_day_record():
    dates = sync.window_dates(7, dt.date(2026, 8, 25))
    stale = sync.sleep_event(
        {
            "dailySleepDTO": {
                **SLEEP["dailySleepDTO"],
                "calendarDate": "2026-08-19",
            }
        }
    )
    with pytest.raises(ValueError, match="2026-08-23"):
        sync.check_sleep_canary([stale], dates)


def test_canary_allows_the_last_two_days_missing_before_today_syncs():
    # A no-watch night followed by a run before today's record has synced.
    dates = sync.window_dates(7, dt.date(2026, 8, 25))
    events = [
        sync.sleep_event(
            {
                "dailySleepDTO": {
                    **SLEEP["dailySleepDTO"],
                    "calendarDate": date.isoformat(),
                }
            }
        )
        for date in dates[2:]
    ]
    sync.check_sleep_canary(events, dates)


def test_canary_catches_a_stall_on_the_following_run():
    dates = sync.window_dates(7, dt.date(2026, 8, 25))
    events = [
        sync.sleep_event(
            {
                "dailySleepDTO": {
                    **SLEEP["dailySleepDTO"],
                    "calendarDate": date.isoformat(),
                }
            }
        )
        for date in dates[3:]
    ]
    with pytest.raises(ValueError, match="2026-08-23"):
        sync.check_sleep_canary(events, dates)


def test_canary_allows_missing_sleep_when_the_following_day_is_present():
    dates = sync.window_dates(7, dt.date(2026, 8, 25))
    missing_date = dt.date(2026, 8, 23)
    events = [
        sync.sleep_event(
            {
                "dailySleepDTO": {
                    **SLEEP["dailySleepDTO"],
                    "calendarDate": date.isoformat(),
                }
            }
        )
        for date in dates
        if date != missing_date
    ]
    sync.check_sleep_canary(events, dates)


def test_canary_allows_only_the_most_recent_day_to_be_missing():
    dates = sync.window_dates(7, dt.date(2026, 8, 25))
    events = [
        sync.sleep_event(
            {
                "dailySleepDTO": {
                    **SLEEP["dailySleepDTO"],
                    "calendarDate": date.isoformat(),
                }
            }
        )
        for date in dates[1:]
    ]
    sync.check_sleep_canary(events, dates)


def test_single_day_window_is_exempt_from_the_canary():
    # The most recent day may legitimately have no record yet.
    sync.check_sleep_canary([], sync.window_dates(1, dt.date(2026, 8, 25)))


def test_window_dates_span_the_requested_days():
    dates = sync.window_dates(7, dt.date(2026, 8, 25))
    assert len(dates) == 7
    assert max(dates) == dt.date(2026, 8, 25)
    assert min(dates) == dt.date(2026, 8, 19)
