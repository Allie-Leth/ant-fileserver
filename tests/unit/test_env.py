"""Unit-level tests for `get_config` in app._env.

Covers:
  - basic ENV retrieval
  - required/missing behavior
  - default values
  - JSON casting success/failure
  - file-based ENV loading and error paths
"""

import json

import pytest

from app._env import ConfigurationError, get_config


def test_get_config_success(monkeypatch):
    """get_config returns the ENV value when the variable is set."""
    monkeypatch.setenv("STORAGE_BUCKET", "fw")
    assert get_config("STORAGE_BUCKET") == "fw"


def test_get_config_missing(monkeypatch):
    """get_config raises ConfigurationError if required and ENV is missing."""
    monkeypatch.delenv("STORAGE_BUCKET", raising=False)
    with pytest.raises(ConfigurationError):
        get_config("STORAGE_BUCKET", required=True)


def test_default_return(monkeypatch):
    """get_config returns the default value when ENV is missing and default provided."""
    monkeypatch.delenv("DUMMY", raising=False)
    assert get_config("DUMMY", default="x") == "x"


def test_json_decode_success(monkeypatch):
    """get_config applies JSON cast successfully for valid JSON strings."""
    monkeypatch.setenv("DUMMY", "[1, 2, 3]")
    assert get_config("DUMMY", cast=json.loads) == [1, 2, 3]


def test_json_decode_failure(monkeypatch):
    """get_config raises ConfigurationError when JSON casting fails."""
    monkeypatch.setenv("DUMMY", "not-json")
    with pytest.raises(ConfigurationError):
        get_config("DUMMY", cast=json.loads)


def test_file_env_success(tmp_path, monkeypatch):
    """When FOO is unset and FOO_FILE points to a readable file, the helper should read and return its content."""
    cfg_file = tmp_path / "bucket.txt"
    cfg_file.write_text("from-file\n")  # trailing newline stripped by .strip()

    monkeypatch.delenv("BUCKET", raising=False)
    monkeypatch.setenv("BUCKET_FILE", str(cfg_file))

    assert get_config("BUCKET") == "from-file"


def test_file_env_read_error(monkeypatch):
    """Test that get_config raises ConfigurationError when the file cannot be read.

    When the file pointed to by *_FILE cannot be read, get_config must raise ConfigurationError.
    This covers the except branch on lines 29–32.
    """
    monkeypatch.delenv("BROKEN", raising=False)
    monkeypatch.setenv("BROKEN_FILE", "/path/does/not/exist")

    with pytest.raises(ConfigurationError):
        get_config("BROKEN")
