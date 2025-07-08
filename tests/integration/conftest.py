# pylint: disable=redefined-outer-name
"""
Pytest fixtures for integration tests.

Includes fixtures for in-memory S3 backend setup and a production Flask app.
"""

import os

import boto3
from botocore.exceptions import ClientError
import pytest

from app import create_app
from app.blueprints.firmware.service import FirmwareService


# ---------- S3 client ----------
@pytest.fixture(scope="session")
def s3_client():
    """Return a boto3 S3 client wired to the endpoint in environment vars."""
    return boto3.client(
        "s3",
        endpoint_url=os.environ["STORAGE_ENDPOINT"],
        aws_access_key_id=os.environ["STORAGE_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["STORAGE_SECRET_ACCESS_KEY"],
        region_name=os.getenv("STORAGE_REGION", "us-east-1"),
    )


# ---------- Make sure bucket exists ----------
@pytest.fixture(scope="session", autouse=True)
def ensure_bucket(s3_client):
    """Create the test bucket once per session if it doesn’t already exist."""
    bucket = os.environ["STORAGE_BUCKET"]
    try:
        s3_client.head_bucket(Bucket=bucket)
    except ClientError:
        s3_client.create_bucket(Bucket=bucket)


# ---------- Live service ----------
@pytest.fixture(scope="session")
def prod_app():
    """FirmwareService instance that talks to the live S3 backend."""
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
    """Flask application configured for production settings."""
    return create_app("production")


@pytest.fixture()
def client(live_app):
    """Yield a Flask test-client backed by the production app."""
    with live_app.test_client() as c:
        yield c
