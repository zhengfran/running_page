import asyncio
import importlib.util
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_module():
    spec = importlib.util.spec_from_file_location(
        "garmin_publication_client",
        ROOT / "run_page/garmin_publication_client.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeGarmin:
    class ActivityDownloadFormat:
        ORIGINAL = "original"

    instances = []

    def __init__(self, email=None, password=None, is_cn=False):
        self.email = email
        self.password = password
        self.is_cn = is_cn
        self.login_tokenstore = None
        FakeGarmin.instances.append(self)

    def login(self, tokenstore=None):
        self.login_tokenstore = tokenstore
        return None, None

    def get_activities(self, start=0, limit=20, activitytype=None):
        return [
            {"start": start, "limit": limit, "activitytype": activitytype},
        ]

    def download_activity(self, activity_id, dl_fmt):
        return f"{activity_id}:{dl_fmt}".encode()


@pytest.fixture(autouse=True)
def fake_garminconnect(monkeypatch):
    FakeGarmin.instances = []
    garminconnect = types.ModuleType("garminconnect")
    garminconnect.Garmin = FakeGarmin
    monkeypatch.setitem(sys.modules, "garminconnect", garminconnect)


def test_publication_client_loads_json_tokenstore_from_secret_string():
    module = load_module()
    tokenstore = (
        '{"di_token":"access","di_refresh_token":"refresh","di_client_id":"client"}'
    )

    client = module.GarminPublicationClient(tokenstore)

    tokenstore_path = Path(FakeGarmin.instances[0].login_tokenstore)
    assert tokenstore_path.is_dir()
    assert (tokenstore_path / "garmin_tokens.json").read_text() == tokenstore

    asyncio.run(client.aclose())
    assert not tokenstore_path.exists()


def test_publication_client_fetches_running_activities():
    module = load_module()
    client = module.GarminPublicationClient("/tmp/tokenstore")

    activities = asyncio.run(client.get_activities(5, 10))

    assert activities == [{"start": 5, "limit": 10, "activitytype": "running"}]


def test_publication_client_downloads_original_fit_zip():
    module = load_module()
    client = module.GarminPublicationClient("/tmp/tokenstore")

    download = asyncio.run(client.download_activity("123", "fit"))

    assert download == b"123:original"


def test_publication_client_rejects_non_fit_downloads():
    module = load_module()
    client = module.GarminPublicationClient("/tmp/tokenstore")

    with pytest.raises(ValueError, match="FIT"):
        asyncio.run(client.download_activity("123", "gpx"))


def test_publication_client_forwards_credentials_for_token_self_heal():
    module = load_module()

    module.GarminPublicationClient(
        "/tmp/tokenstore", email="runner@example.com", password="hunter2"
    )

    assert FakeGarmin.instances[0].email == "runner@example.com"
    assert FakeGarmin.instances[0].password == "hunter2"


def test_publication_client_defaults_credentials_to_none():
    module = load_module()

    module.GarminPublicationClient("/tmp/tokenstore")

    assert FakeGarmin.instances[0].email is None
    assert FakeGarmin.instances[0].password is None
