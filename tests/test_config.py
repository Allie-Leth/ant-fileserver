import os
import pytest
from flask import Flask

from app.config import BaseConfig, ConfigurationError


def test_init_app_invalid_json(monkeypatch):
    """
    Put malformed JSON in API_KEY_ROLES.
    init_app must raise ConfigurationError (lines 35-36).
    """

    # ── All required env-vars ───────────────────────────────────────────
    monkeypatch.setenv("STORAGE_ENDPOINT", "http://s3")
    monkeypatch.setenv("STORAGE_BUCKET", "fw")
    monkeypatch.setenv("STORAGE_ACCESS_KEY_ID", "k")
    monkeypatch.setenv("STORAGE_SECRET_ACCESS_KEY", "s")
    monkeypatch.setenv("JWT_SECRET_KEY", "supersecret")

    # malformed JSON → triggers the except branch
    monkeypatch.setenv("API_KEY_ROLES", "{not:json")

    app = Flask(__name__)

    with pytest.raises(ConfigurationError):
        BaseConfig.init_app(app)