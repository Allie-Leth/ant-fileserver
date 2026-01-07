"""Metadata models for firmware and factory files.

Defines:
- `FirmwareMetaData`: immutable dataclass for versioned firmware releases
- `FactoryFileMetaData`: immutable dataclass for static factory files (bootloader, partition-table)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class FirmwareMetaData:
    """Immutable representation of firmware metadata.

    Fields:
      - project: firmware project name
      - device_type: hardware type identifier
      - version: semantic version string
      - checksum: hex SHA-256 of binary
      - file_size: size in bytes
      - release_date: UTC datetime of release
      - release_notes: optional human-readable notes
      - checksum_algo: algorithm name (default "sha256")
      - download_url: optional URL for download
      - channel: release channel (e.g. "stable")
      - mandatory: whether update is mandatory
      - signature: optional signature blob
      - min_bootloader: optional minimum bootloader version
      - bootloader_version: optional exact bootloader version for this firmware
      - partition_table_version: optional exact partition table version for this firmware
      - metadata_version: schema version (default 1)
      - extra: optional dict for additional fields
    """

    # Core Identity
    project: str
    device_type: str
    version: str
    # Integrity & Delivery
    checksum: str
    file_size: int

    # Release Info
    release_date: datetime
    release_notes: str = ""

    # Defaults

    checksum_algo: str = "sha256"
    download_url: str | None = None
    channel: str = "stable"
    mandatory: bool = False
    signature: str | None = None
    min_bootloader: str | None = None
    bootloader_version: str | None = None
    partition_table_version: str | None = None
    metadata_version: int = field(default=1)

    # run-time validation hook
    def __post_init__(self):
        """Validate that `metadata_version` is supported (only version 1)."""
        allowed = {1}
        if self.metadata_version not in allowed:
            raise ValueError(
                f"metadata_version {self.metadata_version!r} not supported; "
                f"allowed: {sorted(allowed)}"
            )

    extra: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FirmwareMetaData:
        """Build a FirmwareMetadata from a dict (e.g. loaded from metadata.json).

        Expects 'release_date' in ISO 8601, with optional trailing 'Z'.
        """
        dt_str = data["release_date"]
        if dt_str.endswith("Z"):
            # Strip the 'Z', parse, then attach UTC tzinfo
            dt = datetime.fromisoformat(dt_str[:-1]).replace(tzinfo=UTC)
        else:
            dt = datetime.fromisoformat(dt_str)

        return cls(
            project=data["project"],
            device_type=data["device_type"],
            version=data["version"],
            checksum=data["checksum"],
            file_size=data["file_size"],
            release_date=dt,
            download_url=None,
            release_notes=data.get("release_notes", ""),
            checksum_algo=data.get("checksum_algo", "sha256"),
            channel=data.get("channel", "stable"),
            mandatory=data.get("mandatory", False),
            signature=data.get("signature"),
            min_bootloader=data.get("min_bootloader"),
            bootloader_version=data.get("bootloader_version"),
            partition_table_version=data.get("partition_table_version"),
            metadata_version=int(data.get("metadata_version", 1)),
            extra=data.get("extra"),
        )

    def to_dict(self, include_url: bool = True) -> dict[str, Any]:
        """Convert back to a JSON-serializable dict.

        If include_url is False, omits the download_url field.
        """
        result = asdict(self)
        # Convert datetime to ISO 8601 Z
        result["release_date"] = (
            self.release_date.astimezone(UTC).isoformat().replace("+00:00", "Z")
        )
        if not include_url:
            result.pop("download_url", None)
        return result


@dataclass(frozen=True)
class FactoryFileMetaData:
    """Immutable representation of factory file metadata.

    Factory files are versioned - multiple versions can coexist.

    Fields:
      - device_type: hardware type identifier (e.g., "esp32s3")
      - file_type: factory file type ("bootloader" or "partition-table")
      - version: semantic version string (e.g., "1.0.0")
      - checksum: hex SHA-256 of binary
      - file_size: size in bytes
      - upload_date: UTC datetime of upload
      - flash_address: address to flash file at (e.g., 0x0, 0x8000)
      - checksum_algo: algorithm name (default "sha256")
      - download_url: optional URL for download (set by API layer)
    """

    device_type: str
    file_type: str
    version: str
    checksum: str
    file_size: int
    upload_date: datetime
    flash_address: int
    checksum_algo: str = "sha256"
    download_url: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FactoryFileMetaData:
        """Build a FactoryFileMetaData from a dict (e.g. loaded from metadata.json).

        Expects 'upload_date' in ISO 8601, with optional trailing 'Z'.
        """
        dt_str = data["upload_date"]
        if dt_str.endswith("Z"):
            dt = datetime.fromisoformat(dt_str[:-1]).replace(tzinfo=UTC)
        else:
            dt = datetime.fromisoformat(dt_str)

        return cls(
            device_type=data["device_type"],
            file_type=data["file_type"],
            version=data["version"],
            checksum=data["checksum"],
            file_size=data["file_size"],
            upload_date=dt,
            flash_address=data["flash_address"],
            checksum_algo=data.get("checksum_algo", "sha256"),
            download_url=data.get("download_url"),
        )

    def to_dict(self, include_url: bool = True) -> dict[str, Any]:
        """Convert back to a JSON-serializable dict.

        If include_url is False, omits the download_url field.
        """
        result = asdict(self)
        result["upload_date"] = (
            self.upload_date.astimezone(UTC).isoformat().replace("+00:00", "Z")
        )
        if not include_url:
            result.pop("download_url", None)
        return result
