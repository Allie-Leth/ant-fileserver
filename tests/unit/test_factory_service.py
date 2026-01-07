# ruff: noqa: PLC0415,PLR2004   # imports inside tests, magic values in assertions
"""Unit tests for FactoryService.

Tests for:
- upload_file: upload a versioned factory file to S3
- get_file: retrieve a specific version of a factory file from S3
- get_metadata: retrieve metadata for a specific version
- get_latest: retrieve the latest version of a factory file
- list_files: list all factory files for a device type
"""

import base64
from datetime import datetime

import boto3
import pytest
from moto import mock_aws

from app.blueprints.factory.schema import FLASH_ADDRESSES
from app.errors import ChecksumMismatchError, DuplicateVersionError

_BUCKET = "firmware"


def _b64(data: bytes) -> str:
    """Helper to base64 encode bytes."""
    return base64.b64encode(data).decode()


@pytest.fixture(scope="function")
def factory_svc():
    """Provide a FactoryService connected to moto's in-memory S3."""
    from app.blueprints.factory.service import FactoryService

    with mock_aws():
        s3_client = boto3.client("s3", region_name="us-east-1")
        s3_client.create_bucket(Bucket=_BUCKET)

        yield FactoryService(
            endpoint_url=None,
            bucket=_BUCKET,
            access_key_id="x",
            secret_access_key="y",
            region="us-east-1",
        )


class TestUploadFile:
    """Tests for FactoryService.upload_file()."""

    def test_upload_stores_versioned_file_in_s3(self, factory_svc):
        """Upload should store the file in S3 with version in path."""
        factory_svc.upload_file(
            "esp32s3",
            "bootloader",
            {"version": "1.0.0", "file_b64": _b64(b"bootloader content")},
        )

        # Verify we can retrieve it with version
        data = factory_svc.get_file("esp32s3", "bootloader", "1.0.0")
        assert data == b"bootloader content"

    def test_upload_multiple_versions(self, factory_svc):
        """Multiple versions of same file type can coexist."""
        factory_svc.upload_file(
            "esp32s3",
            "bootloader",
            {"version": "1.0.0", "file_b64": _b64(b"version 1")},
        )
        factory_svc.upload_file(
            "esp32s3",
            "bootloader",
            {"version": "2.0.0", "file_b64": _b64(b"version 2")},
        )

        # Both versions should be retrievable
        assert factory_svc.get_file("esp32s3", "bootloader", "1.0.0") == b"version 1"
        assert factory_svc.get_file("esp32s3", "bootloader", "2.0.0") == b"version 2"

    def test_upload_rejects_duplicate_version(self, factory_svc):
        """Upload should reject duplicate version."""
        factory_svc.upload_file(
            "esp32s3",
            "bootloader",
            {"version": "1.0.0", "file_b64": _b64(b"first")},
        )

        with pytest.raises(DuplicateVersionError):
            factory_svc.upload_file(
                "esp32s3",
                "bootloader",
                {"version": "1.0.0", "file_b64": _b64(b"duplicate")},
            )

    def test_upload_requires_version(self, factory_svc):
        """Upload should fail if version is missing."""
        with pytest.raises(ValueError, match="[Vv]ersion"):
            factory_svc.upload_file(
                "esp32s3",
                "bootloader",
                {"file_b64": _b64(b"content")},
            )

    def test_upload_auto_calculates_checksum(self, factory_svc):
        """Checksum should be auto-calculated if not provided."""
        content = b"test content"
        factory_svc.upload_file(
            "esp32s3",
            "bootloader",
            {"version": "1.0.0", "file_b64": _b64(content)},
        )

        meta = factory_svc.get_metadata("esp32s3", "bootloader", "1.0.0")
        import hashlib

        expected_checksum = hashlib.sha256(content).hexdigest()
        assert meta.checksum == expected_checksum

    def test_upload_verifies_provided_checksum(self, factory_svc):
        """If checksum is provided, it should be verified."""
        content = b"test content"
        import hashlib

        correct_checksum = hashlib.sha256(content).hexdigest()

        # Should succeed with correct checksum
        factory_svc.upload_file(
            "esp32s3",
            "bootloader",
            {
                "version": "1.0.0",
                "file_b64": _b64(content),
                "checksum": correct_checksum,
            },
        )

    def test_upload_rejects_incorrect_checksum(self, factory_svc):
        """Upload should fail if provided checksum doesn't match."""
        with pytest.raises(ChecksumMismatchError):
            factory_svc.upload_file(
                "esp32s3",
                "bootloader",
                {"version": "1.0.0", "file_b64": _b64(b"content"), "checksum": "wrong"},
            )

    def test_upload_rejects_invalid_base64(self, factory_svc):
        """Upload should fail for invalid base64."""
        with pytest.raises(ValueError, match="Invalid base64"):
            factory_svc.upload_file(
                "esp32s3",
                "bootloader",
                {"version": "1.0.0", "file_b64": "not-valid-base64!!!"},
            )

    def test_upload_stores_version_in_metadata(self, factory_svc):
        """Upload should store version in metadata."""
        factory_svc.upload_file(
            "esp32s3",
            "bootloader",
            {"version": "1.2.3", "file_b64": _b64(b"content")},
        )

        meta = factory_svc.get_metadata("esp32s3", "bootloader", "1.2.3")
        assert meta.version == "1.2.3"


class TestGetFile:
    """Tests for FactoryService.get_file()."""

    def test_get_file_returns_binary_content(self, factory_svc):
        """get_file should return the raw binary content."""
        factory_svc.upload_file(
            "esp32s3",
            "partition-table",
            {"version": "1.0.0", "file_b64": _b64(b"\x00\x01\x02\x03")},
        )

        data = factory_svc.get_file("esp32s3", "partition-table", "1.0.0")
        assert data == b"\x00\x01\x02\x03"

    def test_get_file_not_found_raises_error(self, factory_svc):
        """get_file should raise FileNotFoundError if file doesn't exist."""
        from app.errors import FileNotFoundError

        with pytest.raises(FileNotFoundError):
            factory_svc.get_file("nonexistent", "bootloader", "1.0.0")

    def test_get_file_version_not_found(self, factory_svc):
        """get_file should raise error if specific version doesn't exist."""
        from app.errors import FileNotFoundError

        factory_svc.upload_file(
            "esp32s3",
            "bootloader",
            {"version": "1.0.0", "file_b64": _b64(b"v1")},
        )

        with pytest.raises(FileNotFoundError):
            factory_svc.get_file("esp32s3", "bootloader", "2.0.0")


class TestGetMetadata:
    """Tests for FactoryService.get_metadata()."""

    def test_metadata_includes_flash_address(self, factory_svc):
        """Metadata should include the correct flash address for file type."""
        factory_svc.upload_file(
            "esp32s3",
            "bootloader",
            {"version": "1.0.0", "file_b64": _b64(b"x")},
        )

        meta = factory_svc.get_metadata("esp32s3", "bootloader", "1.0.0")
        assert meta.flash_address == FLASH_ADDRESSES["bootloader"]
        assert meta.flash_address == 0x0

    def test_metadata_includes_partition_table_address(self, factory_svc):
        """Partition table should have address 0x8000."""
        factory_svc.upload_file(
            "esp32s3",
            "partition-table",
            {"version": "1.0.0", "file_b64": _b64(b"y")},
        )

        meta = factory_svc.get_metadata("esp32s3", "partition-table", "1.0.0")
        assert meta.flash_address == 0x8000

    def test_metadata_includes_file_size(self, factory_svc):
        """Metadata should include correct file size."""
        content = b"0123456789"
        factory_svc.upload_file(
            "esp32s3",
            "bootloader",
            {"version": "1.0.0", "file_b64": _b64(content)},
        )

        meta = factory_svc.get_metadata("esp32s3", "bootloader", "1.0.0")
        assert meta.file_size == len(content)

    def test_metadata_includes_upload_date(self, factory_svc):
        """Metadata should include upload date."""
        factory_svc.upload_file(
            "esp32s3",
            "bootloader",
            {"version": "1.0.0", "file_b64": _b64(b"x")},
        )

        meta = factory_svc.get_metadata("esp32s3", "bootloader", "1.0.0")
        assert isinstance(meta.upload_date, datetime)
        assert meta.upload_date.tzinfo is not None  # Should be timezone-aware

    def test_metadata_includes_version(self, factory_svc):
        """Metadata should include version."""
        factory_svc.upload_file(
            "esp32s3",
            "bootloader",
            {"version": "2.1.0", "file_b64": _b64(b"x")},
        )

        meta = factory_svc.get_metadata("esp32s3", "bootloader", "2.1.0")
        assert meta.version == "2.1.0"

    def test_metadata_not_found_raises_error(self, factory_svc):
        """get_metadata should raise error if file doesn't exist."""
        from app.errors import FileNotFoundError

        with pytest.raises(FileNotFoundError):
            factory_svc.get_metadata("nonexistent", "bootloader", "1.0.0")


class TestGetLatest:
    """Tests for FactoryService.get_latest()."""

    def test_get_latest_returns_highest_version(self, factory_svc):
        """get_latest should return the highest semver version."""
        factory_svc.upload_file(
            "esp32s3",
            "bootloader",
            {"version": "1.0.0", "file_b64": _b64(b"v1")},
        )
        factory_svc.upload_file(
            "esp32s3",
            "bootloader",
            {"version": "2.0.0", "file_b64": _b64(b"v2")},
        )
        factory_svc.upload_file(
            "esp32s3",
            "bootloader",
            {"version": "1.5.0", "file_b64": _b64(b"v1.5")},
        )

        meta = factory_svc.get_latest("esp32s3", "bootloader")
        assert meta.version == "2.0.0"

    def test_get_latest_with_single_version(self, factory_svc):
        """get_latest should work with single version."""
        factory_svc.upload_file(
            "esp32s3",
            "bootloader",
            {"version": "1.0.0", "file_b64": _b64(b"only")},
        )

        meta = factory_svc.get_latest("esp32s3", "bootloader")
        assert meta.version == "1.0.0"

    def test_get_latest_not_found(self, factory_svc):
        """get_latest should raise error if no versions exist."""
        from app.errors import FileNotFoundError

        with pytest.raises(FileNotFoundError):
            factory_svc.get_latest("nonexistent", "bootloader")


class TestListFiles:
    """Tests for FactoryService.list_files()."""

    def test_list_returns_all_files_for_device(self, factory_svc):
        """list_files should return all files for the device type."""
        factory_svc.upload_file(
            "esp32s3",
            "bootloader",
            {"version": "1.0.0", "file_b64": _b64(b"boot")},
        )
        factory_svc.upload_file(
            "esp32s3",
            "partition-table",
            {"version": "1.0.0", "file_b64": _b64(b"part")},
        )

        files = factory_svc.list_files("esp32s3")
        assert len(files) == 2
        file_types = {f.file_type for f in files}
        assert file_types == {"bootloader", "partition-table"}

    def test_list_returns_all_versions(self, factory_svc):
        """list_files should return all versions of each file type."""
        factory_svc.upload_file(
            "esp32s3",
            "bootloader",
            {"version": "1.0.0", "file_b64": _b64(b"v1")},
        )
        factory_svc.upload_file(
            "esp32s3",
            "bootloader",
            {"version": "2.0.0", "file_b64": _b64(b"v2")},
        )

        files = factory_svc.list_files("esp32s3")
        assert len(files) == 2
        versions = {f.version for f in files}
        assert versions == {"1.0.0", "2.0.0"}

    def test_list_returns_empty_for_new_device(self, factory_svc):
        """list_files should return empty list for device with no files."""
        files = factory_svc.list_files("nonexistent")
        assert files == []

    def test_list_only_returns_files_for_specified_device(self, factory_svc):
        """list_files should not include files from other devices."""
        factory_svc.upload_file(
            "esp32s3",
            "bootloader",
            {"version": "1.0.0", "file_b64": _b64(b"s3")},
        )
        factory_svc.upload_file(
            "esp32c3",
            "bootloader",
            {"version": "1.0.0", "file_b64": _b64(b"c3")},
        )

        files = factory_svc.list_files("esp32s3")
        assert len(files) == 1
        assert files[0].device_type == "esp32s3"


class TestListVersions:
    """Tests for FactoryService.list_versions()."""

    def test_list_versions_returns_all_versions_for_file_type(self, factory_svc):
        """list_versions should return all versions of a specific file type."""
        factory_svc.upload_file(
            "esp32s3",
            "bootloader",
            {"version": "1.0.0", "file_b64": _b64(b"v1")},
        )
        factory_svc.upload_file(
            "esp32s3",
            "bootloader",
            {"version": "2.0.0", "file_b64": _b64(b"v2")},
        )
        factory_svc.upload_file(
            "esp32s3",
            "partition-table",
            {"version": "1.0.0", "file_b64": _b64(b"pt")},
        )

        versions = factory_svc.list_versions("esp32s3", "bootloader")
        assert len(versions) == 2
        version_strs = {v.version for v in versions}
        assert version_strs == {"1.0.0", "2.0.0"}

    def test_list_versions_empty_for_nonexistent(self, factory_svc):
        """list_versions should return empty for nonexistent file type."""
        versions = factory_svc.list_versions("esp32s3", "bootloader")
        assert versions == []
