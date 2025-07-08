"""Integration smoke tests for S3 storage backend.

Verifies bucket existence and basic put/get operations using the live MinIO service.
"""

import os

import pytest


@pytest.mark.integration
def test_bucket_exists(s3):
    """Ensure the configured STORAGE_BUCKET is present in the S3 buckets list."""
    names = [b["Name"] for b in s3.list_buckets()["Buckets"]]
    assert os.environ["STORAGE_BUCKET"] in names


@pytest.mark.integration
def test_put_and_get_object(s3):
    """Put an object to S3 and verify it can be retrieved with the same contents."""
    s3.put_object(
        Bucket=os.environ["STORAGE_BUCKET"],
        Key="ci/hello.txt",
        Body=b"hello",
        ContentType="text/plain",
    )
    obj = s3.get_object(
        Bucket=os.environ["STORAGE_BUCKET"],
        Key="ci/hello.txt",
    )
    assert obj["Body"].read() == b"hello"
