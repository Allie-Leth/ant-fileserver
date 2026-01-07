"""FactoryService module.

Provides `FactoryService`, an S3-backed service for storing and retrieving
versioned factory files (bootloader, partition-table).
"""

import base64
import datetime
import hashlib
import json
import logging

import boto3
import semver
from botocore.config import Config
from botocore.exceptions import ClientError

from app.blueprints.factory.schema import FLASH_ADDRESSES
from app.errors import (
    ChecksumMismatchError,
    DuplicateVersionError,
    FileNotFoundError,
    StorageError,
)
from app.models import FactoryFileMetaData

logger = logging.getLogger(__name__)


class FactoryService:
    """S3-backed service for versioned factory files (bootloader, partition-table).

    Factory files are versioned - multiple versions can coexist for each
    device_type/file_type combination.
    """

    def __init__(  # noqa: PLR0913
        self,
        endpoint_url: str | None,
        bucket: str,
        access_key_id: str,
        secret_access_key: str,
        region: str,
        prefix: str = "factory",
        config_overrides: Config | None = None,
    ):
        """Initialize the FactoryService with its S3 client and settings."""
        s3_config = config_overrides or Config(
            signature_version="s3v4",
            region_name=region,
        )

        self.s3 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            config=s3_config,
        )

        self.bucket = bucket
        self.prefix = prefix

    def _file_key(self, device_type: str, file_type: str, version: str) -> str:
        """Generate S3 key for the binary file."""
        return f"{self.prefix}/{device_type}/{file_type}/{version}/file.bin"

    def _meta_key(self, device_type: str, file_type: str, version: str) -> str:
        """Generate S3 key for the metadata file."""
        return f"{self.prefix}/{device_type}/{file_type}/{version}/metadata.json"

    def _version_exists(self, device_type: str, file_type: str, version: str) -> bool:
        """Check if a specific version already exists."""
        key = self._meta_key(device_type, file_type, version)
        try:
            self.s3.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "404":
                return False
            raise StorageError(f"Failed to check version existence: {e}") from e

    def upload_file(
        self,
        device_type: str,
        file_type: str,
        payload: dict,
    ) -> None:
        """Upload a versioned factory file.

        Expected payload:
        {
            "version": "<semver>",  # required
            "file_b64": "<base64-encoded binary>",
            "checksum": "<hex sha256>",  # optional; auto-calculated if absent
        }

        Args:
            device_type: Hardware type identifier (e.g., "esp32s3")
            file_type: Factory file type ("bootloader" or "partition-table")
            payload: Dict containing version, file_b64 and optional checksum

        Raises:
            ValueError: If version is missing or base64 is invalid
            DuplicateVersionError: If version already exists
            ChecksumMismatchError: If provided checksum doesn't match
            StorageError: If S3 write fails
        """
        # Extract and validate version
        version = payload.get("version")
        if not version:
            raise ValueError("Version is required for factory file upload")

        # Check for duplicate version
        if self._version_exists(device_type, file_type, version):
            raise DuplicateVersionError(
                f"Factory file {device_type}/{file_type} version {version} already exists"
            )

        # Decode base64
        try:
            raw_bytes = base64.b64decode(payload["file_b64"])
        except (KeyError, ValueError) as e:
            raise ValueError(f"Invalid base64 factory file blob: {e}") from e

        # Calculate checksum
        calc_checksum = hashlib.sha256(raw_bytes).hexdigest()
        supplied_checksum = payload.get("checksum")
        if supplied_checksum and supplied_checksum != calc_checksum:
            raise ChecksumMismatchError(
                f"Expected {supplied_checksum}, got {calc_checksum}"
            )

        # Get flash address for this file type
        flash_address = FLASH_ADDRESSES[file_type]

        # Build S3 keys
        bin_key = self._file_key(device_type, file_type, version)
        meta_key = self._meta_key(device_type, file_type, version)

        # Build metadata
        meta = {
            "device_type": device_type,
            "file_type": file_type,
            "version": version,
            "checksum": calc_checksum,
            "checksum_algo": "sha256",
            "file_size": len(raw_bytes),
            "upload_date": (
                datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
            ),
            "flash_address": flash_address,
        }

        try:
            # Upload binary
            self.s3.put_object(
                Bucket=self.bucket,
                Key=bin_key,
                Body=raw_bytes,
                ContentType="application/octet-stream",
            )

            # Upload metadata
            self.s3.put_object(
                Bucket=self.bucket,
                Key=meta_key,
                Body=json.dumps(meta).encode("utf-8"),
                ContentType="application/json",
            )

            logger.info(
                "Uploaded factory file %s/%s v%s (%d bytes)",
                device_type,
                file_type,
                version,
                len(raw_bytes),
            )

        except ClientError as err:
            raise StorageError(
                f"S3 write failed for factory file {device_type}/{file_type}/{version}: {err}"
            ) from err

    def get_file(self, device_type: str, file_type: str, version: str) -> bytes:
        """Retrieve a specific version of a factory file binary from S3.

        Args:
            device_type: Hardware type identifier
            file_type: Factory file type
            version: Semantic version string

        Returns:
            Raw binary bytes

        Raises:
            FileNotFoundError: If the file/version doesn't exist
            StorageError: If there's an S3 error
        """
        key = self._file_key(device_type, file_type, version)

        try:
            response = self.s3.get_object(Bucket=self.bucket, Key=key)
            return response["Body"].read()
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code in ("NoSuchKey", "404"):
                raise FileNotFoundError(
                    f"Factory file {device_type}/{file_type} v{version} not found"
                ) from e
            raise StorageError(f"Failed to retrieve factory file {key}: {e}") from e

    def get_metadata(
        self, device_type: str, file_type: str, version: str
    ) -> FactoryFileMetaData:
        """Retrieve metadata for a specific version of a factory file.

        Args:
            device_type: Hardware type identifier
            file_type: Factory file type
            version: Semantic version string

        Returns:
            FactoryFileMetaData object

        Raises:
            FileNotFoundError: If the file/version doesn't exist
            StorageError: If there's an S3 error
        """
        key = self._meta_key(device_type, file_type, version)

        try:
            response = self.s3.get_object(Bucket=self.bucket, Key=key)
            body = response["Body"].read().decode("utf-8")
            meta_dict = json.loads(body)
            return FactoryFileMetaData.from_dict(meta_dict)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code in ("NoSuchKey", "404"):
                raise FileNotFoundError(
                    f"Factory file {device_type}/{file_type} v{version} not found"
                ) from e
            raise StorageError(f"Failed to retrieve factory metadata {key}: {e}") from e

    def get_latest(self, device_type: str, file_type: str) -> FactoryFileMetaData:
        """Get the latest (highest semver) version of a factory file.

        Args:
            device_type: Hardware type identifier
            file_type: Factory file type

        Returns:
            FactoryFileMetaData for the latest version

        Raises:
            FileNotFoundError: If no versions exist
        """
        versions = self.list_versions(device_type, file_type)
        if not versions:
            raise FileNotFoundError(
                f"No versions found for factory file {device_type}/{file_type}"
            )

        # Sort by semver and return highest
        versions.sort(key=lambda m: semver.VersionInfo.parse(m.version))
        return versions[-1]

    def list_versions(
        self, device_type: str, file_type: str
    ) -> list[FactoryFileMetaData]:
        """List all versions of a specific factory file type.

        Args:
            device_type: Hardware type identifier
            file_type: Factory file type

        Returns:
            List of FactoryFileMetaData objects for all versions
        """
        key_prefix = f"{self.prefix}/{device_type}/{file_type}/"

        try:
            paginator = self.s3.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=self.bucket, Prefix=key_prefix)
        except ClientError as e:
            raise StorageError(
                f"Failed to list versions for {device_type}/{file_type}: {e}"
            ) from e

        metas: list[FactoryFileMetaData] = []
        for page in pages:
            for obj in page.get("Contents", []):
                key = obj.get("Key", "")
                if not key.endswith("metadata.json"):
                    continue
                try:
                    body = (
                        self.s3.get_object(Bucket=self.bucket, Key=key)["Body"]
                        .read()
                        .decode("utf-8")
                    )
                    meta_dict = json.loads(body)
                    metas.append(FactoryFileMetaData.from_dict(meta_dict))
                except (ClientError, json.JSONDecodeError, KeyError) as e:
                    logger.warning(
                        "Skipping metadata at %r: %s",
                        key,
                        e,
                    )
                    continue

        return metas

    def list_files(self, device_type: str) -> list[FactoryFileMetaData]:
        """List all factory files (all types, all versions) for a device type.

        Args:
            device_type: Hardware type identifier

        Returns:
            List of FactoryFileMetaData objects
        """
        key_prefix = f"{self.prefix}/{device_type}/"

        try:
            paginator = self.s3.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=self.bucket, Prefix=key_prefix)
        except ClientError as e:
            raise StorageError(
                f"Failed to list factory files for {device_type}: {e}"
            ) from e

        metas: list[FactoryFileMetaData] = []
        for page in pages:
            for obj in page.get("Contents", []):
                key = obj.get("Key", "")
                if not key.endswith("metadata.json"):
                    continue
                try:
                    body = (
                        self.s3.get_object(Bucket=self.bucket, Key=key)["Body"]
                        .read()
                        .decode("utf-8")
                    )
                    meta_dict = json.loads(body)
                    metas.append(FactoryFileMetaData.from_dict(meta_dict))
                except (ClientError, json.JSONDecodeError, KeyError) as e:
                    logger.warning(
                        "Skipping metadata at %r (device_type=%s): %s",
                        key,
                        device_type,
                        e,
                    )
                    continue

        return metas
