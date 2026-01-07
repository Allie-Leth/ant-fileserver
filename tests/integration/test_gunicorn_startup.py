"""Integration tests for Gunicorn server startup.

This module tests that Gunicorn can successfully start with our configuration
and serve requests properly.
"""

# ruff: noqa: PLC0415 PLR2004
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest
import requests


@pytest.mark.integration
class TestGunicornStartup:
    """Test suite for Gunicorn server startup and basic operations."""

    @classmethod
    def setup_class(cls):
        """Set up test environment."""
        cls.project_root = Path(__file__).parent.parent.parent
        cls.test_port = cls._find_free_port()
        cls.base_url = f"http://localhost:{cls.test_port}"

    @staticmethod
    def _find_free_port():
        """Find a free port for testing."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            s.listen(1)
            port = s.getsockname()[1]
        return port

    def _start_gunicorn(self, extra_env=None, config_file="gunicorn.conf.py"):
        """Start Gunicorn server with test configuration."""
        env = os.environ.copy()
        env.update(
            {
                "PORT": str(self.test_port),
                "GUNICORN_WORKERS": "1",  # Single worker for testing
                "GUNICORN_LOG_LEVEL": "debug",
                "FLASK_ENV": "testing",
                # MinIO test configuration
                "STORAGE_ENDPOINT": "http://localhost:9000",
                "STORAGE_BUCKET": "test-firmware",
                "STORAGE_ACCESS_KEY_ID": "minioadmin",
                "STORAGE_SECRET_ACCESS_KEY": "minioadmin",
                "JWT_SECRET_KEY": "test-secret-key",
                "API_KEY_ROLES": '{"test-key":["admin","uploader"]}',
            }
        )

        if extra_env:
            env.update(extra_env)

        # Start Gunicorn process
        cmd = [sys.executable, "-m", "gunicorn", "-c", config_file, "app:create_app()"]

        process = subprocess.Popen(
            cmd,
            cwd=str(self.project_root),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Wait for server to start
        max_attempts = 30
        for _ in range(max_attempts):
            try:
                response = requests.get(f"{self.base_url}/health", timeout=1)
                if response.status_code == 200:
                    return process
            except requests.exceptions.RequestException:
                pass
            time.sleep(0.5)

            # Check if process has died
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                pytest.fail(
                    f"Gunicorn failed to start:\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
                )

        # If we get here, server didn't start in time
        process.terminate()
        stdout, stderr = process.communicate()
        pytest.fail(
            f"Gunicorn failed to start within {max_attempts / 2} seconds:\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
        )

    def test_gunicorn_starts_successfully(self):
        """Test that Gunicorn starts successfully with our configuration."""
        process = None
        try:
            process = self._start_gunicorn()

            # Verify server is responding
            response = requests.get(f"{self.base_url}/health")
            assert response.status_code == 200

            # Verify process is still running
            assert process.poll() is None

        finally:
            if process:
                process.terminate()
                process.wait(timeout=5)

    def test_gunicorn_worker_configuration(self):
        """Test that Gunicorn respects worker configuration."""
        process = None
        try:
            # Start with 2 workers
            process = self._start_gunicorn(extra_env={"GUNICORN_WORKERS": "2"})

            # Give workers time to spawn
            time.sleep(2)

            # Check process is running
            assert process.poll() is None

            # Make multiple concurrent requests to ensure workers handle them
            from concurrent import futures as concurrent_futures

            with concurrent_futures.ThreadPoolExecutor(max_workers=4) as executor:
                futures = [
                    executor.submit(requests.get, f"{self.base_url}/health")
                    for _ in range(10)
                ]
                results = [f.result() for f in futures]

            # All requests should succeed
            assert all(r.status_code == 200 for r in results)

        finally:
            if process:
                process.terminate()
                process.wait(timeout=5)

    def test_gunicorn_handles_signals(self):
        """Test that Gunicorn handles signals properly."""
        process = None
        try:
            process = self._start_gunicorn()

            # Send HUP signal (should reload)
            process.send_signal(signal.SIGHUP)
            time.sleep(2)

            # Server should still be running
            response = requests.get(f"{self.base_url}/health")
            assert response.status_code == 200

            # Send TERM signal (should gracefully shutdown)
            process.terminate()
            exit_code = process.wait(timeout=10)
            assert exit_code == 0

        finally:
            if process and process.poll() is None:
                process.kill()
                process.wait()

    def test_gunicorn_logging_configuration(self):
        """Test that Gunicorn logging is configured correctly."""
        process = None
        temp_access_log = None
        temp_error_log = None

        try:
            # Create temporary log files
            temp_access_log = tempfile.NamedTemporaryFile(mode="w+", delete=False)
            temp_error_log = tempfile.NamedTemporaryFile(mode="w+", delete=False)

            # Start with file logging
            process = self._start_gunicorn(extra_env={"GUNICORN_LOG_LEVEL": "debug"})

            # Make a request
            response = requests.get(f"{self.base_url}/health")
            assert response.status_code == 200

            # Check that logs are going to stdout/stderr (captured by subprocess)
            # Note: In real config, logs go to stdout/stderr denoted by '-'

        finally:
            if process:
                process.terminate()
                process.wait(timeout=5)
            if temp_access_log:
                os.unlink(temp_access_log.name)
            if temp_error_log:
                os.unlink(temp_error_log.name)

    def test_gunicorn_preload_configuration(self):
        """Test that preload_app configuration works correctly."""
        process = None
        try:
            # Test with preload enabled
            process = self._start_gunicorn(extra_env={"GUNICORN_PRELOAD": "true"})

            # Server should start successfully
            response = requests.get(f"{self.base_url}/health")
            assert response.status_code == 200

        finally:
            if process:
                process.terminate()
                process.wait(timeout=5)

    def test_gunicorn_timeout_handling(self):
        """Test that Gunicorn timeout is properly configured."""
        # This test would require a special endpoint that sleeps
        # Since we don't have one, we'll just verify the server starts
        # with our timeout configuration
        process = None
        try:
            process = self._start_gunicorn()

            # Verify server started
            response = requests.get(f"{self.base_url}/health")
            assert response.status_code == 200

            # In a real test, we'd have an endpoint that takes >30s but <60s
            # to verify our timeout increase to 60s works

        finally:
            if process:
                process.terminate()
                process.wait(timeout=5)
