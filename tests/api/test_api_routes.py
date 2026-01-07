"""API route tests for the firmware service.

Covers:
- authentication endpoints
- firmware listing, latest, and upload behavior
"""

import base64
from http import HTTPStatus

import pytest
from flask_jwt_extended import create_access_token

API_KEY = "dev-key"


# --------------------------------------------------------------------------- #
#  Auth
# --------------------------------------------------------------------------- #
def test_login_and_access_token(client):
    """POST /auth/login returns 200 and a valid JWT access token."""
    res = client.post("/api/v1/auth/login", json={"api_key": API_KEY})
    assert res.status_code == HTTPStatus.OK
    token = res.get_json()["access_token"]
    assert token.startswith("ey")  # looks like JWT


# --------------------------------------------------------------------------- #
#  Helper: signed auth header
# --------------------------------------------------------------------------- #
@pytest.fixture()
def jwt_headers(client):
    """Obtain a real access token via /auth/login for use in subsequent requests."""
    res = client.post("/api/v1/auth/login", json={"api_key": API_KEY})
    token = res.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------------------- #
#  Routes
# --------------------------------------------------------------------------- #
def test_firmware_list(client, jwt_headers):
    """GET /firmware/<project>/<device_type> returns 200 and the first version."""
    res = client.get("/api/v1/firmware/acme/widget", headers=jwt_headers)
    assert res.status_code == HTTPStatus.OK
    assert res.get_json()[0]["version"] == "1.0.0"


def test_latest_with_url(client, jwt_headers):
    """GET /firmware/.../latest returns 200 and includes a public download_url."""
    res = client.get("/api/v1/firmware/acme/widget/latest", headers=jwt_headers)
    assert res.status_code == HTTPStatus.OK
    # URL should point to our public download endpoint, not MinIO presigned URL
    download_url = res.get_json()["download_url"]
    assert "/api/v1/firmware/acme/widget/" in download_url
    assert download_url.endswith("/download")


def test_upload_requires_role(client):
    """POST /upload without 'uploader' role returns 403 Forbidden."""
    with client.application.app_context():
        bad_token = create_access_token(
            identity=API_KEY,
            additional_claims={"roles": []},
        )

    res = client.post(
        "/api/v1/firmware/acme/widget/upload",
        json={
            "access_token": bad_token,
            "version": "3.0.0",
            "firmware_b64": base64.b64encode(b"x").decode(),
        },
    )
    assert res.status_code == HTTPStatus.FORBIDDEN


def test_successful_upload(client):
    """POST /upload with 'uploader' role returns 204 and makes version 3.0.0 latest."""
    with client.application.app_context():
        up_token = create_access_token(
            identity=API_KEY,
            additional_claims={"roles": ["uploader"]},
        )

    res = client.post(
        "/api/v1/firmware/acme/widget/upload",
        headers={
            "Authorization": f"Bearer {up_token}",
            "Content-Type": "application/json",
        },
        json={
            "version": "3.0.0",
            "firmware_b64": base64.b64encode(b"x").decode(),
        },
    )
    assert res.status_code == HTTPStatus.NO_CONTENT

    # verify new version is latest
    latest = client.get("/api/v1/firmware/acme/widget/latest")
    assert latest.get_json()["version"] == "3.0.0"


def _dump(resp):
    """Debug helper to print status and JSON on failure."""
    print("\nDEBUG-DUMP:", resp.status_code, resp.get_json(), "\n")
