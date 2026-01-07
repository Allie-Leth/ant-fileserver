"""Tests for firmware download endpoint.

TDD Red phase: These tests define the expected behavior for the
/api/v1/firmware/<project>/<device_type>/<version>/download endpoint.

The endpoint should:
- Stream firmware binary from MinIO without exposing MinIO URLs
- Validate path parameters (project, device_type, version)
- Return proper Content-Type and Content-Disposition headers
- Return 404 for non-existent firmware
- Work without authentication (public firmware distribution)
"""

import base64
from http import HTTPStatus


class TestFirmwareDownloadEndpoint:
    """Test cases for GET /api/v1/firmware/<project>/<device_type>/<version>/download."""

    def test_download_returns_binary_content(self, client):
        """Download endpoint should return the actual firmware binary."""
        # First upload a firmware
        token = client.post(
            "/api/v1/auth/login", json={"api_key": "dev-key"}
        ).get_json()["access_token"]

        firmware_content = b"FIRMWARE_BINARY_CONTENT_HERE"
        client.post(
            "/api/v1/firmware/testproj/esp32/upload",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "version": "1.0.0",
                "firmware_b64": base64.b64encode(firmware_content).decode(),
            },
        )

        # Download the firmware
        response = client.get("/api/v1/firmware/testproj/esp32/1.0.0/download")

        assert response.status_code == HTTPStatus.OK
        assert response.data == firmware_content

    def test_download_content_type_is_octet_stream(self, client):
        """Download should return Content-Type: application/octet-stream."""
        # Upload firmware first
        token = client.post(
            "/api/v1/auth/login", json={"api_key": "dev-key"}
        ).get_json()["access_token"]

        client.post(
            "/api/v1/firmware/testproj/device1/upload",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "version": "2.0.0",
                "firmware_b64": base64.b64encode(b"test").decode(),
            },
        )

        response = client.get("/api/v1/firmware/testproj/device1/2.0.0/download")

        assert response.status_code == HTTPStatus.OK
        assert response.content_type == "application/octet-stream"

    def test_download_content_disposition_attachment(self, client):
        """Download should include Content-Disposition: attachment header."""
        # Upload firmware first
        token = client.post(
            "/api/v1/auth/login", json={"api_key": "dev-key"}
        ).get_json()["access_token"]

        client.post(
            "/api/v1/firmware/myproj/nrf52/upload",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "version": "3.0.0",
                "firmware_b64": base64.b64encode(b"nrf firmware").decode(),
            },
        )

        response = client.get("/api/v1/firmware/myproj/nrf52/3.0.0/download")

        assert response.status_code == HTTPStatus.OK
        disposition = response.headers.get("Content-Disposition", "")
        assert "attachment" in disposition
        assert "filename=" in disposition

    def test_download_filename_includes_version(self, client):
        """Downloaded filename should include project, device, and version."""
        # Upload firmware first
        token = client.post(
            "/api/v1/auth/login", json={"api_key": "dev-key"}
        ).get_json()["access_token"]

        client.post(
            "/api/v1/firmware/acme/widget/upload",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "version": "1.2.3",
                "firmware_b64": base64.b64encode(b"widget fw").decode(),
            },
        )

        response = client.get("/api/v1/firmware/acme/widget/1.2.3/download")

        disposition = response.headers.get("Content-Disposition", "")
        # Filename should help identify what was downloaded
        assert (
            "acme" in disposition or "widget" in disposition or "1.2.3" in disposition
        )

    def test_download_nonexistent_returns_404(self, client):
        """Downloading non-existent firmware should return 404."""
        response = client.get("/api/v1/firmware/noproject/nodevice/9.9.9/download")

        assert response.status_code == HTTPStatus.NOT_FOUND
        body = response.get_json()
        assert body["error"] == "version_not_found"

    def test_download_validates_path_traversal_in_project(self, client):
        """Download should reject path traversal attempts in project."""
        response = client.get("/api/v1/firmware/test.bad/device/1.0.0/download")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.get_json()["error"] == "validation_error"

    def test_download_validates_path_traversal_in_device(self, client):
        """Download should reject path traversal attempts in device_type."""
        response = client.get("/api/v1/firmware/project/../etc/1.0.0/download")

        # Flask may normalize or our validation catches it
        assert response.status_code in (HTTPStatus.BAD_REQUEST, HTTPStatus.NOT_FOUND)

    def test_download_validates_invalid_semver(self, client):
        """Download should reject invalid semver in version."""
        response = client.get("/api/v1/firmware/project/device/not-semver/download")

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.get_json()["error"] == "validation_error"

    def test_download_no_auth_required(self, client):
        """Download should work without authentication (public distribution)."""
        # Upload with auth
        token = client.post(
            "/api/v1/auth/login", json={"api_key": "dev-key"}
        ).get_json()["access_token"]

        firmware_content = b"public firmware"
        client.post(
            "/api/v1/firmware/public/device/upload",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "version": "1.0.0",
                "firmware_b64": base64.b64encode(firmware_content).decode(),
            },
        )

        # Download WITHOUT auth - should work
        response = client.get("/api/v1/firmware/public/device/1.0.0/download")

        assert response.status_code == HTTPStatus.OK
        assert response.data == firmware_content

    def test_download_content_length_matches_data(self, client):
        """Content-Length header should match actual response size."""
        # Upload firmware
        token = client.post(
            "/api/v1/auth/login", json={"api_key": "dev-key"}
        ).get_json()["access_token"]

        firmware_content = b"A" * 1000  # 1000 bytes
        client.post(
            "/api/v1/firmware/sizetest/device/upload",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "version": "1.0.0",
                "firmware_b64": base64.b64encode(firmware_content).decode(),
            },
        )

        response = client.get("/api/v1/firmware/sizetest/device/1.0.0/download")

        assert response.status_code == HTTPStatus.OK
        if "Content-Length" in response.headers:
            assert int(response.headers["Content-Length"]) == len(firmware_content)
        assert len(response.data) == len(firmware_content)

    def test_download_binary_integrity(self, client):
        """Downloaded binary should be byte-for-byte identical to uploaded."""
        # Create realistic firmware-like content with various byte values
        firmware_content = bytes(range(256)) * 10  # All byte values repeated

        token = client.post(
            "/api/v1/auth/login", json={"api_key": "dev-key"}
        ).get_json()["access_token"]

        client.post(
            "/api/v1/firmware/integrity/test/upload",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "version": "1.0.0",
                "firmware_b64": base64.b64encode(firmware_content).decode(),
            },
        )

        response = client.get("/api/v1/firmware/integrity/test/1.0.0/download")

        assert response.status_code == HTTPStatus.OK
        assert response.data == firmware_content


class TestDownloadUrlNotExposed:
    """Verify that internal MinIO URLs are not exposed to clients."""

    def test_latest_response_has_download_path_not_minio_url(self, client):
        """The /latest endpoint should provide API download path, not MinIO URL."""
        # Upload firmware
        token = client.post(
            "/api/v1/auth/login", json={"api_key": "dev-key"}
        ).get_json()["access_token"]

        client.post(
            "/api/v1/firmware/urltest/device/upload",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "version": "1.0.0",
                "firmware_b64": base64.b64encode(b"test").decode(),
            },
        )

        response = client.get("/api/v1/firmware/urltest/device/latest")

        assert response.status_code == HTTPStatus.OK
        body = response.get_json()

        # The download_url should NOT contain MinIO internal URLs
        download_url = body.get("download_url", "")
        assert "minio" not in download_url.lower()
        assert "s3" not in download_url.lower()
        assert ":9000" not in download_url

        # Should contain our API path instead (or be null until we update it)
        # After implementation, this should be something like:
        # /api/v1/firmware/urltest/device/1.0.0/download
