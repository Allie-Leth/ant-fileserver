"""Firmware blueprint routes.

Endpoints for listing all firmware, retrieving the next/latest firmware,
and uploading new firmware for a given project and device type.
"""

import dataclasses

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt, jwt_required
from marshmallow import ValidationError

from app.blueprints.firmware.schema import (
    FirmwareMetaDataSchema,
    LatestFirmwareQuerySchema,
)
from app.models import FirmwareMetaData

firmware_bp = Blueprint("firmware", __name__)


@firmware_bp.route("/<project>/<device_type>", methods=["GET"])
def list_all(project: str, device_type: str, svc):
    """List all firmware metadata for a project and device type.

    GET /api/v1/firmware/<project>/<device_type>
    Returns a list of all firmware metadata (no download URLs).
    """
    # No query params, just list all versions
    metas: list[FirmwareMetaData] = svc.list_firmware(project, device_type)

    # Optional ?with_urls=true to embed presigned links in every item
    if request.args.get("with_urls", "").lower() in {"1", "true", "yes"}:
        metas = [
            dataclasses.replace(
                m,
                download_url=svc.generate_presigned_url(
                    project, device_type, m.version
                ),
            )
            for m in metas
        ]

    # Serialize
    result = FirmwareMetaDataSchema(many=True).dump(metas)

    return jsonify(result), 200


@firmware_bp.route("/<project>/<device_type>/latest", methods=["GET"])
def get_latest(project: str, device_type: str, svc):
    """Get the next firmware after `current`, or the latest if none specified.

    GET /api/v1/firmware/<project>/<device_type>/latest?current=<semver>
    Returns the next firmware after `current`, or the latest if up-to-date.
    """
    try:
        # Validate query string
        params = LatestFirmwareQuerySchema().load(request.args)
        current = params.get("current")

        # Call Service
        meta: FirmwareMetaData = svc.get_latest(
            project, device_type, current_version=current
        )

        # Add presigned URL (immutable object → create a copy)
        meta = dataclasses.replace(
            meta,
            download_url=svc.generate_presigned_url(project, device_type, meta.version),
        )

        # Serialize
        result = FirmwareMetaDataSchema().dump(meta)
        return jsonify(result), 200

    except ValidationError as ve:
        return jsonify({"error": "validation_error", "message": str(ve)}), 400


@firmware_bp.post("/<project>/<device_type>/upload")
@jwt_required()
def upload(project: str, device_type: str, svc):
    """Upload a new firmware binary and metadata.

    POST /api/v1/firmware/<project>/<device_type>/upload
    Body: JSON as defined by `FirmwareService.upload_firmware()`.
    Requires the 'uploader' role in your JWT.
    """
    identity = get_jwt()
    if "uploader" not in identity["roles"]:
        return jsonify({"error": "forbidden"}), 403

    payload = request.get_json(force=True, silent=True) or {}
    svc.upload_firmware(project, device_type, payload)
    return "", 204
