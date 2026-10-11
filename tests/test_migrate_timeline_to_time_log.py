import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "run_page"))


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"run_page/{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


migrate = load("migrate_timeline_to_time_log")
sync = sys.modules["garmin_timeline_sync"]


def test_old_activity_keeps_its_garmin_identity_and_gets_the_time_log_format():
    old = {
        "id": "a12345678901",
        "summary": "Running · 10.2 km",
        "description": "Distance: 10.20 km",
        "start": {"dateTime": "2026-08-25T14:30:00+08:00"},
        "end": {"dateTime": "2026-08-25T15:30:00+08:00"},
    }
    event = migrate.convert(old)
    assert event.event_id == sync.activity_event_id(
        12345678901
    )  # same id the daily sync uses
    assert (event.title, event.start_utc, event.end_utc) == (
        "Run 10.2 km",
        "2026-08-25T06:30:00Z",
        "2026-08-25T07:30:00Z",
    )
    body = event.body()
    assert body["colorId"] == "10" and body["transparency"] == "transparent"
    assert body["extendedProperties"]["private"] == {
        **sync.MARKER,
        "garmin_kind": "activity",
        "garmin_id": "12345678901",
    }


def test_old_sleep_moves_its_score_into_the_description():
    old = {
        "id": "b20260825",
        "summary": "Sleep · 82",
        "description": "Asleep: 7h 10m",
        "start": {"dateTime": "2026-08-24T15:40:00Z"},
        "end": {"dateTime": "2026-08-24T23:05:00Z"},
    }
    event = migrate.convert(old, color_id="4")
    assert event.event_id == sync.sleep_event_id("2026-08-25")
    assert (event.title, event.description, event.color_id) == (
        "Sleep",
        "Asleep: 7h 10m\nScore: 82",
        "4",
    )


def test_foreign_cancelled_and_all_day_events_are_skipped():
    timed = {
        "start": {"dateTime": "2026-08-25T06:30:00Z"},
        "end": {"dateTime": "2026-08-25T07:00:00Z"},
    }
    assert migrate.convert({"id": "handmade123", **timed}) is None
    assert migrate.convert({"id": "a1", "status": "cancelled", **timed}) is None
    assert (
        migrate.convert(
            {
                "id": "b20260825",
                "start": {"date": "2026-08-25"},
                "end": {"date": "2026-08-26"},
            }
        )
        is None
    )


class FakeCalendar:
    def __init__(self):
        self.calls = []

    def insert_or_patch(self, event_id, body, patch_body, marker):
        self.calls.append(patch_body)
        return "inserted" if event_id != "taken" else "unchanged"


def test_migration_never_patches_existing_events():
    old = {
        "id": "b20260825",
        "summary": "Sleep",
        "start": {"dateTime": "2026-08-24T15:40:00Z"},
        "end": {"dateTime": "2026-08-24T23:05:00Z"},
    }
    fake = FakeCalendar()
    counts = migrate.migrate([migrate.convert(old)], fake)
    assert fake.calls == [None] and counts["inserted"] == 1


def test_old_activity_titles_become_the_daily_sync_titles():
    assert migrate.activity_title("Running · 10.2 km") == "Run 10.2 km"
    assert migrate.activity_title("Strength Training") == "Strength training"
    assert migrate.activity_title("Cycling · 32.5 km") == "Ride 32.5 km"


deleter = load("delete_old_timeline_calendars")


class _Call:
    def __init__(self, value):
        self.value = value

    def execute(self):
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


class FakeService:
    """Old calendar 'old' holds one sleep; the Time Log holds what `copies` says."""

    def __init__(self, copies, role="owner"):
        self.copies, self.role = copies, role

    def events(self):
        service = self

        class Events:
            def list(self, calendarId, **_):
                return _Call(
                    {
                        "items": [
                            {
                                "id": "b20260825",
                                "summary": "Sleep",
                                "start": {"dateTime": "2026-08-24T15:40:00Z"},
                                "end": {"dateTime": "2026-08-24T23:05:00Z"},
                            }
                        ]
                    }
                )

            def get(self, calendarId, eventId):
                return _Call(service.copies.get(eventId, LookupError("404")))

        return Events()

    def calendarList(self):
        service = self

        class CalendarList:
            def get(self, calendarId):
                return _Call({"accessRole": service.role})

        return CalendarList()


SLEEP_ID = sync.sleep_event_id("2026-08-25")
MARKED = {"status": "confirmed", "extendedProperties": {"private": dict(sync.MARKER)}}


def test_deletion_is_allowed_only_when_every_event_is_safely_copied():
    assert deleter.check(FakeService({SLEEP_ID: MARKED}), "old", "timelog") == []
    assert "not in the Time Log" in deleter.check(FakeService({}), "old", "timelog")[0]
    unmarked = {"status": "confirmed", "extendedProperties": {"private": {}}}
    assert deleter.check(FakeService({SLEEP_ID: unmarked}), "old", "timelog")
    assert deleter.check(
        FakeService({SLEEP_ID: {**MARKED, "status": "cancelled"}}), "old", "timelog"
    )


def test_never_deletes_the_time_log_or_a_calendar_it_does_not_own():
    assert deleter.check(FakeService({SLEEP_ID: MARKED}), "timelog", "timelog") == [
        "it is the Time Log"
    ]
    assert deleter.check(
        FakeService({SLEEP_ID: MARKED}, role="writer"), "old", "timelog"
    ) == ["service account is writer, not owner"]
