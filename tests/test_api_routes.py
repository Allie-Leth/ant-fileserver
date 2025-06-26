# tests/api/test_api_routes.py
import base64
import pytest
from flask_jwt_extended import create_access_token

API_KEY = "dev-key"


# --------------------------------------------------------------------------- #
#  Auth
# --------------------------------------------------------------------------- #

@pytest.mark.api
def test_login_and_access_token(client):
    res = client.post("/api/v1/auth/login", json={"api_key": API_KEY})
    assert res.status_code == 200
    token = res.get_json()["access_token"]
    assert token.startswith("ey")          # looks like JWT


# --------------------------------------------------------------------------- #
#  Helper: signed auth header
# --------------------------------------------------------------------------- #
@pytest.fixture()
def jwt_headers(client):
    """Real token obtained through the /auth/login endpoint."""
    res = client.post("/api/v1/auth/login", json={"api_key": API_KEY})
    token = res.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------------------- #
#  Routes
# --------------------------------------------------------------------------- #

@pytest.mark.api
def test_firmware_list(client, jwt_headers):
    res = client.get("/api/v1/firmware/acme/widget", headers=jwt_headers)
    assert res.status_code == 200
    assert res.get_json()[0]["version"] == "1.0.0"


@pytest.mark.api
def test_latest_with_url(client, jwt_headers):
    res = client.get("/api/v1/firmware/acme/widget/latest", headers=jwt_headers)
    assert res.status_code == 200
    assert res.get_json()["download_url"].startswith("https://dummy")


@pytest.mark.api
def test_upload_requires_role(client):
    with client.application.app_context():
        bad_token = create_access_token(
            identity=API_KEY, 
            additional_claims={"roles": []},
        )

    res = client.post(
        "/api/v1/firmware/acme/widget/upload",
        #   ↓ put the token in JSON because app expects it there first
        json={
            "access_token": bad_token,                 # ← critical
            "version":      "3.0.0",
            "firmware_b64": base64.b64encode(b"x").decode(),
        },
    )
    assert res.status_code == 403




@pytest.mark.api
def test_successful_upload(client):
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
    assert res.status_code == 204

    # verify new version is latest
    latest = client.get("/api/v1/firmware/acme/widget/latest")
    assert latest.get_json()["version"] == "3.0.0"
    
    
def _dump(resp):
    print("\nDEBUG-DUMP:", resp.status_code, resp.get_json(), "\n")