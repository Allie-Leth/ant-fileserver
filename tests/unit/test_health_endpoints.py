"""Unit tests for health check endpoints.

This module tests the ops blueprint health check endpoints including
liveness, readiness, and metrics endpoints.
"""

# ruff: noqa: PLR2004
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from app.blueprints.ops.routes import check_minio_connectivity, health_bp, ops_bp


class TestHealthEndpoints:
    """Test suite for health check endpoint functionality."""

    @pytest.fixture
    def app(self):
        """Create a minimal Flask app for testing."""
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.config["START_TIME"] = datetime.now(UTC)

        # Register blueprints
        app.register_blueprint(health_bp)
        app.register_blueprint(ops_bp)

        return app

    @pytest.fixture
    def client(self, app):
        """Create a test client."""
        return app.test_client()

    def test_health_endpoint_direct(self, client):
        """Test the direct /health endpoint (liveness probe)."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.get_json()

        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["service"] == "ant-fileserver"
        assert "version" in data

    def test_health_endpoint_ops_prefix(self, client):
        """Test the /api/v1/ops/health endpoint."""
        response = client.get("/api/v1/ops/health")

        assert response.status_code == 200
        data = response.get_json()

        assert data["status"] == "healthy"
        assert data["service"] == "ant-fileserver"

    @patch("app.blueprints.ops.routes.check_minio_connectivity")
    def test_ready_endpoint_healthy(self, mock_check, client):
        """Test the /ready endpoint when storage is healthy."""
        mock_check.return_value = (True, None)

        response = client.get("/ready")

        assert response.status_code == 200
        data = response.get_json()

        assert data["ready"] is True
        assert "timestamp" in data
        assert data["service"] == "ant-fileserver"
        assert data["checks"]["storage"]["healthy"] is True
        assert data["checks"]["storage"]["error"] is None

    @patch("app.blueprints.ops.routes.check_minio_connectivity")
    def test_ready_endpoint_unhealthy(self, mock_check, client):
        """Test the /ready endpoint when storage is unhealthy."""
        mock_check.return_value = (False, "Connection timeout")

        response = client.get("/ready")

        assert response.status_code == 503
        data = response.get_json()

        assert data["ready"] is False
        assert data["checks"]["storage"]["healthy"] is False
        assert data["checks"]["storage"]["error"] == "Connection timeout"

    @patch("app.blueprints.ops.routes.check_minio_connectivity")
    def test_ready_endpoint_ops_prefix(self, mock_check, client):
        """Test the /api/v1/ops/ready endpoint."""
        mock_check.return_value = (True, None)

        response = client.get("/api/v1/ops/ready")

        assert response.status_code == 200
        data = response.get_json()
        assert data["ready"] is True

    def test_metrics_endpoint(self, client):
        """Test the /api/v1/ops/metrics endpoint."""
        response = client.get("/api/v1/ops/metrics")

        assert response.status_code == 200
        data = response.get_json()

        assert "timestamp" in data
        assert data["service"] == "ant-fileserver"
        assert "version" in data
        assert "uptime_seconds" in data
        assert data["uptime_seconds"] >= 0
        assert "environment" in data
        assert "metrics" in data
        assert "python_version" in data["metrics"]
        assert "workers" in data["metrics"]

    @patch("app.blueprints.ops.routes.boto3.client")
    def test_check_minio_connectivity_success(self, mock_boto_client, app):
        """Test MinIO connectivity check when successful."""
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3

        with app.app_context():
            app.config["STORAGE_ENDPOINT"] = "http://minio:9000"
            app.config["STORAGE_BUCKET"] = "test-bucket"
            app.config["STORAGE_ACCESS_KEY_ID"] = "test-key"
            app.config["STORAGE_SECRET_ACCESS_KEY"] = "test-secret"

            is_healthy, error = check_minio_connectivity()

            assert is_healthy is True
            assert error is None
            mock_s3.head_bucket.assert_called_once_with(Bucket="test-bucket")

    @patch("app.blueprints.ops.routes.boto3.client")
    def test_check_minio_connectivity_failure(self, mock_boto_client, app):
        """Test MinIO connectivity check when it fails."""
        mock_s3 = MagicMock()
        mock_s3.head_bucket.side_effect = Exception("Connection refused")
        mock_boto_client.return_value = mock_s3

        with app.app_context():
            app.config["STORAGE_ENDPOINT"] = "http://minio:9000"
            app.config["STORAGE_BUCKET"] = "test-bucket"
            app.config["STORAGE_ACCESS_KEY_ID"] = "test-key"
            app.config["STORAGE_SECRET_ACCESS_KEY"] = "test-secret"

            is_healthy, error = check_minio_connectivity()

            assert is_healthy is False
            assert "Connection refused" in error

    @patch.dict("os.environ", {}, clear=True)
    def test_check_minio_connectivity_missing_config(self, app):
        """Test MinIO connectivity check with missing configuration."""
        with app.app_context():
            # Clear all config
            app.config.pop("STORAGE_ENDPOINT", None)
            app.config.pop("STORAGE_BUCKET", None)
            app.config.pop("STORAGE_ACCESS_KEY_ID", None)
            app.config.pop("STORAGE_SECRET_ACCESS_KEY", None)

            is_healthy, error = check_minio_connectivity()

            assert is_healthy is False
            assert "Storage configuration incomplete" in error

    @patch.dict("os.environ", {"APP_VERSION": "1.2.3"})
    def test_version_from_environment(self, client):
        """Test that version is read from environment variable."""
        response = client.get("/health")
        data = response.get_json()

        assert data["version"] == "1.2.3"

    @patch.dict("os.environ", {}, clear=True)
    def test_version_default(self, client):
        """Test default version when environment variable is not set."""
        response = client.get("/health")
        data = response.get_json()

        assert data["version"] == "unknown"
