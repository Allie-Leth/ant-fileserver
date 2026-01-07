"""Edge-case tests for firmware routes.

Covers:
- 404 when no firmware version is found
- 500 when storage errors occur on upload
- listing with URLs branch
- 400 on semver validation errors
"""

import base64
from http import HTTPStatus

from app.blueprints.factory.schema import FLASH_ADDRESSES
from app.errors import StorageError, VersionNotFoundError

# Expected count for tests
EXPECTED_FACTORY_FILE_COUNT = 2  # bootloader + partition-table


def _svc(app):
    """Helper to extract the FirmwareService instance from the app."""
    return app.firmware_service


def test_latest_when_none(monkeypatch, client):
    """GET /latest returns 404 and version_not_found when no versions exist."""
    svc = _svc(client.application)
    monkeypatch.setattr(
        svc,
        "get_latest",
        lambda *_, **__: (_ for _ in ()).throw(VersionNotFoundError("none")),
    )

    res = client.get("/api/v1/firmware/ghost/device/latest")
    assert res.status_code == HTTPStatus.NOT_FOUND
    assert res.get_json()["error"] == "version_not_found"


def test_upload_storage_error(monkeypatch, client):
    """POST /upload returns 500 and storage_error when upload_firmware raises StorageError."""
    svc = _svc(client.application)
    monkeypatch.setattr(
        svc,
        "upload_firmware",
        lambda *_, **__: (_ for _ in ()).throw(StorageError("disk full")),
    )

    token = client.post("/api/v1/auth/login", json={"api_key": "dev-key"}).get_json()[
        "access_token"
    ]

    res = client.post(
        "/api/v1/firmware/acme/widget/upload",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "version": "9.9.9",
            "firmware_b64": base64.b64encode(b"x").decode(),
        },
    )

    assert res.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert res.get_json()["error"] == "storage_error"


def test_list_with_urls(client):
    """GET list with ?with_urls=true returns 200 and includes download_url."""
    svc = _svc(client.application)
    svc.upload_firmware(
        "acme",
        "widget",
        {"version": "1.0.0", "firmware_b64": base64.b64encode(b"x").decode()},
    )

    res = client.get("/api/v1/firmware/acme/widget?with_urls=true")
    body = res.get_json()

    assert res.status_code == HTTPStatus.OK
    # URL should point to public download endpoint, not MinIO presigned URL
    download_url = body[0]["download_url"]
    assert "/api/v1/firmware/acme/widget/1.0.0/download" in download_url


def test_latest_validation_error(client):
    """GET latest with invalid semver returns 400 and validation_error."""
    res = client.get("/api/v1/firmware/acme/widget/latest?current=not.semver")
    assert res.status_code == HTTPStatus.BAD_REQUEST
    assert res.get_json()["error"] == "validation_error"


def test_latest_with_include_factory(client):
    """GET /latest?include_factory=true includes factory_files when firmware specifies them."""
    svc = _svc(client.application)

    # Upload factory files first
    factory_svc = client.application.factory_service
    factory_svc.upload_file(
        "widget",
        "bootloader",
        {"version": "1.0.0", "file_b64": base64.b64encode(b"bootloader").decode()},
    )
    factory_svc.upload_file(
        "widget",
        "partition-table",
        {"version": "2.0.0", "file_b64": base64.b64encode(b"partition").decode()},
    )

    # Upload firmware that references factory versions
    svc.upload_firmware(
        "acme",
        "widget",
        {
            "version": "3.0.0",
            "firmware_b64": base64.b64encode(b"firmware").decode(),
            "bootloader_version": "1.0.0",
            "partition_table_version": "2.0.0",
        },
    )

    res = client.get("/api/v1/firmware/acme/widget/latest?include_factory=true")
    body = res.get_json()

    assert res.status_code == HTTPStatus.OK
    assert body["version"] == "3.0.0"
    assert "factory_files" in body
    assert len(body["factory_files"]) == EXPECTED_FACTORY_FILE_COUNT

    # Check bootloader info
    bootloader = next(
        f for f in body["factory_files"] if f["file_type"] == "bootloader"
    )
    assert bootloader["version"] == "1.0.0"
    assert bootloader["flash_address"] == FLASH_ADDRESSES["bootloader"]
    assert "download_url" in bootloader
    assert "widget/bootloader/1.0.0" in bootloader["download_url"]

    # Check partition-table info
    partition = next(
        f for f in body["factory_files"] if f["file_type"] == "partition-table"
    )
    assert partition["version"] == "2.0.0"
    assert partition["flash_address"] == FLASH_ADDRESSES["partition-table"]
    assert "download_url" in partition


def test_latest_without_include_factory(client):
    """GET /latest without include_factory does not include factory_files."""
    svc = _svc(client.application)
    svc.upload_firmware(
        "acme",
        "widget",
        {
            "version": "4.0.0",
            "firmware_b64": base64.b64encode(b"firmware").decode(),
            "bootloader_version": "1.0.0",
        },
    )

    res = client.get("/api/v1/firmware/acme/widget/latest")
    body = res.get_json()

    assert res.status_code == HTTPStatus.OK
    assert "factory_files" not in body


def test_latest_include_factory_no_versions_set(client):
    """GET /latest?include_factory=true returns empty factory_files if firmware has no versions."""
    svc = _svc(client.application)
    svc.upload_firmware(
        "acme",
        "widget",
        {
            "version": "5.0.0",
            "firmware_b64": base64.b64encode(b"firmware").decode(),
            # No bootloader_version or partition_table_version
        },
    )

    res = client.get("/api/v1/firmware/acme/widget/latest?include_factory=true")
    body = res.get_json()

    assert res.status_code == HTTPStatus.OK
    assert body["factory_files"] == []
