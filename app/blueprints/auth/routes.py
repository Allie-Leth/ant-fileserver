"""Auth Blueprint routes.

Provides endpoints for:
  - POST /api/v1/auth/login: authenticate with an API key and receive a JWT access token.
  - POST /api/v1/auth/refresh: refresh an existing JWT access token.
  - GET  /api/v1/auth/whoami:  return the caller’s API key and roles.
"""

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)

auth_bp = Blueprint("auth", __name__)


# POST /api/v1/auth/login
@auth_bp.route("/login", methods=["POST"])
def login():
    """Authenticate using an API key and return a JWT access token.

    Body JSON or header:
      { "api_key": "<key>" }   OR   X-API-KEY: <key>

    Returns:
      { "access_token": "<JWT>" }
    """
    payload = request.get_json(silent=True) or {}
    key = payload.get("api_key") or request.headers.get("X-API-KEY")

    roles_map = current_app.config["API_KEY_ROLES"]
    roles = roles_map.get(key)
    if not roles:
        return jsonify({"error": "invalid_credentials"}), 401

    token = create_access_token(
        identity=key,
        additional_claims={"roles": roles},
    )
    return jsonify({"access_token": token}), 200


# POST /api/v1/auth/refresh
@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    """Refresh an access token using a valid refresh token.

    Headers:
      Authorization: Bearer <refresh_token>

    Returns:
      { "access_token": "<new_JWT>" }
    """
    identity = get_jwt_identity()
    roles = get_jwt().get("roles", [])
    new_token = create_access_token(
        identity=identity,
        additional_claims={"roles": roles},
    )
    return jsonify({"access_token": new_token}), 200


# GET /api/v1/auth/whoami
@auth_bp.route("/whoami", methods=["GET"])
@jwt_required()
def whoami():
    """Returns the caller’s API key and roles as JSON."""
    return (
        jsonify(
            {
                "key": get_jwt_identity(),  # string
                "roles": get_jwt().get("roles", []),
            }
        ),
        200,
    )
