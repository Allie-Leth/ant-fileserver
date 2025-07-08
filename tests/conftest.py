# ruff: noqa: I001,E402   # ignore “imports not at top” and “un-sorted import block”
# pylint: disable=import-outside-toplevel

"""Pytest fixtures for testing FirmwareService with moto and Flask app factory."""

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

# Allow importing app when tests run outside project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ruff: noqa: E402  ── imports below rely on sys.path tweak above
import app  # noqa: E402
from app import create_app  # noqa: E402
from app.blueprints.firmware.service import (  # noqa: E402
    FirmwareMetaData,
    FirmwareService,
)

_BUCKET = "firmware"


@pytest.fixture(autouse=True, scope="session")
def dummy_app_env():
    """Set environment variables needed for all tests."""
    os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
    os.environ.setdefault("STORAGE_ENDPOINT", "http://dummy")
    os.environ.setdefault("STORAGE_BUCKET", "firmware")
    os.environ.setdefault("STORAGE_ACCESS_KEY_ID", "x")
    os.environ.setdefault("STORAGE_SECRET_ACCESS_KEY", "y")
    os.environ.setdefault("STORAGE_REGION", "us-east-1")


@pytest.fixture(scope="function")
def svc():
    """Provide a FirmwareService connected to moto’s in-memory S3 with seeded data."""
    with mock_aws():
        s3_client = boto3.client("s3", region_name="us-east-1")  # renamed
        s3_client.create_bucket(Bucket=_BUCKET)

        for ver in ("1.0.0", "2.0.0"):
            prefix = f"releases/acme/widget/{ver}/"
            s3_client.put_object(
                Bucket=_BUCKET,
                Key=prefix + "metadata.json",
                Body=json.dumps(
                    {
                        "project": "acme",
                        "device_type": "widget",
                        "version": ver,
                        "checksum": "deadbeef",
                        "file_size": 1,
                        "release_date": "2025-01-01T00:00:00Z",
                    }
                ),
            )

        yield FirmwareService(
            endpoint_url=None,
            bucket=_BUCKET,
            access_key_id="x",
            secret_access_key="y",
            region="us-east-1",
        )


@pytest.fixture()
def fake_service(monkeypatch):
    """Inject a fake FirmwareService implementation into the app factory."""

    class _Fake:
        def __init__(self):
            self._store = {("acme", "widget"): ["1.0.0", "2.0.0"]}

        def list_firmware(self, project, device_type):
            """Return FirmwareMetaData objects for stored versions."""
            return [
                FirmwareMetaData(
                    project=project,
                    device_type=device_type,
                    version=v,
                    checksum="x",
                    file_size=1,
                    release_date=datetime(2025, 1, 1, tzinfo=UTC),
                )
                for v in self._store.get((project, device_type), [])
            ]

        # keep signature expected by real service; underscore marks “unused”
        def get_latest(self, project, device_type, _current_version=None):
            """Return newest FirmwareMetaData."""
            return self.list_firmware(project, device_type)[-1]

        def generate_presigned_url(self, project, device_type, version, **_):
            """Return dummy download URL."""
            return f"https://dummy/{project}/{device_type}/{version}/f.bin"

        def upload_firmware(self, project, device_type, payload):
            """Add new firmware version to in-memory store."""
            self._store.setdefault((project, device_type), []).append(
                payload["version"]
            )

    fake_svc = _Fake()
    monkeypatch.setattr(app, "FirmwareService")
    return fake_svc


@pytest.fixture()
def client(_fake_service):
    """Provide a Flask test client with the fake service injected."""
    app_ = create_app("development")  # DEBUG true simplifies traceback
    with app_.test_client() as c:
        for rule in app_.url_map.iter_rules():
            if rule.endpoint.startswith("firmware."):
                rule.defaults = rule.defaults or {}
                rule.defaults["svc"] = _fake_service
        yield c
