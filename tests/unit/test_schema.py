import pytest
from marshmallow import ValidationError

from app.blueprints.firmware.schema import (
    validate_semver,
    LatestFirmwareQuerySchema,
)


def test_validate_semver_bad():
    with pytest.raises(ValidationError):
        validate_semver("not-a-version")


def test_latest_query_schema_bad_current():
    schema = LatestFirmwareQuerySchema()
    with pytest.raises(ValidationError):
        schema.load({"current": "bogus"})
