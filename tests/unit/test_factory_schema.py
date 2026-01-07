# ruff: noqa: PLC0415,PLR2004   # imports inside tests, magic values in assertions
"""Unit tests for factory file schema validation.

Tests for:
- validate_file_type: validates file_type is a known enum value
- VALID_FILE_TYPES: set of allowed file types
- FLASH_ADDRESSES: mapping of file types to flash addresses
"""

import pytest
from marshmallow import ValidationError


class TestValidateFileType:
    """Tests for the validate_file_type function."""

    @pytest.mark.parametrize("value", ["bootloader", "partition-table"])
    def test_valid_file_types_accepted(self, value):
        """Valid file types should not raise."""
        from app.blueprints.factory.schema import validate_file_type

        validate_file_type(value)  # Should not raise

    @pytest.mark.parametrize(
        "value",
        [
            "firmware",  # Not a factory file
            "config",  # Not allowed
            "../etc",  # Path traversal attempt
            "",  # Empty
            "BOOTLOADER",  # Case-sensitive
            "partition_table",  # Wrong separator
            "boot loader",  # Space not allowed
        ],
    )
    def test_invalid_file_types_rejected(self, value):
        """Invalid file types should raise ValidationError."""
        from app.blueprints.factory.schema import validate_file_type

        with pytest.raises(ValidationError) as exc_info:
            validate_file_type(value)
        assert "Invalid file_type" in str(exc_info.value)


class TestFlashAddresses:
    """Tests for the FLASH_ADDRESSES constant."""

    def test_bootloader_flash_address_is_zero(self):
        """Bootloader should flash at address 0x0."""
        from app.blueprints.factory.schema import FLASH_ADDRESSES

        assert FLASH_ADDRESSES["bootloader"] == 0x0

    def test_partition_table_flash_address(self):
        """Partition table should flash at address 0x8000."""
        from app.blueprints.factory.schema import FLASH_ADDRESSES

        assert FLASH_ADDRESSES["partition-table"] == 0x8000

    def test_all_valid_types_have_addresses(self):
        """Every valid file type must have a flash address."""
        from app.blueprints.factory.schema import FLASH_ADDRESSES, VALID_FILE_TYPES

        for file_type in VALID_FILE_TYPES:
            assert file_type in FLASH_ADDRESSES


class TestValidFileTypes:
    """Tests for the VALID_FILE_TYPES constant."""

    def test_contains_bootloader(self):
        """Bootloader must be a valid file type."""
        from app.blueprints.factory.schema import VALID_FILE_TYPES

        assert "bootloader" in VALID_FILE_TYPES

    def test_contains_partition_table(self):
        """partition-table must be a valid file type."""
        from app.blueprints.factory.schema import VALID_FILE_TYPES

        assert "partition-table" in VALID_FILE_TYPES

    def test_only_two_valid_types(self):
        """Only bootloader and partition-table are valid."""
        from app.blueprints.factory.schema import VALID_FILE_TYPES

        assert len(VALID_FILE_TYPES) == 2


class TestFactoryFileMetaDataSchema:
    """Tests for the FactoryFileMetaDataSchema."""

    def test_serializes_all_required_fields(self):
        """Schema should serialize all required fields including version."""
        from datetime import UTC, datetime

        from app.blueprints.factory.schema import FactoryFileMetaDataSchema
        from app.models import FactoryFileMetaData

        meta = FactoryFileMetaData(
            device_type="esp32s3",
            file_type="bootloader",
            version="1.0.0",
            checksum="abc123",
            file_size=1024,
            upload_date=datetime(2025, 1, 1, tzinfo=UTC),
            flash_address=0x0,
        )

        schema = FactoryFileMetaDataSchema()
        result = schema.dump(meta)

        assert result["device_type"] == "esp32s3"
        assert result["file_type"] == "bootloader"
        assert result["version"] == "1.0.0"
        assert result["checksum"] == "abc123"
        assert result["file_size"] == 1024
        assert result["flash_address"] == 0x0
        assert "upload_date" in result

    def test_flash_address_serializes_as_integer(self):
        """Flash address should serialize as an integer, not hex string."""
        from datetime import UTC, datetime

        from app.blueprints.factory.schema import FactoryFileMetaDataSchema
        from app.models import FactoryFileMetaData

        meta = FactoryFileMetaData(
            device_type="esp32s3",
            file_type="partition-table",
            version="2.0.0",
            checksum="abc123",
            file_size=3072,
            upload_date=datetime(2025, 1, 1, tzinfo=UTC),
            flash_address=0x8000,
        )

        schema = FactoryFileMetaDataSchema()
        result = schema.dump(meta)

        assert result["flash_address"] == 0x8000
        assert isinstance(result["flash_address"], int)

    def test_download_url_serializes_when_present(self):
        """Download URL should serialize when provided."""
        from datetime import UTC, datetime

        from app.blueprints.factory.schema import FactoryFileMetaDataSchema
        from app.models import FactoryFileMetaData

        meta = FactoryFileMetaData(
            device_type="esp32s3",
            file_type="bootloader",
            version="1.0.0",
            checksum="abc123",
            file_size=1024,
            upload_date=datetime(2025, 1, 1, tzinfo=UTC),
            flash_address=0x0,
            download_url="http://example.com/factory/esp32s3/bootloader/1.0.0",
        )

        schema = FactoryFileMetaDataSchema()
        result = schema.dump(meta)

        assert (
            result["download_url"]
            == "http://example.com/factory/esp32s3/bootloader/1.0.0"
        )
