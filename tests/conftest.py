# ruff: noqa: I001,E402,PLC0415   # ignore "imports not at top" and "un-sorted import block"
# pylint: disable=import-outside-toplevel

"""Pytest fixtures for testing FirmwareService with moto and Flask app factory."""

import base64
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
from app.blueprints.factory.schema import FLASH_ADDRESSES  # noqa: E402
from app.blueprints.firmware.service import (  # noqa: E402
    FirmwareMetaData,
    FirmwareService,
)
from app.errors import FileNotFoundError as AppFileNotFoundError  # noqa: E402
from app.errors import VersionNotFoundError  # noqa: E402
from app.models import FactoryFileMetaData  # noqa: E402

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
    os.environ.setdefault("PUBLIC_BASE_URL", "https://firmware.example.com")


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
            self._binaries = {}  # Store actual binary data: (project, device, version) -> bytes
            self._factory_versions = {}  # Store factory versions: (project, device, version) -> dict

        def list_firmware(self, project, device_type):
            return [
                FirmwareMetaData(
                    project=project,
                    device_type=device_type,
                    version=v,
                    checksum="x",
                    file_size=len(self._binaries.get((project, device_type, v), b"")),
                    release_date=datetime(2025, 1, 1, tzinfo=UTC),
                    bootloader_version=self._factory_versions.get(
                        (project, device_type, v), {}
                    ).get("bootloader_version"),
                    partition_table_version=self._factory_versions.get(
                        (project, device_type, v), {}
                    ).get("partition_table_version"),
                )
                for v in self._store.get((project, device_type), [])
            ]

        def get_latest(self, project, device_type, current_version=None):  # noqa: ARG002
            """Return newest FirmwareMetaData (ignores *current_version* in fake)."""
            versions = self._store.get((project, device_type), [])
            if not versions:
                raise VersionNotFoundError(f"No firmware for {project}/{device_type}")
            return self.list_firmware(project, device_type)[-1]

        def generate_presigned_url(self, project, device_type, version, **_):
            return f"https://dummy/{project}/{device_type}/{version}/f.bin"

        def upload_firmware(self, project, device_type, payload):
            version = payload["version"]
            self._store.setdefault((project, device_type), []).append(version)
            # Store the actual binary data
            binary_data = base64.b64decode(payload["firmware_b64"])
            self._binaries[(project, device_type, version)] = binary_data
            # Store factory version references if provided
            factory_refs = {}
            if "bootloader_version" in payload:
                factory_refs["bootloader_version"] = payload["bootloader_version"]
            if "partition_table_version" in payload:
                factory_refs["partition_table_version"] = payload[
                    "partition_table_version"
                ]
            if factory_refs:
                self._factory_versions[(project, device_type, version)] = factory_refs

        def get_firmware_binary(self, project, device_type, version):
            """Retrieve firmware binary from fake storage."""
            key = (project, device_type, version)
            if key not in self._binaries:
                raise VersionNotFoundError(
                    f"Firmware {project}/{device_type}/{version} not found"
                )
            return self._binaries[key]

    fake_svc = _Fake()
    # <— overwrite the real service factory in the app module
    monkeypatch.setattr(app, "FirmwareService", lambda *_, **__: fake_svc)
    return fake_svc


@pytest.fixture()
def fake_factory_service(monkeypatch):
    """Inject a fake FactoryService implementation into the app factory."""
    import hashlib

    import semver

    class _FakeFactory:
        def __init__(self):
            # Keys are (device_type, file_type, version) tuples
            self._files: dict[tuple[str, str, str], bytes] = {}
            self._metadata: dict[tuple[str, str, str], FactoryFileMetaData] = {}

        def upload_file(self, device_type, file_type, payload):
            """Store versioned file in memory."""
            version = payload.get("version")
            if not version:
                raise ValueError("Version is required for factory file upload")

            key = (device_type, file_type, version)
            raw_bytes = base64.b64decode(payload["file_b64"])
            self._files[key] = raw_bytes
            self._metadata[key] = FactoryFileMetaData(
                device_type=device_type,
                file_type=file_type,
                version=version,
                checksum=hashlib.sha256(raw_bytes).hexdigest(),
                file_size=len(raw_bytes),
                upload_date=datetime.now(UTC),
                flash_address=FLASH_ADDRESSES[file_type],
            )

        def get_file(self, device_type, file_type, version):
            """Retrieve versioned file from memory."""
            key = (device_type, file_type, version)
            if key not in self._files:
                raise AppFileNotFoundError(
                    f"Factory file {device_type}/{file_type} v{version} not found"
                )
            return self._files[key]

        def get_metadata(self, device_type, file_type, version):
            """Retrieve metadata for a specific version."""
            key = (device_type, file_type, version)
            if key not in self._metadata:
                raise AppFileNotFoundError(
                    f"Factory file {device_type}/{file_type} v{version} not found"
                )
            return self._metadata[key]

        def get_latest(self, device_type, file_type):
            """Get the latest (highest semver) version of a factory file."""
            versions = self.list_versions(device_type, file_type)
            if not versions:
                raise AppFileNotFoundError(
                    f"No versions found for factory file {device_type}/{file_type}"
                )
            versions.sort(key=lambda m: semver.VersionInfo.parse(m.version))
            return versions[-1]

        def list_versions(self, device_type, file_type):
            """List all versions of a specific factory file type."""
            return [
                meta
                for (dt, ft, _), meta in self._metadata.items()
                if dt == device_type and ft == file_type
            ]

        def list_files(self, device_type):
            """List all files for device (all types, all versions)."""
            return [
                meta for (dt, _, _), meta in self._metadata.items() if dt == device_type
            ]

    fake_svc = _FakeFactory()
    monkeypatch.setattr(app, "FactoryService", lambda *_, **__: fake_svc)
    return fake_svc


@pytest.fixture()
def client(fake_service, fake_factory_service):
    """Flask test‐client with both fake services injected."""
    app_ = create_app("development")  # DEBUG true simplifies traceback
    # Inject fake services
    app_.firmware_service = fake_service
    app_.factory_service = fake_factory_service
    with app_.test_client() as c:
        yield c
