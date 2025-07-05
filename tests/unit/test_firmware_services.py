import base64
import pytest
from urllib.parse import urlparse

from app.errors import (
    DuplicateVersionError,
    ChecksumMismatchError,
)
from app.models import FirmwareMetaData


def test_list_firmware_sorted(svc):
    metas = svc.list_firmware("acme", "widget")
    assert [m.version for m in metas] == ["1.0.0", "2.0.0"]
    # ensure objects are dataclass instances, not dicts
    assert isinstance(metas[0], FirmwareMetaData)


def test_get_latest_without_current(svc):
    latest = svc.get_latest("acme", "widget")
    assert latest.version == "2.0.0"


def test_get_latest_with_current_returns_next(svc):
    nxt = svc.get_latest("acme", "widget", current_version="1.0.0")
    assert nxt.version == "2.0.0"


def test_upload_duplicate_version_guard(svc):
    payload = {
        "version": "2.0.0",  # already exists
        "firmware_b64": base64.b64encode(b"x").decode(),
    }
    with pytest.raises(DuplicateVersionError):
        svc.upload_firmware("acme", "widget", payload)


def test_upload_checksum_mismatch(svc):
    payload = {
        "version": "3.0.0",
        "firmware_b64": base64.b64encode(b"x").decode(),
        "checksum": "bogus",  # wrong
    }
    with pytest.raises(ChecksumMismatchError):
        svc.upload_firmware("acme", "widget", payload)


def test_successful_upload_then_latest(svc):
    bin_data = b"hello"
    payload = {
        "version": "3.0.0",
        "firmware_b64": base64.b64encode(bin_data).decode(),
        # omit checksum to let service compute it
        "release_notes": "third release",
    }
    svc.upload_firmware("acme", "widget", payload)

    latest = svc.get_latest("acme", "widget")
    assert latest.version == "3.0.0"
    assert latest.file_size == len(bin_data)
    assert latest.release_notes == "third release"


def test_presigned_url_shape(svc):
    url = svc.generate_presigned_url("acme", "widget", "1.0.0", expires_in=123)
    parsed = urlparse(url)

    # Path-style or virtual-hosted both end with the key string.
    assert parsed.path.endswith("/releases/acme/widget/1.0.0/firmware.bin")

    # Expiration is expressed either as Expires (SigV2) or X-Amz-Expires (SigV4)
    assert "Expires=123" in parsed.query or "X-Amz-Expires=123" in parsed.query
