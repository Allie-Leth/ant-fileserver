"""Schemas for firmware API.

Defines:
- `validate_semver`: custom validator for semantic versions.
- `validate_path_segment`: validator for URL path segments (project, device_type).
- `LatestFirmwareQuerySchema`: for querying the latest firmware.
- `FirmwareMetaDataSchema`: for serializing firmware metadata.
"""

import re

import semver
from marshmallow import Schema, ValidationError, fields

# Safe pattern for path segments: alphanumeric, hyphens, underscores only
# No dots (prevents ../ traversal), no slashes, no special chars
PATH_SEGMENT_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")


def validate_path_segment(value: str) -> None:
    """Validate a URL path segment (project or device_type).

    Allows alphanumeric characters, hyphens, and underscores.
    Must start with alphanumeric, max 64 chars.
    Rejects path traversal attempts (../, ./, etc).

    Raises:
        ValidationError: if the string contains unsafe characters.
    """
    if not value or not PATH_SEGMENT_PATTERN.match(value):
        raise ValidationError(
            f"Invalid path segment: {value!r}. "
            "Must be 1-64 alphanumeric characters, hyphens, or underscores, "
            "starting with alphanumeric."
        )


def validate_semver(value: str) -> None:
    """Ensure the string is a valid semantic version.

    Raises:
        ValidationError: if the string is not valid semver.
    """
    try:
        semver.VersionInfo.parse(value)
    except ValueError:
        raise ValidationError(f"Invalid semantic version: {value}") from None


class LatestFirmwareQuerySchema(Schema):
    """Query-string schema for `GET /<project>/<device_type>/latest?current=<version>`."""

    current = fields.Str(
        required=False,
        validate=validate_semver,
        metadata={
            "description": "Your current firmware version (semver); "
            "service will return the next higher release."
        },
    )
    include_factory = fields.Bool(
        required=False,
        load_default=False,
        metadata={
            "description": "If true, include factory file metadata (bootloader, partition-table) "
            "in the response when the firmware specifies factory version references."
        },
    )


class FirmwareMetaDataSchema(Schema):
    """Schema that serializes a `FirmwareMetaData` dataclass to JSON."""

    project = fields.Str(required=True)
    device_type = fields.Str(required=True)
    version = fields.Str(required=True, validate=validate_semver)
    checksum = fields.Str(required=True)
    checksum_algo = fields.Str(required=True)
    file_size = fields.Int(required=True)
    download_url = fields.Url(required=False, dump_only=True)
    release_notes = fields.Str(required=True)
    release_date = fields.DateTime(required=True)  # ISO8601 output
    channel = fields.Str(required=True)
    mandatory = fields.Bool(required=True)
    signature = fields.Str(required=False)
    min_bootloader = fields.Str(required=False)
    bootloader_version = fields.Str(required=False)
    partition_table_version = fields.Str(required=False)
    metadata_version = fields.Int(required=True)
    extra = fields.Dict(required=False)
