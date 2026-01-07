"""Operations endpoints for health checks and monitoring.

This module provides health check endpoints for Kubernetes liveness and
readiness probes. These endpoints do not require authentication.
"""

import os
from datetime import UTC, datetime

import boto3
from botocore.exceptions import BotoCoreError
from flask import Blueprint, current_app, jsonify

from app.extensions import limiter

ops_bp = Blueprint("ops", __name__, url_prefix="/api/v1/ops")

# Also register health endpoints without /api/v1/ops prefix for easier access
health_bp = Blueprint("health", __name__)


def check_minio_connectivity():
    """Check if MinIO/S3 storage is accessible.

    Returns:
        Tuple of (is_healthy, error_message)
    """
    try:
        # Get storage configuration from app config or environment
        endpoint_url = current_app.config.get(
            "STORAGE_ENDPOINT", os.environ.get("STORAGE_ENDPOINT")
        )
        bucket = current_app.config.get(
            "STORAGE_BUCKET", os.environ.get("STORAGE_BUCKET")
        )
        access_key = current_app.config.get(
            "STORAGE_ACCESS_KEY_ID", os.environ.get("STORAGE_ACCESS_KEY_ID")
        )
        secret_key = current_app.config.get(
            "STORAGE_SECRET_ACCESS_KEY", os.environ.get("STORAGE_SECRET_ACCESS_KEY")
        )
        region = current_app.config.get(
            "STORAGE_REGION", os.environ.get("STORAGE_REGION", "us-east-1")
        )

        if not all([endpoint_url, bucket, access_key, secret_key]):
            return False, "Storage configuration incomplete"

        # Create S3 client
        s3_client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )

        # Try to check if bucket exists
        s3_client.head_bucket(Bucket=bucket)
        return True, None

    except BotoCoreError as e:
        return False, f"Storage error: {str(e)}"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"


@health_bp.route("/health")
@ops_bp.route("/health")
@limiter.exempt
def health():
    """Liveness probe endpoint for Kubernetes.

    This endpoint indicates whether the application is running and able
    to handle requests. It does not check external dependencies.

    Returns:
        JSON response with health status
    """
    return jsonify(
        {
            "status": "healthy",
            "timestamp": datetime.now(UTC).isoformat(),
            "service": "ant-fileserver",
            "version": os.environ.get("APP_VERSION", "unknown"),
        }
    ), 200


@health_bp.route("/ready")
@ops_bp.route("/ready")
@limiter.exempt
def ready():
    """Readiness probe endpoint for Kubernetes.

    This endpoint indicates whether the application is ready to serve
    traffic. It checks critical dependencies like storage connectivity.

    Returns:
        JSON response with readiness status
    """
    # Check MinIO connectivity
    storage_healthy, storage_error = check_minio_connectivity()

    # Overall readiness
    is_ready = storage_healthy

    # Build response
    response = {
        "ready": is_ready,
        "timestamp": datetime.now(UTC).isoformat(),
        "service": "ant-fileserver",
        "version": os.environ.get("APP_VERSION", "unknown"),
        "checks": {"storage": {"healthy": storage_healthy, "error": storage_error}},
    }

    # Return 200 if ready, 503 if not ready
    status_code = 200 if is_ready else 503
    return jsonify(response), status_code


@ops_bp.route("/metrics")
@limiter.exempt
def metrics():
    """Basic metrics endpoint.

    This endpoint provides basic application metrics. In production,
    this could be extended to provide Prometheus-compatible metrics.

    Returns:
        JSON response with basic metrics
    """
    # Get basic metrics
    uptime_seconds = int(
        (
            datetime.now(UTC) - current_app.config.get("START_TIME", datetime.now(UTC))
        ).total_seconds()
    )

    return jsonify(
        {
            "timestamp": datetime.now(UTC).isoformat(),
            "service": "ant-fileserver",
            "version": os.environ.get("APP_VERSION", "unknown"),
            "uptime_seconds": uptime_seconds,
            "environment": os.environ.get("FLASK_ENV", "production"),
            "metrics": {
                "python_version": os.environ.get("PYTHON_VERSION", "unknown"),
                "workers": int(os.environ.get("GUNICORN_WORKERS", "1")),
            },
        }
    ), 200
