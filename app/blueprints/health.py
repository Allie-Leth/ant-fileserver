"""Health check endpoints for Kubernetes probes.

Provides /health (liveness) and /ready (readiness) endpoints.
"""

from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.route("/health", methods=["GET"])
def health():
    """Liveness probe endpoint.
    
    Returns 200 if the application is running.
    Used by Kubernetes to determine if the pod should be restarted.
    """
    return jsonify({"status": "healthy"}), 200


@health_bp.route("/ready", methods=["GET"])
def ready():
    """Readiness probe endpoint.
    
    Returns 200 if the application is ready to receive traffic.
    In the future, this could check MinIO connectivity.
    """
    # For now, we just return ready if the app is running
    # In production, you'd check:
    # - MinIO connectivity
    # - Database if used
    # - Other critical dependencies
    
    return jsonify({"status": "ready"}), 200