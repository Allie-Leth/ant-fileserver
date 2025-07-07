import semver
from marshmallow import Schema, ValidationError, fields


def validate_semver(value: str) -> None:
    """
    Ensure the string is a valid semantic version.
    Raises ValidationError otherwise.
    """

    try:
        semver.VersionInfo.parse(value)
    except ValueError:
        raise ValidationError(f"Invalid semantic version: {value}") from None


class LatestFirmwareQuerySchema(Schema):
    """
    Schema for GET /<project>/<device_type>/latest?current=<version>
    """

    current = fields.Str(
        required=False,
        validate=validate_semver,
        metadata={
            "description": "Your current firmware version (semver); service will return the next higher release."
        },
    )


class FirmwareMetaDataSchema(Schema):
    """
    Serialize the FirmwareMetaData dataclass into JSON.
    """

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
    metadata_version = fields.Int(required=True)
    extra = fields.Dict(required=False)
