import asyncio
import importlib.util
import json
import sys
import types
import zipfile
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module():
    spec = importlib.util.spec_from_file_location(
        "garmin_publish", ROOT / "run_page/garmin_publish.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


garmin_publish = load_module()


def synthetic_fit_zip(content=b"synthetic-fit"):
    output = BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("123_ACTIVITY.fit", content)
    return output.getvalue()


def test_extracts_fit_from_garmin_zip():
    assert garmin_publish.extract_fit(synthetic_fit_zip()) == b"synthetic-fit"


def test_archive_entry_verifies_checksum_and_size(tmp_path):
    fit_path = tmp_path / "garmin/123.fit"
    fit_path.parent.mkdir()
    fit_path.write_bytes(b"synthetic-fit")
    manifest = {
        "version": 1,
        "activities": {
            "123": {
                "path": "garmin/123.fit",
                "sha256": garmin_publish.sha256_bytes(b"synthetic-fit"),
                "bytes": 13,
            }
        },
    }

    assert garmin_publish.verify_archive_entry(tmp_path, "123", manifest) == fit_path


def test_candidate_preserves_garmin_utc_local_time_and_title():
    candidate = garmin_publish.candidate_from_metadata(
        {
            "activityId": 123,
            "activityName": "Singapore Evening Run",
            "startTimeGMT": "2026-06-06 11:00:00",
            "startTimeLocal": "2026-06-06 19:00:00",
            "locationName": "Singapore",
        }
    )

    assert candidate.source_activity_id == "123"
    assert candidate.name == "Singapore Evening Run"
    assert candidate.start_utc == "2026-06-06T11:00:00+00:00"
    assert candidate.start_local == "2026-06-06 19:00:00"


def test_discovery_stops_after_page_crosses_cutover():
    pages = [
        [
            {
                "activityId": 3,
                "activityName": "New",
                "startTimeGMT": "2026-06-07 00:00:00",
                "startTimeLocal": "2026-06-07 08:00:00",
            },
            {
                "activityId": 2,
                "activityName": "Boundary",
                "startTimeGMT": "2026-06-05 11:01:14",
                "startTimeLocal": "2026-06-05 19:01:14",
            },
        ],
        [
            {
                "activityId": 1,
                "activityName": "Old",
                "startTimeGMT": "2026-06-01 00:00:00",
                "startTimeLocal": "2026-06-01 08:00:00",
            }
        ],
    ]

    class Client:
        def __init__(self):
            self.calls = 0

        async def get_activities(self, _offset, _limit):
            page = pages[self.calls]
            self.calls += 1
            return page

    client = Client()
    candidates = asyncio.run(
        garmin_publish.discover_candidates(
            client, garmin_publish.parse_utc(garmin_publish.DEFAULT_CUTOVER)
        )
    )

    assert [candidate.source_activity_id for candidate in candidates] == ["3"]
    assert client.calls == 1


def test_normalization_uses_garmin_identity_title_and_redacted_route(monkeypatch):
    track_module = types.ModuleType("gpxtrackposter.track")

    class Track:
        def load_fit(self, _path):
            self.start_time = object()
            self.moving_dict = {
                "distance": 5000,
                "moving_time": "moving",
                "elapsed_time": "elapsed",
                "average_speed": 3.2,
            }
            self.average_heartrate = 145
            self.polyline_str = "raw-route"

    track_module.Track = Track
    package = types.ModuleType("gpxtrackposter")
    monkeypatch.setitem(sys.modules, "gpxtrackposter", package)
    monkeypatch.setitem(sys.modules, "gpxtrackposter.track", track_module)

    class Activity:
        def __init__(self, **values):
            self.__dict__.update(values)

    candidate = garmin_publish.Candidate(
        source_activity_id="123",
        name="Evening Run",
        start_utc="2026-06-06T11:00:00+00:00",
        start_local="2026-06-06 19:00:00",
        location_name="Singapore",
    )
    activity = garmin_publish.normalized_activity(
        candidate, Path("synthetic.fit"), Activity, lambda _route: "redacted-route"
    )

    assert activity.run_id == -123
    assert activity.source == "garmin"
    assert activity.source_activity_id == "123"
    assert activity.name == "Evening Run"
    assert activity.start_date_local == "2026-06-06 19:00:00"
    assert activity.summary_polyline == "redacted-route"


def test_write_json_is_atomic_and_stable(tmp_path):
    path = tmp_path / "batch.json"
    garmin_publish.write_json(path, {"version": 1, "candidates": []})

    assert json.loads(path.read_text()) == {"version": 1, "candidates": []}
    assert not path.with_suffix(".json.tmp").exists()


def test_public_activity_list_excludes_near_zero_distance_rows():
    class Query:
        def __init__(self):
            self.filtered = False

        def filter(self, _condition):
            self.filtered = True
            return self

        def order_by(self, _column):
            return []

    class Session:
        def __init__(self):
            self.result = Query()

        def query(self, _activity):
            return self.result

    class Field:
        def __gt__(self, _value):
            return True

    class Activity:
        distance = Field()
        start_date_local = Field()

    session = Session()
    assert garmin_publish.activity_dicts(session, Activity) == []
    assert session.result.filtered is True
