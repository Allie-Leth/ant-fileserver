import os
import pytest
import boto3
from app import create_app
from app.blueprints.firmware.service import FirmwareService

@pytest.fixture(scope="session")
def minio_env():
    # Values come from CI job; we just assert they're present
    required = ["STORAGE_ENDPOINT", "STORAGE_BUCKET",
                "STORAGE_ACCESS_KEY_ID", "STORAGE_SECRET_ACCESS_KEY"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise RuntimeError(f"CI didn’t set: {', '.join(missing)}")

@pytest.fixture(scope="session")
def s3(minio_env):
    return boto3.client(
        "s3",
        endpoint_url=os.environ["STORAGE_ENDPOINT"],
        aws_access_key_id=os.environ["STORAGE_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["STORAGE_SECRET_ACCESS_KEY"],
        region_name=os.getenv("STORAGE_REGION", "us-east-1"),
    )

@pytest.fixture(scope="session")
def live_service():
    return FirmwareService(
        endpoint_url=os.environ["STORAGE_ENDPOINT"],
        bucket=os.environ["STORAGE_BUCKET"],
        access_key_id=os.environ["STORAGE_ACCESS_KEY_ID"],
        secret_access_key=os.environ["STORAGE_SECRET_ACCESS_KEY"],
        region=os.getenv("STORAGE_REGION", "us-east-1"),
    )

@pytest.fixture(scope="session")
def live_app():
    # Use the actual env-vars (no moto)
    return create_app("production")   # config object doesn’t matter; env wins

@pytest.fixture()
def client(live_app):
    with live_app.test_client() as c:
        yield c
