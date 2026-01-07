"""Tests for path segment validation to prevent path traversal attacks."""

from http import HTTPStatus

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from marshmallow import ValidationError

from app.blueprints.firmware.schema import PATH_SEGMENT_PATTERN, validate_path_segment


class TestValidatePathSegment:
    """Test cases for validate_path_segment function."""

    # Valid path segments - should pass
    @pytest.mark.parametrize(
        "value",
        [
            "test",
            "myproject",
            "device1",
            "nrf52840",
            "esp32-s3",
            "my_device",
            "Project123",
            "a",  # single char
            "a" * 64,  # max length
            "ESP32",
            "nRF52",
            "my-project-name",
            "my_project_name",
            "device-type-v2",
            "0device",  # starts with number - valid
            "123",  # all numbers - valid
        ],
    )
    def test_valid_path_segments(self, value):
        """Valid path segments should not raise."""
        # Should not raise
        validate_path_segment(value)

    # Invalid path segments - should fail
    @pytest.mark.parametrize(
        "value",
        [
            "../etc",  # path traversal
            "..%2F",  # encoded path traversal
            "foo/../bar",  # path traversal in middle
            ".hidden",  # starts with dot
            ".",  # single dot
            "..",  # double dot
            "foo/bar",  # contains slash
            "foo\\bar",  # contains backslash
            "",  # empty string
            "a" * 65,  # exceeds max length
            "hello world",  # contains space
            "test@project",  # contains @
            "test.device",  # contains dot
            "-invalid",  # starts with hyphen
            "_invalid",  # starts with underscore
        ],
    )
    def test_invalid_path_segments(self, value):
        """Invalid path segments should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_path_segment(value)
        assert "Invalid path segment" in str(exc_info.value)


class TestPathValidationInRoutes:
    """Test path validation is applied in API routes."""

    def test_list_rejects_path_traversal(self, client):
        """GET /firmware with path traversal should return 400."""
        # Note: Flask may normalize some paths before they reach the route
        # These tests verify our validation layer works for values that get through
        res = client.get("/api/v1/firmware/test/..%2Fetc")
        # Flask may return 404 for normalized paths, or 400 if our validation catches it
        assert res.status_code in (HTTPStatus.BAD_REQUEST, HTTPStatus.NOT_FOUND)

    def test_list_rejects_dots(self, client):
        """GET /firmware with dot in name should return 400."""
        res = client.get("/api/v1/firmware/test.project/device")
        assert res.status_code == HTTPStatus.BAD_REQUEST
        assert res.get_json()["error"] == "validation_error"

    def test_list_rejects_slashes(self, client):
        """GET /firmware with embedded slash should return 400 or 404."""
        res = client.get("/api/v1/firmware/test%2Fproject/device")
        assert res.status_code in (HTTPStatus.BAD_REQUEST, HTTPStatus.NOT_FOUND)

    def test_list_accepts_valid_names(self, client):
        """GET /firmware with valid names should work."""
        res = client.get("/api/v1/firmware/my-project/esp32-device")
        assert res.status_code == HTTPStatus.OK

    def test_list_accepts_underscores(self, client):
        """GET /firmware with underscores should work."""
        res = client.get("/api/v1/firmware/my_project/my_device")
        assert res.status_code == HTTPStatus.OK

    def test_latest_rejects_path_traversal(self, client):
        """GET /firmware/.../latest with bad path should return 400."""
        res = client.get("/api/v1/firmware/test.bad/device/latest")
        assert res.status_code == HTTPStatus.BAD_REQUEST
        assert res.get_json()["error"] == "validation_error"

    def test_upload_rejects_path_traversal(self, client):
        """POST /firmware/.../upload with bad path should return 400."""
        # First get a token
        token = client.post(
            "/api/v1/auth/login", json={"api_key": "dev-key"}
        ).get_json()["access_token"]

        res = client.post(
            "/api/v1/firmware/test.bad/device/upload",
            headers={"Authorization": f"Bearer {token}"},
            json={"version": "1.0.0", "firmware_b64": "SGVsbG8="},
        )
        assert res.status_code == HTTPStatus.BAD_REQUEST
        assert res.get_json()["error"] == "validation_error"


class TestFuzzPathValidation:
    """Property-based fuzz tests for path validation using Hypothesis."""

    @settings(max_examples=1000)
    @given(st.text(max_size=100))
    def test_fuzz_validation_matches_regex(self, value):
        """Fuzz test: validation result must be consistent with regex pattern.

        If validation passes, the value MUST match the whitelist regex.
        If validation fails, that's expected for non-matching input.
        """
        try:
            validate_path_segment(value)
            # If validation passed, it MUST match the whitelist pattern
            assert PATH_SEGMENT_PATTERN.match(value), (
                f"Validation passed but value doesn't match pattern: {value!r}"
            )
        except ValidationError:
            # Expected for non-matching input - this is correct behavior
            pass

    @settings(max_examples=500)
    @given(st.from_regex(PATH_SEGMENT_PATTERN, fullmatch=True))
    def test_fuzz_valid_patterns_always_pass(self, value):
        """Fuzz test: any string matching the whitelist pattern should pass.

        Generates random strings that match our safe pattern regex,
        and verifies they all pass validation.
        """
        # Should not raise - all regex-matching values must be accepted
        validate_path_segment(value)
