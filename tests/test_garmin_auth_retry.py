import importlib.util
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_module():
    sys.path.insert(0, str(ROOT / "run_page"))
    aiofiles = types.ModuleType("aiofiles")
    cloudscraper = types.ModuleType("cloudscraper")
    cloudscraper.CloudScraper = object
    garth = types.ModuleType("garth")
    httpx = types.ModuleType("httpx")
    httpx.Timeout = lambda *_args, **_kwargs: object()
    config = types.ModuleType("config")
    config.FOLDER_DICT = {}
    config.JSON_FILE = "activities.json"
    config.SQL_FILE = "data.db"
    config.config = lambda *_args, **_kwargs: ""
    garmin_device_adaptor = types.ModuleType("garmin_device_adaptor")
    garmin_device_adaptor.wrap_device_info = lambda file: file
    utils = types.ModuleType("utils")
    utils.make_activities_file = lambda *_args, **_kwargs: None

    monkey_modules = {
        "aiofiles": aiofiles,
        "cloudscraper": cloudscraper,
        "garth": garth,
        "httpx": httpx,
        "config": config,
        "garmin_device_adaptor": garmin_device_adaptor,
        "utils": utils,
    }
    for name, module in monkey_modules.items():
        sys.modules.setdefault(name, module)

    spec = importlib.util.spec_from_file_location(
        "garmin_sync", ROOT / "run_page/garmin_sync.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


garmin_sync = load_module()


def test_refresh_garmin_oauth2_retries_transient_failure():
    calls = []
    sleeps = []

    def refresh():
        calls.append("refresh")
        if len(calls) < 3:
            raise ValueError("non-json response")

    garmin_sync.refresh_garmin_oauth2(
        refresh,
        max_attempts=3,
        retry_delay_seconds=0.5,
        sleep_func=sleeps.append,
    )

    assert calls == ["refresh", "refresh", "refresh"]
    assert sleeps == [0.5, 1.0]


def test_refresh_garmin_oauth2_reports_secret_regeneration_after_retries():
    def refresh():
        raise ValueError("non-json response")

    with pytest.raises(garmin_sync.GarminConnectConnectionError) as exc_info:
        garmin_sync.refresh_garmin_oauth2(
            refresh,
            max_attempts=2,
            retry_delay_seconds=0,
            sleep_func=lambda _seconds: None,
        )

    assert "GARMIN_SECRET_STRING" in str(exc_info.value)
