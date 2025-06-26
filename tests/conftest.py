import json
import boto3
import pytest
from datetime import datetime, timezone
from moto import mock_aws

from app.blueprints.firmware.service import FirmwareService, FirmwareMetaData

_BUCKET = "firmware"



@pytest.fixture(scope="function")
def svc():
    """FirmwareService wired to moto’s in-memory S3 with a test bucket."""
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=_BUCKET)

        # seed two releases
        for ver in ("1.0.0", "2.0.0"):
            prefix = f"releases/acme/widget/{ver}/"
            client.put_object(
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
    """In-memory stand-in that mimics FirmwareService API."""
    class _Fake:
        def __init__(self):
            self._store = {
                ("acme", "widget"): ["1.0.0", "2.0.0"],
            }

        # --- methods used by blueprints ---
        def list_firmware(self, project, device_type):
            return [
                FirmwareMetaData(
                    project=project,
                    device_type=device_type,
                    version=v,
                    checksum="x",
                    file_size=1,
                    release_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
                )
                for v in self._store.get((project, device_type), [])
            ]

        def get_latest(self, project, device_type, current_version=None):
            return self.list_firmware(project, device_type)[-1]

        def generate_presigned_url(self, project, device_type, version, **_):
            return f"https://dummy/{project}/{device_type}/{version}/f.bin"

        def upload_firmware(self, project, device_type, payload):
            self._store.setdefault((project, device_type), []).append(
                payload["version"]
            )

    svc = _Fake()

    # Monkey-patch the service instance the app factory would create
    import app
    monkeypatch.setattr(app, "FirmwareService", lambda *a, **kw: svc)

    return svc


@pytest.fixture()
def client(fake_service, monkeypatch):
    """Flask test-client with our fake service injected."""
    from app import create_app

    app_ = create_app("development")   # DEBUG true simplifies traceback
    with app_.test_client() as c:
        # Inject the fake service into all routes that expect 'svc'
        for rule in app_.url_map.iter_rules():
            if rule.endpoint.startswith("firmware."):

                rule.defaults = (rule.defaults or {})
                rule.defaults["svc"] = fake_service
        yield c