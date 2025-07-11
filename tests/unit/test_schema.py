"""Unit tests for firmware schema validation.

Covers:
- `validate_semver` raising ValidationError on invalid versions.
- `LatestFirmwareQuerySchema` enforcing semver format for the `current` field.
"""

import pytest
from marshmallow import ValidationError

from app.blueprints.firmware.schema import LatestFirmwareQuerySchema, validate_semver


def test_validate_semver_bad():
    """validate_semver should raise ValidationError for non-semver strings."""
    with pytest.raises(ValidationError):
        validate_semver("not-a-version")


def test_latest_query_schema_bad_current():
    """LatestFirmwareQuerySchema.load should raise ValidationError for invalid `current`."""
    schema = LatestFirmwareQuerySchema()
    with pytest.raises(ValidationError):
        schema.load({"current": "bogus"})
