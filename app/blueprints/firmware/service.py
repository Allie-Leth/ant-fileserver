import json
import logging
from typing import List, Optional

import boto3
import semver
from botocore.config import Config
from botocore.exceptions import ClientError

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
            raise RuntimeError(f"Failed to list objects for {project}/{device_type}: {e}")
            
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
                except (ClientError, json.JSONDecodeError) as e:
                    logger.warning(
                        "Skipping metadata at %r (project=%s, device_type=%s): %s",
                        key, project, device_type, e
                    )
                    continue
                    
        metas.sort(key=lambda m: semver.VersionInfo.parse(m.version))
        return metas
                
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
            raise RuntimeError(f"Failed to generate presigned URL for {key}: {e}")