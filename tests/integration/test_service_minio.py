import base64
import pytest

@pytest.mark.integration
def test_upload_and_list(live_service):
    payload = {
        "project": "acme",
        "device_type": "widget",
        "version": "9.9.9",
        "firmware_b64": base64.b64encode(b"bin").decode(),
        "checksum": "e1e2e3",
        "file_size": 3,
        "release_date": "2030-01-01T00:00:00Z",
    }
    live_service.upload_firmware(**payload)

    meta = live_service.get_latest("acme", "widget")
    assert meta.version == "9.9.9"
