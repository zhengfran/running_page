import importlib.util
import shutil
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

ROOT = Path(__file__).resolve().parents[1]


def load_db_module():
    spec = importlib.util.spec_from_file_location(
        "running_page_generator_db", ROOT / "run_page/generator/db.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_existing_database_is_backfilled_with_strava_identity(tmp_path):
    module = load_db_module()
    database = tmp_path / "data.db"
    shutil.copy(ROOT / "run_page/data.db", database)

    session = module.init_db(database)

    assert session.query(module.Activity).count() == 1065
    assert (
        session.query(module.Activity)
        .filter(module.Activity.source == "strava")
        .count()
        == 1065
    )
    assert (
        session.query(module.Activity)
        .filter(module.Activity.source_activity_id.is_(None))
        .count()
        == 0
    )


def test_provider_qualified_identity_is_unique(tmp_path):
    module = load_db_module()
    database = tmp_path / "data.db"
    session = module.init_db(database)
    values = {
        "source": "garmin",
        "source_activity_id": "42",
        "name": "Run",
        "distance": 1000,
        "type": "Run",
        "start_date": "2026-06-06 00:00:00+00:00",
        "start_date_local": "2026-06-06 08:00:00",
        "summary_polyline": "",
        "average_speed": 3.0,
    }
    session.add(module.Activity(run_id=-42, **values))
    session.commit()

    session.add(module.Activity(run_id=-43, **values))
    with pytest.raises(IntegrityError):
        session.commit()


def test_identity_migration_creates_unique_index(tmp_path):
    module = load_db_module()
    database = tmp_path / "legacy.db"
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE activities (run_id INTEGER PRIMARY KEY)")
    connection.execute("INSERT INTO activities(run_id) VALUES (7)")
    connection.commit()
    connection.close()

    module.init_db(database)
    connection = sqlite3.connect(database)
    row = connection.execute(
        "SELECT source, source_activity_id FROM activities WHERE run_id = 7"
    ).fetchone()
    indexes = connection.execute("PRAGMA index_list(activities)").fetchall()
    connection.close()

    assert row == ("strava", "7")
    assert "uq_activities_source_identity" in {index[1] for index in indexes}
