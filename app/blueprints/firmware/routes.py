from flask import Blueprint, request, jsonify
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
    metas: list[FirmwareMetaData] = svc.list_firmware(project, device_type)
    # Dump many= True to serialize a list
    result = FirmwareMetaDataSchema(many=True).dump(metas)
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