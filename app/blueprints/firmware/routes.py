from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from marshmallow import ValidationError

from .schema import (
    LatestFirmwareQuerySchema,
    FirmwareMetaDataSchema,
)

from app.models import FirmwareMetaData
from app.errors import FirmwareError

firmware_bp = Blueprint("firmware", __name__)

@firmware_bp.route("/<project>/<device_type>", methods=["GET"])
def list_all(project: str, device_type: str, svc):
    """
    GET /api/v1/firmware/<project>/<device_type>
    Returns a list of all firmware metadata (no download URLs).
    """
    # No query params, just list all versions
    meta: list[FirmwareMetaData] = svc.list_firmware(project, device_type)
    
    # Optional ?with_urls=true to embed presigned links in every item
    if request.args.get("with_urls", "").lower() in {"1", "true", "yes"}:
        for m in meta:
            m.download_url = svc.generate_presigned_url(
                project, device_type, m.version
            )
    # Attach a temporary download URL so clients can fetch right away
    meta.download_url = svc.generate_presigned_url(
        project, device_type, meta.version
    )

    # Serialize
    result = FirmwareMetaDataSchema().dump(meta)
    
    return jsonify(result), 200

@firmware_bp.route("/<project>/<device_type>/latest", methods=["GET"])
def get_latest(project: str, device_type: str, svc):
    """
    GET /api/v1/firmware/<project>/<device_type>/latest?current=<semver>
    Returns the next firmware after `current`, or the latest if none specified.
    """
    try: 
        # Validate query string
        params = LatestFirmwareQuerySchema().load(request.args)
        current = params.get("current")
        
        # Call Service
        meta: FirmwareMetaData = svc.get_latest(
            project, device_type, current_version=current
        )
        
        # Serialize
        result = FirmwareMetaDataSchema().dump(meta)
        return jsonify(result), 200
    
    except ValidationError as ve:
        return jsonify({"error": "validation_error", "message": str(ve)}), 400
    
@firmware_bp.post("/<project>/<device_type>/upload")
@jwt_required()
def upload(project: str, device_type: str, svc):
    """
    POST /api/v1/firmware/<project>/<device_type>/upload
    Body: JSON described in FirmwareService.upload_firmware().
    Requires 'uploader' role.
    """
    identity = get_jwt()
    if "uploader" not in identity["roles"]:
        return jsonify({"error": "forbidden"}), 403

    payload = request.get_json(force=True, silent=True) or {}
    svc.upload_firmware(project, device_type, payload)
    return "", 204