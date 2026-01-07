"""Integration tests for WSGI application.

This module tests that the WSGI application can be created successfully
and responds to requests when loaded through the wsgi entry point.
"""

# ruff: noqa: PLC0415
import os
import sys

import pytest


@pytest.mark.integration
class TestWSGIApp:
    """Test suite for WSGI application integration."""

    def setup_method(self):
        """Set up test environment before each test."""
        # Store original environment
        self.original_env = os.environ.copy()

        # Set test configuration
        os.environ["FLASK_ENV"] = "testing"
        os.environ["JWT_SECRET_KEY"] = "test-secret-key"
        os.environ["API_KEY_ROLES"] = '{"test-key":["admin","uploader"]}'

        # Storage configuration (will fail gracefully in testing)
        os.environ["STORAGE_ENDPOINT"] = "http://localhost:9000"
        os.environ["STORAGE_BUCKET"] = "test-firmware"
        os.environ["STORAGE_ACCESS_KEY_ID"] = "minioadmin"
        os.environ["STORAGE_SECRET_ACCESS_KEY"] = "minioadmin"

    def teardown_method(self):
        """Restore original environment after each test."""
        os.environ.clear()
        os.environ.update(self.original_env)

        # Remove wsgi from imports to force reload
        if "wsgi" in sys.modules:
            del sys.modules["wsgi"]

    def test_wsgi_app_creation(self):
        """Test that WSGI application can be created successfully."""
        # Import wsgi module
        import wsgi

        # Verify application was created
        assert wsgi.application is not None
        assert wsgi.app is not None
        assert wsgi.application == wsgi.app

        # Verify it's a Flask application
        from flask import Flask

        assert isinstance(wsgi.application, Flask)

    def test_wsgi_app_configuration(self):
        """Test that WSGI application has correct configuration."""
        # Import wsgi module
        import wsgi

        app = wsgi.application

        # Verify configuration is loaded from environment
        # Note: The app may be created with different config based on when wsgi was imported
        assert app.config["JWT_SECRET_KEY"] is not None

        # Verify API key roles are loaded if set
        if "API_KEY_ROLES" in app.config:
            assert isinstance(app.config["API_KEY_ROLES"], dict)

    def test_wsgi_app_blueprints_registered(self):
        """Test that all blueprints are registered in WSGI app."""
        # Import wsgi module
        import wsgi

        app = wsgi.application

        # Get registered blueprint names
        blueprint_names = [bp.name for bp in app.blueprints.values()]

        # Verify expected blueprints are registered
        assert "auth" in blueprint_names
        assert "firmware" in blueprint_names

    def test_wsgi_app_request_context(self):
        """Test that WSGI app can handle request contexts."""
        # Import wsgi module
        import wsgi

        app = wsgi.application

        # Create a test client
        client = app.test_client()

        # Make a request to a non-existent endpoint (should return 404)
        response = client.get("/non-existent")
        assert response.status_code == 404  # noqa: PLR2004

        # Test that error handler returns JSON
        data = response.get_json()
        assert data is not None
        assert "error" in data

    def test_wsgi_app_extensions_initialized(self):
        """Test that Flask extensions are properly initialized."""
        # Import wsgi module
        import wsgi

        app = wsgi.application

        # Verify JWT extension is initialized
        assert hasattr(app, "extensions")
        assert "flask-jwt-extended" in app.extensions

        # Verify limiter is initialized
        assert "limiter" in app.extensions

        # Note: CORS doesn't register itself in app.extensions
        # but we can verify it's working by checking if CORS headers are added

    def test_wsgi_app_handles_different_environments(self):
        """Test WSGI app creation with different environment settings."""
        # Test with production environment
        os.environ["FLASK_ENV"] = "production"

        # Remove wsgi from imports to force reload
        if "wsgi" in sys.modules:
            del sys.modules["wsgi"]

        # Import wsgi module
        import wsgi

        app = wsgi.application

        # Verify production configuration
        assert app.config["TESTING"] is False
        assert app.config["DEBUG"] is False

    def test_wsgi_app_error_handlers(self):
        """Test that WSGI app has proper error handlers."""
        # Import wsgi module
        import wsgi

        app = wsgi.application
        client = app.test_client()

        # Test 404 error
        response = client.get("/this-route-does-not-exist")
        assert response.status_code == 404  # noqa: PLR2004
        assert response.content_type == "application/json"

        # Test method not allowed (405)
        response = client.post("/")  # Assuming GET only
        assert response.status_code in [404, 405]  # Could be either
        assert response.content_type == "application/json"

    def test_wsgi_app_with_gunicorn_callable(self):
        """Test that WSGI app provides the correct callable for Gunicorn."""
        # Import wsgi module
        import wsgi

        # Verify both 'application' and 'app' are callable
        assert callable(wsgi.application)
        assert callable(wsgi.app)

        # Verify they're the same object
        assert wsgi.application is wsgi.app

        # Verify it's a valid WSGI application
        # WSGI apps should be callable with (environ, start_response)
        from flask import Flask

        assert isinstance(wsgi.application, Flask)
