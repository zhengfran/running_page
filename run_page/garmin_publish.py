"""Archive-first Garmin publication pipeline for this running page."""

import argparse
import asyncio
import datetime as dt
import hashlib
import json
import os
import sqlite3
import sys
import zipfile
from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path

SOURCE = "garmin"
DEFAULT_CUTOVER = "2026-06-05T11:01:14+00:00"
ARCHIVE_MANIFEST_VERSION = 1
BATCH_VERSION = 1
ROUTE_SANITIZATION_MARKER = "public_routes_redacted_v1"


@dataclass(frozen=True)
class Candidate:
    source_activity_id: str
    name: str
    start_utc: str
    start_local: str
    location_name: str = ""


def parse_utc(value):
    value = str(value).strip().replace(" ", "T")
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def normalize_local_time(value):
    value = str(value).strip().replace("T", " ")
    return value[:19]


def candidate_from_metadata(metadata):
    source_activity_id = str(metadata["activityId"])
    start_utc = parse_utc(metadata["startTimeGMT"])
    local_value = metadata.get("startTimeLocal") or metadata["startTimeGMT"]
    return Candidate(
        source_activity_id=source_activity_id,
        name=metadata.get("activityName") or "Run",
        start_utc=start_utc.isoformat(),
        start_local=normalize_local_time(local_value),
        location_name=metadata.get("locationName") or "",
    )


def load_json(path, default):
    path = Path(path)
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as file:
        json.dump(value, file, indent=2, sort_keys=True)
        file.write("\n")
    temporary.replace(path)


def sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def extract_fit(download):
    with zipfile.ZipFile(BytesIO(download)) as archive:
        names = [name for name in archive.namelist() if name.lower().endswith(".fit")]
        activity_names = [name for name in names if name.endswith("_ACTIVITY.fit")]
        selected = (
            activity_names[0] if activity_names else (names[0] if names else None)
        )
        if not selected:
            raise ValueError("Garmin activity export did not contain a FIT file")
        return archive.read(selected)


def load_archive_manifest(archive_dir):
    manifest = load_json(
        Path(archive_dir) / "manifest.json",
        {"version": ARCHIVE_MANIFEST_VERSION, "activities": {}},
    )
    if manifest.get("version") != ARCHIVE_MANIFEST_VERSION:
        raise ValueError("Unsupported FIT archive manifest version")
    manifest.setdefault("activities", {})
    return manifest


def verify_archive_entry(archive_dir, source_activity_id, manifest):
    entry = manifest["activities"].get(str(source_activity_id))
    if not entry:
        raise ValueError(f"FIT archive manifest is missing {source_activity_id}")
    path = Path(archive_dir) / entry["path"]
    content = path.read_bytes()
    if len(content) != entry["bytes"] or sha256_bytes(content) != entry["sha256"]:
        raise ValueError(f"FIT archive verification failed for {source_activity_id}")
    return path


def published_garmin_ids(db_path):
    try:
        connection = sqlite3.connect(db_path)
        rows = connection.execute(
            "SELECT source_activity_id FROM activities WHERE source = ?", (SOURCE,)
        )
        return {str(row[0]) for row in rows}
    except sqlite3.OperationalError:
        return set()
    finally:
        if "connection" in locals():
            connection.close()


async def discover_candidates(client, cutover):
    candidates = []
    offset = 0
    page_size = 100
    while True:
        page = await client.get_activities(offset, page_size)
        if not page:
            break

        page_times = []
        for metadata in page:
            candidate = candidate_from_metadata(metadata)
            start_utc = parse_utc(candidate.start_utc)
            page_times.append(start_utc)
            if start_utc > cutover:
                candidates.append(candidate)

        if page_times and min(page_times) <= cutover:
            break
        offset += page_size

    return sorted(candidates, key=lambda item: item.start_utc)


async def prepare_archive(args):
    secret = os.getenv("GARMIN_SECRET_STRING")
    if not secret:
        raise ValueError("GARMIN_SECRET_STRING is required")

    os.environ.setdefault("GARTH_TELEMETRY_ENABLED", "false")
    from garmin_sync import Garmin

    cutover = parse_utc(args.cutover)
    client = Garmin(secret, "GLOBAL", is_only_running=True)
    try:
        candidates = await discover_candidates(client, cutover)
        published_ids = published_garmin_ids(args.db)
        candidates = [
            candidate
            for candidate in candidates
            if candidate.source_activity_id not in published_ids
        ]

        archive_dir = Path(args.archive_dir)
        garmin_dir = archive_dir / "garmin"
        garmin_dir.mkdir(parents=True, exist_ok=True)
        manifest = load_archive_manifest(archive_dir)

        for candidate in candidates:
            source_activity_id = candidate.source_activity_id
            if source_activity_id in manifest["activities"]:
                verify_archive_entry(archive_dir, source_activity_id, manifest)
                continue

            download = await client.download_activity(source_activity_id, "fit")
            fit = extract_fit(download)
            relative_path = f"garmin/{source_activity_id}.fit"
            archive_path = archive_dir / relative_path
            archive_path.write_bytes(fit)
            manifest["activities"][source_activity_id] = {
                "path": relative_path,
                "sha256": sha256_bytes(fit),
                "bytes": len(fit),
            }

        write_json(archive_dir / "manifest.json", manifest)
        write_json(
            args.batch_file,
            {
                "version": BATCH_VERSION,
                "cutover": cutover.isoformat(),
                "candidates": [asdict(candidate) for candidate in candidates],
            },
        )
        print(f"Prepared {len(candidates)} Garmin Run(s)")
    finally:
        await client.req.aclose()


def load_batch(path):
    batch = load_json(path, None)
    if not batch or batch.get("version") != BATCH_VERSION:
        raise ValueError("Missing or unsupported Garmin publication batch")
    return batch


def sanitize_public_routes_once(session, Activity, filter_out):
    session.execute(
        __import__("sqlalchemy").text(
            "CREATE TABLE IF NOT EXISTS running_page_metadata "
            "(key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
    )
    marker = session.execute(
        __import__("sqlalchemy").text(
            "SELECT value FROM running_page_metadata WHERE key = :key"
        ),
        {"key": ROUTE_SANITIZATION_MARKER},
    ).scalar()
    if marker:
        return

    for activity in session.query(Activity).filter(Activity.summary_polyline != ""):
        activity.summary_polyline = filter_out(activity.summary_polyline) or ""

    session.execute(
        __import__("sqlalchemy").text(
            "INSERT INTO running_page_metadata(key, value) VALUES (:key, :value)"
        ),
        {"key": ROUTE_SANITIZATION_MARKER, "value": "1"},
    )


def compatibility_run_id(source_activity_id):
    return -int(source_activity_id)


def normalized_activity(candidate, fit_path, Activity, filter_out):
    from gpxtrackposter.track import Track

    track = Track()
    track.load_fit(str(fit_path))
    if track.start_time is None or not track.moving_dict:
        raise ValueError(f"Could not parse archived FIT {fit_path}")

    return Activity(
        run_id=compatibility_run_id(candidate.source_activity_id),
        source=SOURCE,
        source_activity_id=candidate.source_activity_id,
        name=candidate.name,
        distance=float(track.moving_dict["distance"]),
        moving_time=track.moving_dict["moving_time"],
        elapsed_time=track.moving_dict["elapsed_time"],
        type="Run",
        start_date=parse_utc(candidate.start_utc).strftime("%Y-%m-%d %H:%M:%S+00:00"),
        start_date_local=candidate.start_local,
        location_country=candidate.location_name,
        summary_polyline=filter_out(track.polyline_str) or "",
        average_heartrate=track.average_heartrate,
        average_speed=float(track.moving_dict["average_speed"]),
    )


def activity_dicts(session, Activity):
    activities = session.query(Activity).order_by(Activity.start_date_local)
    output = []
    streak = 0
    last_date = None
    for activity in activities:
        current_date = dt.datetime.strptime(
            activity.start_date_local, "%Y-%m-%d %H:%M:%S"
        ).date()
        if last_date is None:
            streak = 1
        elif current_date == last_date:
            pass
        elif current_date == last_date + dt.timedelta(days=1):
            streak += 1
        else:
            streak = 1
        activity.streak = streak
        last_date = current_date
        output.append(activity.to_dict())
    return output


def validate_publication(
    session, Activity, archive_dir, manifest, cutover, legacy_count
):
    strava_count = session.query(Activity).filter(Activity.source == "strava").count()
    if strava_count != legacy_count:
        raise ValueError(
            f"Expected {legacy_count} Legacy Activities, found {strava_count}"
        )

    garmin_activities = session.query(Activity).filter(Activity.source == SOURCE).all()
    for activity in garmin_activities:
        if activity.type != "Run":
            raise ValueError(
                f"Garmin Activity {activity.source_activity_id} is not a Run"
            )
        if parse_utc(activity.start_date) <= cutover:
            raise ValueError(
                f"Garmin Activity {activity.source_activity_id} crosses the boundary"
            )
        matching_starts = (
            session.query(Activity)
            .filter(Activity.start_date_local == activity.start_date_local)
            .count()
        )
        if matching_starts != 1:
            raise ValueError(f"Duplicate Garmin start time {activity.start_date_local}")
        verify_archive_entry(archive_dir, activity.source_activity_id, manifest)


def publish_batch(args):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from generator.db import Activity, init_db
    from polyline_processor import filter_out

    batch = load_batch(args.batch_file)
    cutover = parse_utc(batch["cutover"])
    archive_dir = Path(args.archive_dir)
    manifest = load_archive_manifest(archive_dir)
    session = init_db(args.db)

    try:
        sanitize_public_routes_once(session, Activity, filter_out)
        for value in batch["candidates"]:
            candidate = Candidate(**value)
            existing = (
                session.query(Activity)
                .filter_by(
                    source=SOURCE,
                    source_activity_id=candidate.source_activity_id,
                )
                .first()
            )
            if existing:
                continue
            fit_path = verify_archive_entry(
                archive_dir, candidate.source_activity_id, manifest
            )
            session.add(normalized_activity(candidate, fit_path, Activity, filter_out))

        session.flush()
        validate_publication(
            session,
            Activity,
            archive_dir,
            manifest,
            cutover,
            args.legacy_count,
        )
        activities = activity_dicts(session, Activity)
        session.commit()
        write_json(args.json, activities)
        print(f"Published {len(batch['candidates'])} Garmin Run(s)")
    except Exception:
        session.rollback()
        raise


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--archive-dir", required=True)
    prepare.add_argument("--batch-file", required=True)
    prepare.add_argument("--db", default="run_page/data.db")
    prepare.add_argument("--cutover", default=DEFAULT_CUTOVER)

    publish = subparsers.add_parser("publish")
    publish.add_argument("--archive-dir", required=True)
    publish.add_argument("--batch-file", required=True)
    publish.add_argument("--db", default="run_page/data.db")
    publish.add_argument("--json", default="src/static/activities.json")
    publish.add_argument("--legacy-count", type=int, default=1065)

    return parser


def main():
    args = build_parser().parse_args()
    if args.command == "prepare":
        asyncio.run(prepare_archive(args))
    elif args.command == "publish":
        publish_batch(args)


if __name__ == "__main__":
    main()
