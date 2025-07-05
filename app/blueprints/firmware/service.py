import json
import logging
import base64
import hashlib
import datetime
from typing import List, Optional

import boto3
import semver
from botocore.config import Config
from botocore.exceptions import ClientError

from app.errors import (
    DuplicateVersionError,
    ChecksumMismatchError,
    StorageError,
)

from app.models import FirmwareMetaData

logger = logging.getLogger(__name__)

# We're using boto against our local minio on the k3s stack,
# But Boto is designed for AWS so uses AWS-named credentials


class FirmwareService:
    """
    Talks to any S3-compatible store via boto3,
    using STORAGE_* credentials passed in at startup.
    """

    def __init__(
        self,
        endpoint_url: str,
        bucket: str,
        access_key_id: str,
        secret_access_key: str,
        region: str,
        prefix: str = "releases",
        config_overrides: Optional[Config] = None,
    ):
        # Allow overriding the botocore Config
        s3_config = config_overrides or Config(
            signature_version="s3v4",
            region_name=region,
        )

        # Instantiate S3
        self.s3 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            config=s3_config,
        )

        self.bucket = bucket
        self.prefix = prefix

    def list_firmware(self, project: str, device_type: str) -> List[FirmwareMetaData]:
        """
        List all firmware metadata objects for a given project and device type,
        sorted by semantic version.
        """
        key_prefix = f"{self.prefix}/{project}/{device_type}/"

        try:
            paginator = self.s3.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=self.bucket, Prefix=key_prefix)

        except ClientError as e:
            raise StorageError(
                f"Failed to list objects for {project}/{device_type}: {e}"
            )

        metas: List[FirmwareMetaData] = []
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
                    # Parse JSON → dataclass and store
                    meta_dict = json.loads(body)
                    metas.append(FirmwareMetaData.from_dict(meta_dict))

                except (ClientError, json.JSONDecodeError, KeyError) as e:
                    logger.warning(
                        "Skipping metadata at %r (project=%s, device_type=%s): %s",
                        key,
                        project,
                        device_type,
                        e,
                    )
                    continue

        metas.sort(key=lambda m: semver.VersionInfo.parse(m.version))
        return metas

    #  UPLOAD  (new)

    def upload_firmware(
        self,
        project: str,
        device_type: str,
        payload: dict,
    ) -> None:
        """
        Persist a new firmware binary + metadata.json.

        Expected JSON payload:
        {
            "version"      : "1.2.3",
            "firmware_b64" : "<base-64-encoded binary>",
            "checksum"     : "<hex sha256>",      # optional; auto-filled if absent
            "release_notes": "...",               # optional
            ... any extra firmware-meta fields ...
        }
        """
        # ── Validate ---------------------------------------------------- #
        try:
            version = payload["version"]
            semver.VersionInfo.parse(version)  # raises if bad
        except (KeyError, ValueError) as e:
            raise ValueError(f"Invalid or missing version: {e}")

        try:
            raw_bytes = base64.b64decode(payload["firmware_b64"])
        except (KeyError, ValueError) as e:
            raise ValueError(f"Invalid base64 firmware blob: {e}")

        supplied_checksum = payload.get("checksum")
        calc_checksum = hashlib.sha256(raw_bytes).hexdigest()
        if supplied_checksum and supplied_checksum != calc_checksum:
            raise ChecksumMismatchError(
                f"Expected {supplied_checksum}, got {calc_checksum}"
            )

        # ── Version already exists?  ----------------------------------- #
        if any(r.version == version for r in self.list_firmware(project, device_type)):
            raise DuplicateVersionError(version)

        # ── Upload binary ---------------------------------------------- #
        bin_key = f"{self.prefix}/{project}/{device_type}/{version}/firmware.bin"
        meta_key = f"{self.prefix}/{project}/{device_type}/{version}/metadata.json"

        # ── Assemble metadata ------------------------------------------ #
        meta: dict = {
            "project": project,
            "device_type": device_type,
            "version": version,
            "checksum": calc_checksum,
            "file_size": len(raw_bytes),
            "release_notes": payload.get("release_notes", ""),
            "release_date": payload.get(
                "release_date",
                datetime.datetime.utcnow()
                .replace(tzinfo=datetime.timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
            ),
            "channel": payload.get("channel", "stable"),
            "mandatory": bool(payload.get("mandatory", False)),
            "signature": payload.get("signature"),
            "min_bootloader": payload.get("min_bootloader"),
            "metadata_version": int(payload.get("metadata_version", 1)),
            "extra": payload.get("extra"),
        }

        try:
            self.s3.put_object(
                Bucket=self.bucket,
                Key=bin_key,
                Body=raw_bytes,
                ContentType="application/octet-stream",
            )

            self.s3.put_object(
                Bucket=self.bucket,
                Key=meta_key,
                Body=json.dumps(meta).encode("utf-8"),
                ContentType="application/json",
            )

            logger.info("Uploaded firmware %s for %s/%s", version, project, device_type)

        except ClientError as err:
            # Convert AWS-specific error → domain-level error
            raise StorageError(
                f"S3 write failed for {project}/{device_type} {version}: {err}"
            ) from err

    def get_latest(
        self,
        project: str,
        device_type: str,
        current_version: Optional[str] = None,
    ) -> FirmwareMetaData:
        """
        Return the next release after `current_version`,
        or the highest version if none specified or up-to-date.
        """
        releases = self.list_firmware(project, device_type)
        if not releases:
            raise ValueError(f"No firmware releases found for {project}/{device_type}")

        if current_version:
            for release in releases:
                if semver.compare(release.version, current_version) > 0:
                    return release

        # fallback: return the latest release
        return releases[-1]

    def generate_presigned_url(
        self,
        project: str,
        device_type: str,
        version: str,
        expires_in: int = 3600,  # Default 1 hour
    ) -> str:
        """
        Generate a presigned S3 URL for the firmware binary.
        """
        key = f"{self.prefix}/{project}/{device_type}/{version}/firmware.bin"

        try:
            return self.s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expires_in,
            )
        except ClientError as e:
            raise StorageError(f"Failed to generate presigned URL for {key}: {e}")
