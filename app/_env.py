"""
Configuration utilities.

Provides `get_config()` for loading settings from environment variables
or files, and the `ConfigurationError` exception for reporting failures.
"""

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any


class ConfigurationError(Exception):
    """Raised when a required configuration is missing or invalid."""


def get_config(
    name: str,
    *,
    default: Any | None = None,
    required: bool = False,
    cast: Callable[[str], Any] = lambda x: x,
    allow_file: bool = True,
) -> Any:
    """Load a config value by:
      1) ENV:        os.getenv(name)
      2) ENV file:  if allow_file and os.getenv(name + "_FILE"), read that file
      3) DEFAULT:    default
    Then cast it.
    If required=True and result is None/empty, raise ConfigurationError.
    """
    val = os.getenv(name)
    if allow_file and not val:
        file_path = os.getenv(f"{name}_FILE")
        if file_path:
            try:
                val = Path(file_path).read_text(encoding="utf-8").strip()
            except Exception as e:
                raise ConfigurationError(
                    f"Failed to read config file {file_path}: {e}"
                ) from e

    if not val:
        val = default

    try:
        result = cast(val) if val is not None else None
    except Exception as e:
        raise ConfigurationError(
            f"Failed to cast config '{name}' with value '{val}': {e}"
        ) from e

    if required and (result is None or (isinstance(result, str) and not result)):
        raise ConfigurationError(f"Required config '{name}' is missing or empty.")

    return result
