"""
Edge-case tests for firmware routes.

Covers:
- 404 when no firmware version is found
- 500 when storage errors occur on upload
- listing with URLs branch
- 400 on semver validation errors
"""

import base64

from app.errors import StorageError, VersionNotFoundError


def _svc(app):
    """Helper to extract the FirmwareService instance from the app’s URL rules."""
    rule = next(
        r for r in app.url_map.iter_rules() if r.endpoint == "firmware.get_latest"
    )
    return rule.defaults["svc"]


def test_latest_when_none(monkeypatch, client):
    svc = _svc(client.application)
    monkeypatch.setattr(
        svc,
        "get_latest",
        lambda *_, **__: (_ for _ in ()).throw(VersionNotFoundError("none")),
    )
    res = client.get("/api/v1/firmware/ghost/device/latest")
    assert res.status_code == 404
    assert res.get_json()["error"] == "version_not_found"


def test_upload_storage_error(monkeypatch, client):
    """POST /upload returns 500 and storage_error when upload_firmware raises StorageError."""
    svc = _svc(client.application)

    # make *this* service instance raise StorageError on upload
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

    assert res.status_code == 500
    assert res.get_json()["error"] == "storage_error"


def test_list_with_urls(monkeypatch, client):
    """GET list with ?with_urls=true returns 200 and includes download_url."""
    svc = _svc(client.application)

    # seed fake store with one release so list_all returns something
    svc.upload_firmware(
        "acme",
        "widget",
        {"version": "1.0.0", "firmware_b64": base64.b64encode(b"x").decode()},
    )

    # make presigned URL deterministic
    monkeypatch.setattr(
        svc, "generate_presigned_url", lambda *_, **__: "https://signed/url"
    )

    res = client.get("/api/v1/firmware/acme/widget?with_urls=true")
    body = res.get_json()

    assert res.status_code == 200
    assert body[0]["download_url"] == "https://signed/url"  # hit branch


def test_latest_validation_error(client):
    """GET latest with invalid semver returns 400 and validation_error."""
    res = client.get("/api/v1/firmware/acme/widget/latest?current=not.semver")
    assert res.status_code == 400
    assert res.get_json()["error"] == "validation_error"
