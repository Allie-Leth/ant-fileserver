"""Integration tests for health check functionality.

This module tests the health check endpoints with real storage connectivity
to ensure they accurately report system health.
"""

# ruff: noqa: PLC0415 PLR2004
import os

import pytest


@pytest.mark.integration
class TestHealthChecksIntegration:
    """Integration tests for health check endpoints with real dependencies."""

    def test_ready_endpoint_with_real_storage(self, client, s3):
        """Test ready endpoint with actual MinIO connection."""
        # Ensure bucket exists
        bucket = os.environ.get("STORAGE_BUCKET", "test-firmware")
        try:
            s3.head_bucket(Bucket=bucket)
        except Exception:
            s3.create_bucket(Bucket=bucket)

        # Test ready endpoint
        response = client.get("/ready")

        assert response.status_code == 200
        data = response.json
        assert data["ready"] is True
        assert data["checks"]["storage"]["healthy"] is True
        assert data["checks"]["storage"]["error"] is None

    def test_ready_endpoint_with_invalid_storage(self):
        """Test ready endpoint when storage is misconfigured."""
        # Import create_app here to avoid circular imports
        from app import create_app

        # Temporarily override storage config with invalid endpoint
        original_endpoint = os.environ.get("STORAGE_ENDPOINT")
        os.environ["STORAGE_ENDPOINT"] = "http://invalid-host:9999"

        try:
            # Create a new app with invalid storage config
            test_app = create_app("testing")
            with test_app.test_client() as client:
                response = client.get("/ready")

                # Should return 503 when storage is unavailable
                assert response.status_code == 503
                data = response.json
                assert data["ready"] is False
                assert data["checks"]["storage"]["healthy"] is False
                assert data["checks"]["storage"]["error"] is not None
        finally:
            # Restore original endpoint
            if original_endpoint:
                os.environ["STORAGE_ENDPOINT"] = original_endpoint
            else:
                os.environ.pop("STORAGE_ENDPOINT", None)

    def test_health_endpoint_always_healthy(self, client):
        """Test that health endpoint is always healthy regardless of storage."""
        # Even with invalid storage config, health should return 200
        original_endpoint = os.environ.get("STORAGE_ENDPOINT")
        os.environ["STORAGE_ENDPOINT"] = "http://invalid-host:9999"

        try:
            response = client.get("/health")

            assert response.status_code == 200
            data = response.json
            assert data["status"] == "healthy"
        finally:
            if original_endpoint:
                os.environ["STORAGE_ENDPOINT"] = original_endpoint
            else:
                os.environ.pop("STORAGE_ENDPOINT", None)

    def test_metrics_endpoint_uptime(self, client):
        """Test that metrics endpoint reports accurate uptime."""
        # Get metrics immediately
        response1 = client.get("/api/v1/ops/metrics")
        assert response1.status_code == 200
        uptime1 = response1.json["uptime_seconds"]

        # Wait a bit
        import time

        time.sleep(2)

        # Get metrics again
        response2 = client.get("/api/v1/ops/metrics")
        assert response2.status_code == 200
        uptime2 = response2.json["uptime_seconds"]

        # Uptime should have increased
        assert uptime2 > uptime1
        assert uptime2 - uptime1 >= 2  # At least 2 seconds passed
