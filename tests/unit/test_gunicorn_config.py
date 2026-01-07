"""Unit tests for Gunicorn configuration.

This module tests the Gunicorn configuration settings to ensure they
are properly loaded and respond correctly to environment variables.
"""

# ruff: noqa: PLC0415 PLR2004
import os
import sys

import pytest


class TestGunicornConfig:
    """Test suite for Gunicorn configuration validation."""

    def setup_method(self):
        """Set up test environment before each test."""
        # Store original environment
        self.original_env = os.environ.copy()
        # Clear any gunicorn-related env vars
        for key in list(os.environ.keys()):
            if key.startswith("GUNICORN_") or key in [
                "PORT",
                "WEB_CONCURRENCY",
                "STATSD_HOST",
            ]:
                del os.environ[key]

    def teardown_method(self):
        """Restore original environment after each test."""
        os.environ.clear()
        os.environ.update(self.original_env)
        # Remove gunicorn_conf from sys.modules to force reload
        if "gunicorn_conf" in sys.modules:
            del sys.modules["gunicorn_conf"]

    def _load_config(self):
        """Helper to load gunicorn config module."""
        # Import the config file from project root
        import importlib.util
        from pathlib import Path

        config_path = Path(__file__).parent.parent.parent / "gunicorn.conf.py"
        spec = importlib.util.spec_from_file_location("gunicorn_conf", config_path)
        config = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(config)
        return config

    def test_default_configuration(self):
        """Test default configuration values without environment variables."""
        config = self._load_config()

        # Server socket
        assert config.bind == "0.0.0.0:8000"
        assert config.backlog == 2048

        # Worker configuration
        assert config.workers == 2  # Default value
        assert config.worker_class == "sync"
        assert config.timeout == 60
        assert config.keepalive == 2
        assert config.max_requests == 1000
        assert config.max_requests_jitter == 50

        # Logging
        assert config.accesslog == "-"
        assert config.errorlog == "-"
        assert config.loglevel == "info"

        # Security
        assert config.forwarded_allow_ips == "*"
        assert config.limit_request_line == 4094
        assert config.limit_request_fields == 100
        assert config.limit_request_field_size == 8190

        # Process
        assert config.proc_name == "ant-fileserver"
        assert config.daemon is False
        assert config.preload_app is False  # Default is False

    def test_environment_variable_override(self):
        """Test that environment variables properly override defaults."""
        # Set environment variables
        os.environ["PORT"] = "9000"
        os.environ["GUNICORN_WORKERS"] = "4"
        os.environ["GUNICORN_LOG_LEVEL"] = "debug"
        os.environ["GUNICORN_PRELOAD"] = "true"
        os.environ["STATSD_HOST"] = "statsd.example.com"

        config = self._load_config()

        assert config.bind == "0.0.0.0:9000"
        assert config.workers == 4
        assert config.loglevel == "debug"
        assert config.preload_app is True
        assert config.statsd_host == "statsd.example.com"
        assert config.statsd_prefix == "ant-fileserver"

    def test_web_concurrency_fallback(self):
        """Test WEB_CONCURRENCY is used when GUNICORN_WORKERS is not set."""
        os.environ["WEB_CONCURRENCY"] = "3"

        config = self._load_config()
        assert config.workers == 3

    def test_workers_priority(self):
        """Test GUNICORN_WORKERS takes priority over WEB_CONCURRENCY."""
        os.environ["WEB_CONCURRENCY"] = "3"
        os.environ["GUNICORN_WORKERS"] = "5"

        config = self._load_config()
        assert config.workers == 5

    def test_secure_scheme_headers(self):
        """Test secure scheme headers for proxy configuration."""
        config = self._load_config()

        assert config.secure_scheme_headers == {
            "X-FORWARDED-PROTOCOL": "https",
            "X-FORWARDED-PROTO": "https",
            "X-FORWARDED-SSL": "on",
        }

    def test_access_log_format(self):
        """Test access log format includes forwarded IP."""
        config = self._load_config()

        # Check that x-forwarded-for is in the format
        assert "%({x-forwarded-for}i)s" in config.access_log_format
        assert "%(D)s" in config.access_log_format  # Request duration

    def test_lifecycle_hooks_defined(self):
        """Test that all lifecycle hooks are properly defined."""
        config = self._load_config()

        # Check all hooks are callable
        assert callable(config.pre_fork)
        assert callable(config.post_fork)
        assert callable(config.worker_int)
        assert callable(config.pre_exec)
        assert callable(config.when_ready)
        assert callable(config.worker_abort)
        assert callable(config.on_exit)

    def test_invalid_worker_count_defaults(self):
        """Test that invalid worker counts fall back to default."""
        os.environ["GUNICORN_WORKERS"] = "invalid"

        # This should raise ValueError which should be caught
        with pytest.raises(ValueError):
            self._load_config()

    def test_preload_app_case_insensitive(self):
        """Test preload_app handles various boolean representations."""
        test_cases = [
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("false", False),
            ("False", False),
            ("FALSE", False),
            ("1", False),  # Only 'true' is considered True
            ("yes", False),
            ("", False),
        ]

        for value, expected in test_cases:
            os.environ["GUNICORN_PRELOAD"] = value
            config = self._load_config()
            assert config.preload_app == expected, f"Failed for value: {value}"
            # Clean up for next iteration
            if "gunicorn_conf" in sys.modules:
                del sys.modules["gunicorn_conf"]
            if "GUNICORN_PRELOAD" in os.environ:
                del os.environ["GUNICORN_PRELOAD"]

    def test_statsd_configuration(self):
        """Test StatsD configuration is conditional."""
        # Without STATSD_HOST
        config = self._load_config()
        assert config.statsd_host is None
        assert (
            not hasattr(config, "statsd_prefix")
            or config.statsd_prefix == "ant-fileserver"
        )

        # With STATSD_HOST
        if "gunicorn_conf" in sys.modules:
            del sys.modules["gunicorn_conf"]
        os.environ["STATSD_HOST"] = "metrics.local:8125"
        config = self._load_config()
        assert config.statsd_host == "metrics.local:8125"
        assert config.statsd_prefix == "ant-fileserver"
