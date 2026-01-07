"""API tests for operations endpoints.

This module tests the ops blueprint endpoints through the full application
stack to ensure they work correctly without authentication.
"""

# ruff: noqa: PLR2004
import os
from unittest.mock import patch


def test_health_endpoint_no_auth_required(client):
    """Test that /health endpoint does not require authentication."""
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json
    assert data["status"] == "healthy"
    assert data["service"] == "ant-fileserver"


def test_ready_endpoint_no_auth_required(client):
    """Test that /ready endpoint does not require authentication."""
    # Mock storage check to avoid actual connection
    with patch("app.blueprints.ops.routes.check_minio_connectivity") as mock_check:
        mock_check.return_value = (True, None)

        response = client.get("/ready")

        assert response.status_code == 200
        data = response.json
        assert data["ready"] is True


def test_ops_health_endpoint(client):
    """Test the /api/v1/ops/health endpoint."""
    response = client.get("/api/v1/ops/health")

    assert response.status_code == 200
    data = response.json
    assert data["status"] == "healthy"


def test_ops_ready_endpoint(client):
    """Test the /api/v1/ops/ready endpoint."""
    with patch("app.blueprints.ops.routes.check_minio_connectivity") as mock_check:
        mock_check.return_value = (True, None)

        response = client.get("/api/v1/ops/ready")

        assert response.status_code == 200
        data = response.json
        assert data["ready"] is True


def test_ops_metrics_endpoint(client):
    """Test the /api/v1/ops/metrics endpoint."""
    response = client.get("/api/v1/ops/metrics")

    assert response.status_code == 200
    data = response.json

    assert data["service"] == "ant-fileserver"
    assert "uptime_seconds" in data
    assert data["uptime_seconds"] >= 0
    assert "metrics" in data


def test_ready_endpoint_returns_503_when_not_ready(client):
    """Test that /ready returns 503 when dependencies are not healthy."""
    with patch("app.blueprints.ops.routes.check_minio_connectivity") as mock_check:
        mock_check.return_value = (False, "Storage unavailable")

        response = client.get("/ready")

        assert response.status_code == 503
        data = response.json
        assert data["ready"] is False
        assert data["checks"]["storage"]["healthy"] is False
        assert data["checks"]["storage"]["error"] == "Storage unavailable"


def test_health_endpoint_with_version_env(client):
    """Test health endpoint includes version from environment."""
    with patch.dict(os.environ, {"APP_VERSION": "v2.1.0"}):
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json
        assert data["version"] == "v2.1.0"


def test_metrics_endpoint_environment_info(client):
    """Test metrics endpoint includes environment information."""
    with patch.dict(
        os.environ,
        {
            "FLASK_ENV": "production",
            "GUNICORN_WORKERS": "4",
            "PYTHON_VERSION": "3.12.0",
        },
    ):
        response = client.get("/api/v1/ops/metrics")

        assert response.status_code == 200
        data = response.json
        assert data["environment"] == "production"
        assert data["metrics"]["workers"] == 4
        assert data["metrics"]["python_version"] == "3.12.0"


def test_health_endpoints_json_format(client):
    """Test that all health endpoints return proper JSON."""
    endpoints = [
        "/health",
        "/ready",
        "/api/v1/ops/health",
        "/api/v1/ops/ready",
        "/api/v1/ops/metrics",
    ]

    # Mock storage for ready endpoints
    with patch("app.blueprints.ops.routes.check_minio_connectivity") as mock_check:
        mock_check.return_value = (True, None)

        for endpoint in endpoints:
            response = client.get(endpoint)

            # Check content type
            assert response.content_type == "application/json"

            # Check response is valid JSON
            data = response.json
            assert isinstance(data, dict)
            assert (
                "timestamp" in data or endpoint == "/health"
            )  # health doesn't always have timestamp


def test_rate_limiting_not_applied_to_health_checks(client):
    """Test that rate limiting is not applied to health check endpoints."""
    # Make many requests rapidly
    for _ in range(100):
        response = client.get("/health")
        assert response.status_code == 200

    # Ready endpoint should also not be rate limited
    with patch("app.blueprints.ops.routes.check_minio_connectivity") as mock_check:
        mock_check.return_value = (True, None)

        for _ in range(100):
            response = client.get("/ready")
            assert response.status_code == 200
