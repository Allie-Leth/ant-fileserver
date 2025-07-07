import base64

import pytest
from botocore.exceptions import ClientError

from app.blueprints.firmware.service import FirmwareService
from app.errors import (
    ChecksumMismatchError,
    DuplicateVersionError,
    StorageError,
)


# Helper: base64 encode a bytes object
def _b64(payload: bytes) -> str:
    return base64.b64encode(payload).decode()


# Minimal in-memory S3 stub
class _FakeBody:
    def __init__(self, data: bytes):
        self._data = data

    def read(self):
        return self._data


class _FakePaginator:
    def __init__(self, objects: dict[str, bytes]):
        self._objects = objects

    def paginate(self, **_):
        # boto returns an iterator of pages; each has "Contents"
        return [{"Contents": [{"Key": k} for k in self._objects.keys()]}]


class FakeS3:
    """Subset of boto3 S3 client used by FirmwareService."""

    def __init__(self):
        self.objects: dict[str, bytes] = {}

    # list_firmware
    def get_paginator(self, _name):
        return _FakePaginator(self.objects)

    def get_object(self, Bucket, Key):
        return {"Body": _FakeBody(self.objects[Key])}

    # upload_firmware
    def put_object(self, Bucket, Key, Body, ContentType):
        self.objects[Key] = Body

    # generate_presigned_url
    def generate_presigned_url(self, _op, Params, ExpiresIn):
        key = Params["Key"]
        if key not in self.objects:
            raise StorageError("object missing")  # exercise error path
        return f"https://fake-s3/{key}?exp={ExpiresIn}"


# Pytest fixture: real service wired to FakeS3
@pytest.fixture
def svc(monkeypatch):
    service = FirmwareService(
        endpoint_url="http://fake",
        bucket="firmware",
        access_key_id="x",
        secret_access_key="y",
        region="us-east-1",
    )
    fake = FakeS3()
    # overwrite the real boto client with our stub
    service.s3 = fake
    return service


# Happy-path upload → list  → get_latest
def test_upload_and_list_and_latest(svc):
    svc.upload_firmware(
        "acme",
        "widget",
        {"version": "1.0.0", "firmware_b64": _b64(b"x")},
    )
    svc.upload_firmware(
        "acme",
        "widget",
        {"version": "2.0.0", "firmware_b64": _b64(b"y")},
    )

    releases = svc.list_firmware("acme", "widget")
    assert [r.version for r in releases] == ["1.0.0", "2.0.0"]

    # ask for something newer than 1.0.0 → should return 2.0.0
    latest = svc.get_latest("acme", "widget", current_version="1.0.0")
    assert latest.version == "2.0.0"


# Duplicate version
def test_duplicate_version_raises(svc):
    payload = {"version": "3.3.3", "firmware_b64": _b64(b"x")}
    svc.upload_firmware("p", "d", payload)
    with pytest.raises(DuplicateVersionError):
        svc.upload_firmware("p", "d", payload)


# Bad checksum
def test_checksum_mismatch(svc):
    bad = {"version": "4.0.0", "firmware_b64": _b64(b"x"), "checksum": "deadbeef"}
    with pytest.raises(ChecksumMismatchError):
        svc.upload_firmware("p", "d", bad)


# get_latest with no releases → ValueError
def test_get_latest_no_releases(svc):
    with pytest.raises(ValueError):
        svc.get_latest("ghost", "device")


# Presigned-URL generation + error path
def test_presigned_url_success_and_missing(svc):
    svc.upload_firmware("p", "d", {"version": "5.0.0", "firmware_b64": _b64(b"x")})
    url = svc.generate_presigned_url("p", "d", "5.0.0", expires_in=42)
    assert url.endswith("firmware.bin?exp=42")

    # Asking for a non-existent object triggers StorageError via FakeS3
    with pytest.raises(StorageError):
        svc.generate_presigned_url("p", "d", "does-not-exist")


# list_firmware → paginator blows up
def test_list_firmware_client_error(monkeypatch, svc):
    class BadPaginator:
        def paginate(self, *_, **__):
            # mimic boto's ClientError signature
            raise ClientError({"Error": {"Code": "500"}}, "List")

    # svc.s3.get_paginator(...) should return our stub
    monkeypatch.setattr(
        svc.s3,
        "get_paginator",
        lambda *_args, **_kwargs: BadPaginator(),
    )

    with pytest.raises(StorageError):
        svc.list_firmware("p", "d")


@pytest.mark.parametrize(
    "payload",
    [
        {"firmware_b64": _b64(b"x")},
        {"version": "not-semver", "firmware_b64": _b64(b"x")},
    ],
)
def test_upload_bad_version(svc, payload):
    with pytest.raises(ValueError):
        svc.upload_firmware("p", "d", payload)


def test_upload_bad_base64(svc):
    bad = {"version": "1.2.3", "firmware_b64": "!!not-b64!!"}
    with pytest.raises(ValueError):
        svc.upload_firmware("p", "d", bad)


def test_get_latest_already_latest(svc):
    svc.upload_firmware("p", "d", {"version": "0.9.0", "firmware_b64": _b64(b"x")})
    latest = svc.get_latest("p", "d", current_version="1.0.0")
    assert latest.version == "0.9.0"  # returns highest available


def test_presigned_url_client_error(monkeypatch, svc):
    def boom(*_, **__):
        raise ClientError({"Error": {"Code": "NoSuchKey"}}, "Get")

    monkeypatch.setattr(svc.s3, "generate_presigned_url", boom)

    with pytest.raises(StorageError):
        svc.generate_presigned_url("p", "d", "deadbeef")


def test_upload_missing_firmware_blob(svc):
    """Omitting 'firmware_b64' triggers the KeyError→ValueError branch (88-93)."""
    with pytest.raises(ValueError):
        svc.upload_firmware("proj", "dev", {"version": "1.0.0"})


def test_get_latest_no_current_version(svc):
    """Call get_latest() without current_version → returns highest (lines 190-192)."""
    svc.upload_firmware("proj", "dev", {"version": "1.0.0", "firmware_b64": _b64(b"a")})
    svc.upload_firmware("proj", "dev", {"version": "2.0.0", "firmware_b64": _b64(b"b")})

    latest = svc.get_latest("proj", "dev")  # no current_version arg
    assert latest.version == "2.0.0"


def test_get_latest_no_current_arg(svc):
    svc.upload_firmware("p", "d", {"version": "1.0.0", "firmware_b64": _b64(b"a")})
    svc.upload_firmware("p", "d", {"version": "2.0.0", "firmware_b64": _b64(b"b")})

    latest = svc.get_latest("p", "d")  # ← no current_version
    assert latest.version == "2.0.0"


def test_list_skips_bad_metadata(svc):
    """
    Put a metadata.json object that contains INVALID JSON.
    list_firmware should not crash; it should log & skip (lines 88-93).
    """
    bad_key = "releases/p/d/1.0.0/metadata.json"
    svc.s3.put_object(
        Bucket=svc.bucket,
        Key=bad_key,
        Body=b'{"this_is":"NOT valid JSON"',  # missing closing }
        ContentType="application/json",
    )

    # Should return an empty list (skipped), not raise.
    metas = svc.list_firmware("p", "d")
    assert metas == []


def test_get_latest_fallback_to_latest(svc):
    svc.upload_firmware("p", "d", {"version": "1.0.0", "firmware_b64": _b64(b"a")})
    svc.upload_firmware("p", "d", {"version": "2.0.0", "firmware_b64": _b64(b"b")})

    latest = svc.get_latest("p", "d")  # current_version=None
    assert latest.version == "2.0.0"


def test_upload_s3_client_error(monkeypatch, svc):
    """
    Force svc.upload_firmware to hit the except-ClientError branch
    (lines 190-192) and raise StorageError.
    """
    # any call to put_object should raise the AWS client error
    boom = ClientError({"Error": {"Code": "500"}}, "Put")
    monkeypatch.setattr(svc.s3, "put_object", lambda **_: (_ for _ in ()).throw(boom))

    with pytest.raises(StorageError):
        svc.upload_firmware(
            "proj", "dev", {"version": "1.0.0", "firmware_b64": _b64(b"x")}
        )
