import os
import pytest

@pytest.mark.integration
def test_bucket_exists(s3):
    names = [b["Name"] for b in s3.list_buckets()["Buckets"]]
    assert os.environ["STORAGE_BUCKET"] in names

@pytest.mark.integration
def test_put_and_get_object(s3):
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
