"""Schemas for factory file API.

Defines:
- VALID_FILE_TYPES: set of allowed file types (bootloader, partition-table)
- FLASH_ADDRESSES: mapping of file types to flash addresses
- validate_file_type: validator for file type enum
- FactoryFileMetaDataSchema: for serializing factory file metadata
"""

from marshmallow import Schema, ValidationError, fields

# Valid factory file types - only bootloader and partition table allowed
VALID_FILE_TYPES = {"bootloader", "partition-table"}

# Flash addresses for each file type (ESP32-S3 with 8MB flash)
FLASH_ADDRESSES = {
    "bootloader": 0x0,
    "partition-table": 0x8000,
}


def validate_file_type(value: str) -> None:
    """Validate file_type is a known enum value.

    Only 'bootloader' and 'partition-table' are allowed.
    Case-sensitive.

    Args:
        value: The file_type string to validate.

    Raises:
        ValidationError: if the value is not a valid file type.
    """
    if value not in VALID_FILE_TYPES:
        raise ValidationError(
            f"Invalid file_type: {value!r}. Must be one of: {sorted(VALID_FILE_TYPES)}"
        )


class FactoryFileMetaDataSchema(Schema):
    """Schema that serializes a FactoryFileMetaData dataclass to JSON."""

    device_type = fields.Str(required=True)
    file_type = fields.Str(required=True)
    version = fields.Str(required=True)
    checksum = fields.Str(required=True)
    checksum_algo = fields.Str(required=True)
    file_size = fields.Int(required=True)
    upload_date = fields.DateTime(required=True)
    flash_address = fields.Int(required=True)
    download_url = fields.Str(dump_only=True, load_default=None)
