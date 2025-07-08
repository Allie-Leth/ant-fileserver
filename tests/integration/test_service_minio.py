"""Integration tests for FirmwareService with a real MinIO backend.

Validates that uploading a firmware blob and retrieving the latest metadata
works end-to-end.
"""

import base64

import pytest


@pytest.mark.integration
def test_upload_and_latest(live_service):
    """Upload a firmware binary and verify get_latest returns the new version."""
    raw = b"bin"
    payload = {
        "version": "9.9.9",
        "firmware_b64": base64.b64encode(raw).decode(),
        # let the service calculate checksum & file_size
    }
    live_service.upload_firmware("acme", "widget", payload)

    meta = live_service.get_latest("acme", "widget")
    assert meta.version == "9.9.9"
