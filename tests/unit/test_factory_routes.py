# ruff: noqa: PLC0415,PLR2004   # imports inside tests, magic values in assertions
"""Unit tests for factory file API routes.

Tests for:
- GET /api/v1/factory/<device_type>/<file_type>/<version> - Download file (public)
- GET /api/v1/factory/<device_type>/<file_type>/<version>/info - Get metadata
- GET /api/v1/factory/<device_type>/<file_type>/latest - Get latest version
- GET /api/v1/factory/<device_type>/<file_type>/versions - List versions
- POST /api/v1/factory/<device_type>/<file_type>/upload - Upload file (auth required)
- GET /api/v1/factory/<device_type> - List files
"""

import base64
from http import HTTPStatus

import boto3
import pytest
from flask import Flask
from moto import mock_aws

from app.blueprints.factory.routes import factory_bp

_BUCKET = "test-bucket"


def _b64(data: bytes) -> str:
    """Helper to base64 encode bytes."""
    return base64.b64encode(data).decode()


@pytest.fixture
def app_with_service():
    """Create Flask app with real FactoryService connected to moto's mock S3.

    The mock_aws context must encompass both service creation AND client requests,
    so we create everything within a single fixture.
    """
    from flask_jwt_extended import JWTManager

    from app.blueprints.factory.service import FactoryService
    from app.errors import register_error_handlers

    with mock_aws():
        # Create mock S3 bucket
        s3_client = boto3.client("s3", region_name="us-east-1")
        s3_client.create_bucket(Bucket=_BUCKET)

        # Create real service backed by moto
        factory_svc = FactoryService(
            endpoint_url=None,
            bucket=_BUCKET,
            access_key_id="test",
            secret_access_key="test",
            region="us-east-1",
        )

        # Create Flask app
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.config["JWT_SECRET_KEY"] = "test-secret"
        app.config["PUBLIC_BASE_URL"] = "http://test.example.com"

        # Register JWT
        JWTManager(app)

        # Register error handlers
        register_error_handlers(app)

        # Register factory blueprint
        app.register_blueprint(factory_bp, url_prefix="/api/v1/factory")

        # Attach real service
        app.factory_service = factory_svc

        yield app, factory_svc


@pytest.fixture
def app(app_with_service):
    """Extract Flask app from combined fixture."""
    return app_with_service[0]


@pytest.fixture
def factory_svc(app_with_service):
    """Extract FactoryService from combined fixture."""
    return app_with_service[1]


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def auth_headers(app):
    """Create JWT token headers for authenticated requests."""
    from flask_jwt_extended import create_access_token

    with app.app_context():
        token = create_access_token(
            identity="test-user",
            additional_claims={"roles": ["uploader"]},
        )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def non_uploader_headers(app):
    """Create JWT token headers without uploader role."""
    from flask_jwt_extended import create_access_token

    with app.app_context():
        token = create_access_token(
            identity="test-user",
            additional_claims={"roles": ["viewer"]},
        )
    return {"Authorization": f"Bearer {token}"}


class TestDownload:
    """Tests for GET /api/v1/factory/<device_type>/<file_type>/<version>."""

    def test_download_returns_binary(self, client, factory_svc):
        """Download should return the file binary."""
        factory_svc.upload_file(
            "esp32s3",
            "bootloader",
            {"version": "1.0.0", "file_b64": _b64(b"bootloader content")},
        )

        response = client.get("/api/v1/factory/esp32s3/bootloader/1.0.0")

        assert response.status_code == HTTPStatus.OK
        assert response.data == b"bootloader content"
        assert response.content_type == "application/octet-stream"

    def test_download_no_auth_required(self, client, factory_svc):
        """Download should be public (no auth required)."""
        factory_svc.upload_file(
            "esp32s3",
            "bootloader",
            {"version": "1.0.0", "file_b64": _b64(b"content")},
        )

        # No auth headers
        response = client.get("/api/v1/factory/esp32s3/bootloader/1.0.0")

        assert response.status_code == HTTPStatus.OK

    def test_download_not_found(self, client):
        """Download should return 404 if file doesn't exist."""
        response = client.get("/api/v1/factory/nonexistent/bootloader/1.0.0")

        assert response.status_code == HTTPStatus.NOT_FOUND
        data = response.get_json()
        assert data["error"] == "file_not_found"

    def test_download_version_not_found(self, client, factory_svc):
        """Download should return 404 if specific version doesn't exist."""
        factory_svc.upload_file(
            "esp32s3",
            "bootloader",
            {"version": "1.0.0", "file_b64": _b64(b"v1")},
        )

        response = client.get("/api/v1/factory/esp32s3/bootloader/2.0.0")

        assert response.status_code == HTTPStatus.NOT_FOUND

    def test_download_invalid_file_type(self, client):
        """Download should return 400 for invalid file_type."""
        response = client.get("/api/v1/factory/esp32s3/firmware/1.0.0")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.get_json()
        assert data["error"] == "validation_error"

    def test_download_content_disposition(self, client, factory_svc):
        """Download should include Content-Disposition header with version."""
        factory_svc.upload_file(
            "esp32s3",
            "bootloader",
            {"version": "1.0.0", "file_b64": _b64(b"content")},
        )

        response = client.get("/api/v1/factory/esp32s3/bootloader/1.0.0")

        assert "Content-Disposition" in response.headers
        assert "esp32s3-bootloader-1.0.0.bin" in response.headers["Content-Disposition"]


class TestGetInfo:
    """Tests for GET /api/v1/factory/<device_type>/<file_type>/<version>/info."""

    def test_info_returns_metadata(self, client, factory_svc):
        """Info should return file metadata."""
        factory_svc.upload_file(
            "esp32s3",
            "bootloader",
            {"version": "1.0.0", "file_b64": _b64(b"bootloader")},
        )

        response = client.get("/api/v1/factory/esp32s3/bootloader/1.0.0/info")

        assert response.status_code == HTTPStatus.OK
        data = response.get_json()
        assert data["device_type"] == "esp32s3"
        assert data["file_type"] == "bootloader"
        assert data["version"] == "1.0.0"
        assert data["flash_address"] == 0x0
        assert "checksum" in data
        assert "file_size" in data

    def test_info_includes_flash_address(self, client, factory_svc):
        """Info should include correct flash address for partition table."""
        factory_svc.upload_file(
            "esp32s3",
            "partition-table",
            {"version": "1.0.0", "file_b64": _b64(b"partition")},
        )

        response = client.get("/api/v1/factory/esp32s3/partition-table/1.0.0/info")

        assert response.status_code == HTTPStatus.OK
        data = response.get_json()
        assert data["flash_address"] == 0x8000

    def test_info_not_found(self, client):
        """Info should return 404 if file doesn't exist."""
        response = client.get("/api/v1/factory/nonexistent/bootloader/1.0.0/info")

        assert response.status_code == HTTPStatus.NOT_FOUND


class TestGetLatest:
    """Tests for GET /api/v1/factory/<device_type>/<file_type>/latest."""

    def test_latest_returns_highest_version(self, client, factory_svc):
        """Latest should return the highest semver version."""
        factory_svc.upload_file(
            "esp32s3",
            "bootloader",
            {"version": "1.0.0", "file_b64": _b64(b"v1")},
        )
        factory_svc.upload_file(
            "esp32s3",
            "bootloader",
            {"version": "2.0.0", "file_b64": _b64(b"v2")},
        )
        factory_svc.upload_file(
            "esp32s3",
            "bootloader",
            {"version": "1.5.0", "file_b64": _b64(b"v1.5")},
        )

        response = client.get("/api/v1/factory/esp32s3/bootloader/latest")

        assert response.status_code == HTTPStatus.OK
        data = response.get_json()
        assert data["version"] == "2.0.0"

    def test_latest_includes_download_url(self, client, factory_svc):
        """Latest should include download_url."""
        factory_svc.upload_file(
            "esp32s3",
            "bootloader",
            {"version": "1.0.0", "file_b64": _b64(b"content")},
        )

        response = client.get("/api/v1/factory/esp32s3/bootloader/latest")

        assert response.status_code == HTTPStatus.OK
        data = response.get_json()
        assert "download_url" in data
        assert "esp32s3/bootloader/1.0.0" in data["download_url"]

    def test_latest_not_found(self, client):
        """Latest should return 404 if no versions exist."""
        response = client.get("/api/v1/factory/nonexistent/bootloader/latest")

        assert response.status_code == HTTPStatus.NOT_FOUND


class TestListVersions:
    """Tests for GET /api/v1/factory/<device_type>/<file_type>/versions."""

    def test_list_versions_returns_all(self, client, factory_svc):
        """List versions should return all versions of file type."""
        factory_svc.upload_file(
            "esp32s3",
            "bootloader",
            {"version": "1.0.0", "file_b64": _b64(b"v1")},
        )
        factory_svc.upload_file(
            "esp32s3",
            "bootloader",
            {"version": "2.0.0", "file_b64": _b64(b"v2")},
        )

        response = client.get("/api/v1/factory/esp32s3/bootloader/versions")

        assert response.status_code == HTTPStatus.OK
        data = response.get_json()
        assert len(data) == 2
        versions = {d["version"] for d in data}
        assert versions == {"1.0.0", "2.0.0"}

    def test_list_versions_empty(self, client):
        """List versions should return empty array for nonexistent."""
        response = client.get("/api/v1/factory/esp32s3/bootloader/versions")

        assert response.status_code == HTTPStatus.OK
        data = response.get_json()
        assert data == []


class TestUpload:
    """Tests for POST /api/v1/factory/<device_type>/<file_type>/upload."""

    def test_upload_requires_auth(self, client):
        """Upload should require authentication."""
        response = client.post(
            "/api/v1/factory/esp32s3/bootloader/upload",
            json={"version": "1.0.0", "file_b64": _b64(b"content")},
        )

        assert response.status_code == HTTPStatus.UNAUTHORIZED

    def test_upload_requires_uploader_role(self, client, non_uploader_headers):
        """Upload should require 'uploader' role."""
        response = client.post(
            "/api/v1/factory/esp32s3/bootloader/upload",
            json={"version": "1.0.0", "file_b64": _b64(b"content")},
            headers=non_uploader_headers,
        )

        assert response.status_code == HTTPStatus.FORBIDDEN

    def test_upload_success(self, client, auth_headers, factory_svc):
        """Upload should succeed with valid auth and data."""
        response = client.post(
            "/api/v1/factory/esp32s3/bootloader/upload",
            json={"version": "1.0.0", "file_b64": _b64(b"bootloader content")},
            headers=auth_headers,
        )

        assert response.status_code == HTTPStatus.NO_CONTENT

        # Verify file was stored
        stored = factory_svc.get_file("esp32s3", "bootloader", "1.0.0")
        assert stored == b"bootloader content"

    def test_upload_invalid_file_type(self, client, auth_headers):
        """Upload should reject invalid file types."""
        response = client.post(
            "/api/v1/factory/esp32s3/firmware/upload",
            json={"version": "1.0.0", "file_b64": _b64(b"content")},
            headers=auth_headers,
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST


class TestListFiles:
    """Tests for GET /api/v1/factory/<device_type>."""

    def test_list_returns_all_files(self, client, factory_svc):
        """List should return all files for device."""
        factory_svc.upload_file(
            "esp32s3",
            "bootloader",
            {"version": "1.0.0", "file_b64": _b64(b"boot")},
        )
        factory_svc.upload_file(
            "esp32s3",
            "partition-table",
            {"version": "1.0.0", "file_b64": _b64(b"part")},
        )

        response = client.get("/api/v1/factory/esp32s3")

        assert response.status_code == HTTPStatus.OK
        data = response.get_json()
        assert len(data) == 2
        file_types = {f["file_type"] for f in data}
        assert file_types == {"bootloader", "partition-table"}

    def test_list_returns_all_versions(self, client, factory_svc):
        """List should return all versions of each file type."""
        factory_svc.upload_file(
            "esp32s3",
            "bootloader",
            {"version": "1.0.0", "file_b64": _b64(b"v1")},
        )
        factory_svc.upload_file(
            "esp32s3",
            "bootloader",
            {"version": "2.0.0", "file_b64": _b64(b"v2")},
        )

        response = client.get("/api/v1/factory/esp32s3")

        assert response.status_code == HTTPStatus.OK
        data = response.get_json()
        assert len(data) == 2
        versions = {f["version"] for f in data}
        assert versions == {"1.0.0", "2.0.0"}

    def test_list_empty_for_unknown_device(self, client):
        """List should return empty array for unknown device."""
        response = client.get("/api/v1/factory/unknown-device")

        assert response.status_code == HTTPStatus.OK
        data = response.get_json()
        assert data == []

    def test_list_only_includes_specified_device(self, client, factory_svc):
        """List should not include files from other devices."""
        factory_svc.upload_file(
            "esp32s3",
            "bootloader",
            {"version": "1.0.0", "file_b64": _b64(b"s3")},
        )
        factory_svc.upload_file(
            "esp32c3",
            "bootloader",
            {"version": "1.0.0", "file_b64": _b64(b"c3")},
        )

        response = client.get("/api/v1/factory/esp32s3")

        data = response.get_json()
        assert len(data) == 1
        assert data[0]["device_type"] == "esp32s3"
