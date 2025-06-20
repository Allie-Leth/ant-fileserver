from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity

auth_bp = Blueprint("auth", __name__)
jwt = JWTManager()

@auth_bp.route("/login", methods=["POST"])
def login():
    """
    POST /api/v1/auth/login
    Body: { "api_key": "<key>" }
    """
    payload = request.get_json(silent=True) or {}
    key = payload.get("api_key") or request.headers.get("X-API-KEY")
    
    roles_map = current_app.config["API_KEY_ROLES"]
    roles = roles_map.get(key)
    if not roles:
        return jsonify({"error":"invalid_credentials"}), 401

    # Build JWT identity with the key and its roles array
    identity_payload = {"key": key, "roles": roles}
    token = create_access_token(identity=identity_payload)
    return jsonify({"access_token": token}), 200

@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    """
    POST /api/v1/auth/refresh
    Headers: Authorization: Bearer <refresh_token>
    Returns a new access token.
    """
    identity = get_jwt_identity()
    new_token = create_access_token(identity=identity)
    return jsonify({"access_token": new_token}), 200

@auth_bp.route("/whoami", methods=["GET"])
@jwt_required()
def whoami():
    """
    GET /api/v1/auth/whoami
    Returns the decoded JWT identity payload.
    """
    return jsonify(get_jwt_identity()), 200


@auth_bp.route("/<project>/<device_type>/upload", methods=["POST"])
@jwt_required()
def upload_firmware(project: str, device_type: str, svc):
    """
    POST /api/v1/auth/<project>/<device_type>/upload
    Protected endpoint for pushing new firmware.
    Requires the caller’s JWT identity to include the "uploader" role.
    """
    identity = get_jwt_identity()
    if "uploader" not in identity.get("roles", []):
        return jsonify({"error": "forbidden"}), 403

    # Delegate to server layer
    data = request.get_json(force=True)
    svc.upload_firmware(project, device_type, data)
    return "", 204