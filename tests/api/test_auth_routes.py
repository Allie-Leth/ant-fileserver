import base64

import pytest
from flask import Flask
from flask_jwt_extended import create_refresh_token

from app.blueprints.auth.routes import auth_bp
from app.extensions import jwt


@pytest.fixture
def auth_app():
    app = Flask(__name__)
    app.config["JWT_SECRET_KEY"] = base64.b64encode(b"secret").decode()
    app.config["API_KEY_ROLES"] = {"dev-key": ["uploader"]}
    jwt.init_app(app)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    return app


def test_login_via_header(auth_app):
    with auth_app.test_client() as c:
        res = c.post("/auth/login", headers={"X-API-KEY": "dev-key"})
        token = res.get_json()["access_token"]
        assert res.status_code == 200
        assert token.startswith("ey")  # looks like a JWT


def test_refresh_and_whoami(auth_app):
    # Create a real refresh token tied to this app
    with auth_app.app_context():
        refresh = create_refresh_token(
            identity="dev-key",
            additional_claims={"roles": ["uploader"]},
        )

    with auth_app.test_client() as c:
        # exchange refresh → new access token
        new_access = c.post(
            "/auth/refresh", headers={"Authorization": f"Bearer {refresh}"}
        ).get_json()["access_token"]

        # verify /whoami with the fresh access token
        who = c.get(
            "/auth/whoami", headers={"Authorization": f"Bearer {new_access}"}
        ).get_json()
        assert who == {"key": "dev-key", "roles": ["uploader"]}


def test_login_invalid_credentials(auth_app):
    """When the supplied API key is missing or unknown, /login must
    return 401 with {"error":"invalid_credentials"}.
    This executes line 21 in auth/routes.py.
    """
    with auth_app.test_client() as c:
        res = c.post("/auth/login", json={"api_key": "bad-key"})
        body = res.get_json()

    assert res.status_code == 401
    assert body == {"error": "invalid_credentials"}
