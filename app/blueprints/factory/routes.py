"""Factory blueprint routes.

Endpoints for factory file operations (bootloader, partition-table).
These files are set once at manufacturing and rarely change.
"""

from dataclasses import replace

from flask import Blueprint, Response, current_app, jsonify, request
from flask_jwt_extended import get_jwt, jwt_required
from marshmallow import ValidationError

from app.blueprints.factory.schema import FactoryFileMetaDataSchema, validate_file_type
from app.blueprints.firmware.schema import validate_path_segment, validate_semver
from app.errors import FileNotFoundError

factory_bp = Blueprint("factory", __name__)


@factory_bp.route("/<device_type>/<file_type>/<version>", methods=["GET"])
def download(device_type: str, file_type: str, version: str):
    """Download a specific version of a factory file.

    GET /api/v1/factory/<device_type>/<file_type>/<version>
    Public endpoint (no authentication required).

    Returns:
        Raw binary file with appropriate headers.
    """
    # Validate parameters
    try:
        validate_path_segment(device_type)
        validate_file_type(file_type)
        validate_semver(version)
    except ValidationError as ve:
        return jsonify({"error": "validation_error", "message": str(ve)}), 400

    svc = current_app.factory_service

    try:
        binary_data = svc.get_file(device_type, file_type, version)
    except FileNotFoundError:
        return jsonify(
            {"error": "file_not_found", "message": "Factory file not found"}
        ), 404

    filename = f"{device_type}-{file_type}-{version}.bin"
    return Response(
        binary_data,
        status=200,
        mimetype="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(binary_data)),
        },
    )


@factory_bp.route("/<device_type>/<file_type>/<version>/info", methods=["GET"])
def get_info(device_type: str, file_type: str, version: str):
    """Get factory file metadata for a specific version.

    GET /api/v1/factory/<device_type>/<file_type>/<version>/info
    Returns metadata including checksum, size, version, and flash address.
    """
    # Validate parameters
    try:
        validate_path_segment(device_type)
        validate_file_type(file_type)
        validate_semver(version)
    except ValidationError as ve:
        return jsonify({"error": "validation_error", "message": str(ve)}), 400

    svc = current_app.factory_service

    try:
        meta = svc.get_metadata(device_type, file_type, version)
    except FileNotFoundError:
        return jsonify(
            {"error": "file_not_found", "message": "Factory file not found"}
        ), 404

    result = FactoryFileMetaDataSchema().dump(meta)
    return jsonify(result), 200


@factory_bp.route("/<device_type>/<file_type>/latest", methods=["GET"])
def get_latest(device_type: str, file_type: str):
    """Get metadata for the latest version of a factory file.

    GET /api/v1/factory/<device_type>/<file_type>/latest
    Returns metadata for the highest semver version.
    """
    # Validate parameters
    try:
        validate_path_segment(device_type)
        validate_file_type(file_type)
    except ValidationError as ve:
        return jsonify({"error": "validation_error", "message": str(ve)}), 400

    svc = current_app.factory_service

    try:
        meta = svc.get_latest(device_type, file_type)
    except FileNotFoundError:
        return jsonify({"error": "file_not_found", "message": "No versions found"}), 404

    # Build download URL for the latest version
    base_url = current_app.config.get("PUBLIC_BASE_URL", "").rstrip("/")
    download_url = f"{base_url}/api/v1/factory/{device_type}/{file_type}/{meta.version}"

    # Create new metadata with download_url
    meta_with_url = replace(meta, download_url=download_url)

    result = FactoryFileMetaDataSchema().dump(meta_with_url)
    return jsonify(result), 200


@factory_bp.route("/<device_type>/<file_type>/versions", methods=["GET"])
def list_versions(device_type: str, file_type: str):
    """List all versions of a factory file.

    GET /api/v1/factory/<device_type>/<file_type>/versions
    Returns an array of version metadata.
    """
    # Validate parameters
    try:
        validate_path_segment(device_type)
        validate_file_type(file_type)
    except ValidationError as ve:
        return jsonify({"error": "validation_error", "message": str(ve)}), 400

    svc = current_app.factory_service
    metas = svc.list_versions(device_type, file_type)

    result = FactoryFileMetaDataSchema(many=True).dump(metas)
    return jsonify(result), 200


@factory_bp.post("/<device_type>/<file_type>/upload")
@jwt_required()
def upload(device_type: str, file_type: str):
    """Upload a versioned factory file.

    POST /api/v1/factory/<device_type>/<file_type>/upload
    Requires authentication with 'uploader' role.

    Body: JSON with 'version' (required), 'file_b64' (base64-encoded binary),
    and optional 'checksum'. Each version can only be uploaded once.
    """
    # Validate parameters
    try:
        validate_path_segment(device_type)
        validate_file_type(file_type)
    except ValidationError as ve:
        return jsonify({"error": "validation_error", "message": str(ve)}), 400

    # Check authorization
    identity = get_jwt()
    if "uploader" not in identity.get("roles", []):
        return jsonify({"error": "forbidden"}), 403

    svc = current_app.factory_service
    payload = request.get_json(force=True, silent=True) or {}

    svc.upload_file(device_type, file_type, payload)
    return "", 204


@factory_bp.route("/<device_type>", methods=["GET"])
def list_files(device_type: str):
    """List all factory files for a device type.

    GET /api/v1/factory/<device_type>
    Returns an array of file metadata.
    """
    # Validate parameters
    try:
        validate_path_segment(device_type)
    except ValidationError as ve:
        return jsonify({"error": "validation_error", "message": str(ve)}), 400

    svc = current_app.factory_service
    metas = svc.list_files(device_type)

    result = FactoryFileMetaDataSchema(many=True).dump(metas)
    return jsonify(result), 200
