"""Firmware blueprint routes.

Endpoints for listing all firmware, retrieving the next/latest firmware,
and uploading new firmware for a given project and device type.
"""

import dataclasses
import logging

from flask import Blueprint, Response, current_app, jsonify, request
from flask_jwt_extended import get_jwt, jwt_required
from marshmallow import ValidationError

from app.blueprints.firmware.schema import (
    FirmwareMetaDataSchema,
    LatestFirmwareQuerySchema,
    validate_path_segment,
    validate_semver,
)
from app.errors import FileNotFoundError as FactoryFileNotFoundError
from app.errors import VersionNotFoundError
from app.models import FirmwareMetaData

firmware_bp = Blueprint("firmware", __name__)
logger = logging.getLogger(__name__)


def _build_download_url(project: str, device_type: str, version: str) -> str:
    """Build public download URL for firmware binary.

    Uses PUBLIC_BASE_URL config to generate externally accessible URLs
    pointing to the fileserver's download endpoint.
    """
    base_url = current_app.config["PUBLIC_BASE_URL"].rstrip("/")
    return f"{base_url}/api/v1/firmware/{project}/{device_type}/{version}/download"


def _build_factory_download_url(device_type: str, file_type: str, version: str) -> str:
    """Build public download URL for factory file binary.

    Uses PUBLIC_BASE_URL config to generate externally accessible URLs
    pointing to the factory file download endpoint.
    """
    base_url = current_app.config["PUBLIC_BASE_URL"].rstrip("/")
    return f"{base_url}/api/v1/factory/{device_type}/{file_type}/{version}"


@firmware_bp.route("/<project>/<device_type>", methods=["GET"])
def list_all(project: str, device_type: str):
    """List all firmware metadata for a project and device type.

    GET /api/v1/firmware/<project>/<device_type>
    Returns a list of all firmware metadata (no download URLs).
    """
    # Validate path parameters to prevent path traversal
    try:
        validate_path_segment(project)
        validate_path_segment(device_type)
    except ValidationError as ve:
        return jsonify({"error": "validation_error", "message": str(ve)}), 400

    svc = current_app.firmware_service
    # No query params, just list all versions
    metas: list[FirmwareMetaData] = svc.list_firmware(project, device_type)

    # Optional ?with_urls=true to embed download links in every item
    if request.args.get("with_urls", "").lower() in {"1", "true", "yes"}:
        metas = [
            dataclasses.replace(
                m,
                download_url=_build_download_url(project, device_type, m.version),
            )
            for m in metas
        ]

    # Serialize
    result = FirmwareMetaDataSchema(many=True).dump(metas)

    return jsonify(result), 200


@firmware_bp.route("/<project>/<device_type>/latest", methods=["GET"])
def get_latest(project: str, device_type: str):
    """Get the next firmware after `current`, or the latest if none specified.

    GET /api/v1/firmware/<project>/<device_type>/latest?current=<semver>
    Returns the next firmware after `current`, or the latest if up-to-date.

    GET /api/v1/firmware/<project>/<device_type>/latest?include_factory=true
    Additionally includes factory_files array with bootloader and partition-table
    metadata when the firmware specifies factory version references.
    """
    # Validate path parameters to prevent path traversal
    try:
        validate_path_segment(project)
        validate_path_segment(device_type)
    except ValidationError as ve:
        return jsonify({"error": "validation_error", "message": str(ve)}), 400

    svc = current_app.firmware_service
    try:
        # Validate query string
        params = LatestFirmwareQuerySchema().load(request.args)
        current = params.get("current")
        include_factory = params.get("include_factory", False)

        # Call Service
        meta: FirmwareMetaData = svc.get_latest(
            project, device_type, current_version=current
        )

        # Add public download URL (immutable object → create a copy)
        meta = dataclasses.replace(
            meta,
            download_url=_build_download_url(project, device_type, meta.version),
        )

        # Serialize
        result = FirmwareMetaDataSchema().dump(meta)

        # Include factory files if requested
        if include_factory:
            result["factory_files"] = _get_factory_files(device_type, meta)

        return jsonify(result), 200

    except ValidationError as ve:
        return jsonify({"error": "validation_error", "message": str(ve)}), 400


def _get_factory_files(device_type: str, meta: FirmwareMetaData) -> list[dict]:
    """Fetch factory file metadata for firmware's referenced versions.

    Args:
        device_type: The hardware device type
        meta: Firmware metadata containing bootloader_version and/or partition_table_version

    Returns:
        List of factory file info dicts with file_type, version, flash_address,
        checksum, and download_url.
    """
    factory_svc = current_app.factory_service
    factory_files = []

    # Map of firmware field -> factory file type
    factory_refs = [
        ("bootloader_version", "bootloader"),
        ("partition_table_version", "partition-table"),
    ]

    for fw_field, file_type in factory_refs:
        version = getattr(meta, fw_field, None)
        if not version:
            continue

        try:
            factory_meta = factory_svc.get_metadata(device_type, file_type, version)
            factory_files.append(
                {
                    "file_type": file_type,
                    "version": factory_meta.version,
                    "flash_address": factory_meta.flash_address,
                    "checksum": factory_meta.checksum,
                    "download_url": _build_factory_download_url(
                        device_type, file_type, version
                    ),
                }
            )
        except FactoryFileNotFoundError:
            logger.warning(
                "Factory file %s/%s v%s referenced by firmware but not found",
                device_type,
                file_type,
                version,
            )
            # Skip missing factory files - don't fail the request
            continue

    return factory_files


@firmware_bp.post("/<project>/<device_type>/upload")
@jwt_required()
def upload(project: str, device_type: str):
    """Upload a new firmware binary and metadata.

    POST /api/v1/firmware/<project>/<device_type>/upload
    Body: JSON as defined by `FirmwareService.upload_firmware()`.
    Requires the 'uploader' role in your JWT.
    """
    # Validate path parameters to prevent path traversal
    try:
        validate_path_segment(project)
        validate_path_segment(device_type)
    except ValidationError as ve:
        return jsonify({"error": "validation_error", "message": str(ve)}), 400

    svc = current_app.firmware_service
    identity = get_jwt()
    if "uploader" not in identity["roles"]:
        return jsonify({"error": "forbidden"}), 403

    payload = request.get_json(force=True, silent=True) or {}
    svc.upload_firmware(project, device_type, payload)
    return "", 204


@firmware_bp.route("/<project>/<device_type>/<version>/download", methods=["GET"])
def download(project: str, device_type: str, version: str):
    """Download firmware binary.

    GET /api/v1/firmware/<project>/<device_type>/<version>/download
    Returns the raw firmware binary with appropriate headers.
    No authentication required (public firmware distribution).
    """
    # Validate path parameters to prevent path traversal
    try:
        validate_path_segment(project)
        validate_path_segment(device_type)
        validate_semver(version)
    except ValidationError as ve:
        return jsonify({"error": "validation_error", "message": str(ve)}), 400

    svc = current_app.firmware_service

    try:
        binary_data = svc.get_firmware_binary(project, device_type, version)
    except VersionNotFoundError:
        return jsonify(
            {"error": "version_not_found", "message": "Firmware not found"}
        ), 404

    # Build filename for Content-Disposition
    filename = f"{project}-{device_type}-{version}.bin"

    return Response(
        binary_data,
        status=200,
        mimetype="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(binary_data)),
        },
    )
