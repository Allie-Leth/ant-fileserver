import os
import pytest
import boto3
from botocore.exceptions import ClientError
from app import create_app
from app.blueprints.firmware.service import FirmwareService


# ---------- S3 client ----------
@pytest.fixture(scope="session")
def s3():
    return boto3.client(
        "s3",
        endpoint_url=os.environ["STORAGE_ENDPOINT"],
        aws_access_key_id=os.environ["STORAGE_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["STORAGE_SECRET_ACCESS_KEY"],
        region_name=os.getenv("STORAGE_REGION", "us-east-1"),
    )


# ---------- Make sure bucket exists ----------
@pytest.fixture(scope="session", autouse=True)
def ensure_bucket(s3):
    bucket = os.environ["STORAGE_BUCKET"]
    try:
        s3.head_bucket(Bucket=bucket)
    except ClientError:
        # create once; OK if it already exists
        s3.create_bucket(Bucket=bucket)


# ---------- Live service ----------
@pytest.fixture(scope="session")
def live_service():
    return FirmwareService(
        endpoint_url=os.environ["STORAGE_ENDPOINT"],
        bucket=os.environ["STORAGE_BUCKET"],
        access_key_id=os.environ["STORAGE_ACCESS_KEY_ID"],
        secret_access_key=os.environ["STORAGE_SECRET_ACCESS_KEY"],
        region=os.getenv("STORAGE_REGION", "us-east-1"),
    )


# ---------- Live Flask app (for future API E2E tests) ----------
@pytest.fixture(scope="session")
def live_app():
    return create_app("production")


@pytest.fixture()
def client(live_app):
    with live_app.test_client() as c:
        yield c
