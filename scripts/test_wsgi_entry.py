#!/usr/bin/env python3
"""Test script for WSGI entry point validation.

This script validates that the WSGI entry point can be loaded
and creates a valid Flask application instance.
"""

# ruff: noqa: PLC0415
import os
import sys
from pathlib import Path


def test_wsgi_import():
    """Test that wsgi module can be imported successfully.

    Returns:
        Tuple of (success, message)
    """
    try:
        # Add project root to path
        project_root = Path(__file__).parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        # Import wsgi module
        import wsgi  # noqa: F401

        return True, "WSGI module imported successfully"
    except Exception as e:
        return False, f"Failed to import WSGI module: {e}"


def test_application_creation():
    """Test that Flask application is created properly.

    Returns:
        Tuple of (success, message)
    """
    try:
        import wsgi

        # Check application exists
        if not hasattr(wsgi, "application"):
            return False, "WSGI module missing 'application' attribute"

        if not hasattr(wsgi, "app"):
            return False, "WSGI module missing 'app' attribute"

        # Check they're the same
        if wsgi.application is not wsgi.app:
            return False, "'application' and 'app' are not the same object"

        # Check it's a Flask app
        from flask import Flask

        if not isinstance(wsgi.application, Flask):
            return False, "Application is not a Flask instance"

        return True, "Flask application created successfully"
    except Exception as e:
        return False, f"Failed to validate application: {e}"


def test_application_config():
    """Test that application configuration is loaded.

    Returns:
        Tuple of (success, message)
    """
    try:
        import wsgi

        app = wsgi.application

        # Check basic configuration
        if "SECRET_KEY" not in app.config and "JWT_SECRET_KEY" not in app.config:
            return False, "Application missing security keys in configuration"

        # Check environment
        flask_env = os.environ.get("FLASK_ENV", "production")
        if flask_env == "production" and app.config.get("DEBUG", False):
            return False, "DEBUG is True in production environment"

        return True, f"Application configured for '{flask_env}' environment"
    except Exception as e:
        return False, f"Failed to check configuration: {e}"


def test_blueprints_registered():
    """Test that required blueprints are registered.

    Returns:
        Tuple of (success, message)
    """
    try:
        import wsgi

        app = wsgi.application
        blueprint_names = [bp.name for bp in app.blueprints.values()]

        required_blueprints = ["auth", "firmware"]
        missing_blueprints = [
            bp for bp in required_blueprints if bp not in blueprint_names
        ]

        if missing_blueprints:
            return False, f"Missing blueprints: {', '.join(missing_blueprints)}"

        return True, f"All required blueprints registered: {', '.join(blueprint_names)}"
    except Exception as e:
        return False, f"Failed to check blueprints: {e}"


def test_extensions_initialized():
    """Test that Flask extensions are initialized.

    Returns:
        Tuple of (success, message)
    """
    try:
        import wsgi

        app = wsgi.application

        if not hasattr(app, "extensions"):
            return False, "Application has no extensions"

        # Debug: Print what extensions are available
        available_extensions = list(app.extensions.keys())

        required_extensions = ["flask-jwt-extended", "limiter"]
        missing_extensions = [
            ext for ext in required_extensions if ext not in app.extensions
        ]

        if missing_extensions:
            return (
                False,
                f"Missing extensions: {', '.join(missing_extensions)}. Available: {', '.join(available_extensions)}",
            )

        # CORS might be registered differently, check separately
        # cors_registered = any('cors' in ext.lower() for ext in available_extensions)

        return (
            True,
            f"All required extensions initialized. Available: {', '.join(available_extensions)}",
        )
    except Exception as e:
        return False, f"Failed to check extensions: {e}"


def main():
    """Main test execution function."""
    print("=== WSGI Entry Point Validation ===\n")

    # Set minimal test environment
    os.environ.setdefault("JWT_SECRET_KEY", "test-validation-key")
    os.environ.setdefault("API_KEY_ROLES", '{"test":["admin"]}')
    # Storage configuration (required for app startup)
    os.environ.setdefault("STORAGE_ENDPOINT", "http://localhost:9000")
    os.environ.setdefault("STORAGE_BUCKET", "test-firmware")
    os.environ.setdefault("STORAGE_ACCESS_KEY_ID", "minioadmin")
    os.environ.setdefault("STORAGE_SECRET_ACCESS_KEY", "minioadmin")

    # Display environment
    flask_env = os.environ.get("FLASK_ENV", "production")
    print(f"Testing with FLASK_ENV: {flask_env}")
    print(f"Python path includes: {Path(__file__).parent.parent}\n")

    # Run tests
    tests = [
        ("Import Test", test_wsgi_import),
        ("Application Creation", test_application_creation),
        ("Configuration", test_application_config),
        ("Blueprints", test_blueprints_registered),
        ("Extensions", test_extensions_initialized),
    ]

    all_passed = True
    results = []

    for test_name, test_func in tests:
        success, message = test_func()
        results.append((test_name, success, message))
        if not success:
            all_passed = False

    # Display results
    print("=== Test Results ===\n")
    for test_name, success, message in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {message}")

    # Summary
    print(f"\n{'=' * 50}")
    if all_passed:
        print("✅ All WSGI validation tests PASSED")
        sys.exit(0)
    else:
        failed_count = sum(1 for _, success, _ in results if not success)
        print(f"❌ WSGI validation FAILED ({failed_count} test(s) failed)")
        sys.exit(1)


if __name__ == "__main__":
    main()
