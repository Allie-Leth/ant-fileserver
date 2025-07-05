from __future__ import annotations
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Optional, Dict, Any


@dataclass(frozen=True)
class FirmwareMetaData:
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
    download_url: Optional[str] = None
    channel: str = "stable"
    mandatory: bool = False
    signature: Optional[str] = None
    min_bootloader: Optional[str] = None
    metadata_version: int = field(default=1)

    # run-time validation hook
    def __post_init__(self):
        allowed = {1}
        if self.metadata_version not in allowed:
            raise ValueError(
                f"metadata_version {self.metadata_version!r} not supported; "
                f"allowed: {sorted(allowed)}"
            )

    extra: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> FirmwareMetaData:
        """
        Build a FirmwareMetadata from a dict (e.g. loaded from metadata.json).
        Expects 'release_date' in ISO 8601, with optional trailing 'Z'.
        """
        dt_str = data["release_date"]
        if dt_str.endswith("Z"):
            # Strip the 'Z', parse, then attach UTC tzinfo
            dt = datetime.fromisoformat(dt_str[:-1]).replace(tzinfo=timezone.utc)
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
            metadata_version=int(data.get("metadata_version", 1)),
            extra=data.get("extra"),
        )

    def to_dict(self, include_url: bool = True) -> Dict[str, Any]:
        """
        Convert back to a JSON-serializable dict.
        If include_url is False, omits the download_url field.
        """
        result = asdict(self)
        # Convert datetime to ISO 8601 Z
        result["release_date"] = (
            self.release_date.astimezone(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )
        if not include_url:
            result.pop("download_url", None)
        return result
