#!/usr/bin/env python3
"""Validation script for Gunicorn configuration.

This script validates the Gunicorn configuration file by loading it
and checking all settings are properly configured.
"""

import importlib.util
import os
import sys
from pathlib import Path


def load_config(config_path):
    """Load Gunicorn configuration module.

    Args:
        config_path: Path to the configuration file

    Returns:
        Loaded configuration module

    Raises:
        SystemExit: If configuration cannot be loaded
    """
    try:
        spec = importlib.util.spec_from_file_location("gunicorn_conf", config_path)
        config = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(config)
        return config
    except Exception as e:
        print(f"ERROR: Failed to load configuration: {e}", file=sys.stderr)
        sys.exit(1)


def validate_config(config):
    """Validate Gunicorn configuration settings.

    Args:
        config: Loaded configuration module

    Returns:
        Tuple of (is_valid, errors)
    """
    errors = []
    warnings = []

    # Required attributes
    required_attrs = [
        "bind",
        "workers",
        "worker_class",
        "timeout",
        "accesslog",
        "errorlog",
        "loglevel",
        "proc_name",
    ]

    for attr in required_attrs:
        if not hasattr(config, attr):
            errors.append(f"Missing required configuration: {attr}")

    # Validate specific settings
    if hasattr(config, "workers"):
        max_workers = 16  # Maximum recommended workers
        if not isinstance(config.workers, int) or config.workers < 1:
            errors.append(
                f"Invalid workers value: {config.workers} (must be positive integer)"
            )
        elif config.workers > max_workers:
            warnings.append(
                f"High worker count: {config.workers} (may consume excessive resources)"
            )

    if hasattr(config, "timeout"):
        if not isinstance(config.timeout, int) or config.timeout < 1:
            errors.append(
                f"Invalid timeout value: {config.timeout} (must be positive integer)"
            )

    if hasattr(config, "worker_class"):
        valid_worker_classes = ["sync", "eventlet", "gevent", "tornado", "gthread"]
        if config.worker_class not in valid_worker_classes:
            errors.append(
                f"Invalid worker_class: {config.worker_class} (must be one of {valid_worker_classes})"
            )

    # Check lifecycle hooks
    hooks = [
        "pre_fork",
        "post_fork",
        "worker_int",
        "pre_exec",
        "when_ready",
        "worker_abort",
        "on_exit",
    ]
    for hook in hooks:
        if hasattr(config, hook) and not callable(getattr(config, hook)):
            errors.append(f"Hook {hook} is not callable")

    return len(errors) == 0, errors, warnings


def print_config_summary(config):
    """Print configuration summary.

    Args:
        config: Loaded configuration module
    """
    print("\n=== Gunicorn Configuration Summary ===")
    print(f"Bind: {getattr(config, 'bind', 'NOT SET')}")
    print(f"Workers: {getattr(config, 'workers', 'NOT SET')}")
    print(f"Worker Class: {getattr(config, 'worker_class', 'NOT SET')}")
    print(f"Timeout: {getattr(config, 'timeout', 'NOT SET')}s")
    print(f"Max Requests: {getattr(config, 'max_requests', 'NOT SET')}")
    print(f"Keepalive: {getattr(config, 'keepalive', 'NOT SET')}s")
    print(f"Access Log: {getattr(config, 'accesslog', 'NOT SET')}")
    print(f"Error Log: {getattr(config, 'errorlog', 'NOT SET')}")
    print(f"Log Level: {getattr(config, 'loglevel', 'NOT SET')}")
    print(f"Preload App: {getattr(config, 'preload_app', 'NOT SET')}")

    if hasattr(config, "statsd_host") and config.statsd_host:
        print(f"StatsD Host: {config.statsd_host}")
        print(f"StatsD Prefix: {getattr(config, 'statsd_prefix', 'NOT SET')}")

    print("\n=== Security Settings ===")
    print(f"Forwarded Allow IPs: {getattr(config, 'forwarded_allow_ips', 'NOT SET')}")
    print(f"Request Line Limit: {getattr(config, 'limit_request_line', 'NOT SET')}")
    print(f"Request Fields Limit: {getattr(config, 'limit_request_fields', 'NOT SET')}")
    print(
        f"Request Field Size Limit: {getattr(config, 'limit_request_field_size', 'NOT SET')}"
    )

    print("\n=== Environment Variables ===")
    env_vars = [
        "PORT",
        "GUNICORN_WORKERS",
        "WEB_CONCURRENCY",
        "GUNICORN_LOG_LEVEL",
        "GUNICORN_PRELOAD",
        "STATSD_HOST",
    ]
    for var in env_vars:
        value = os.environ.get(var)
        if value:
            print(f"{var}: {value}")


def main():
    """Main validation function."""
    # Determine config path
    if len(sys.argv) > 1:
        config_path = Path(sys.argv[1])
    else:
        config_path = Path(__file__).parent.parent / "gunicorn.conf.py"

    if not config_path.exists():
        print(f"ERROR: Configuration file not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Validating Gunicorn configuration: {config_path}")

    # Load configuration
    config = load_config(config_path)

    # Validate configuration
    is_valid, errors, warnings = validate_config(config)

    # Print summary
    print_config_summary(config)

    # Print validation results
    print("\n=== Validation Results ===")
    if warnings:
        print("\nWarnings:")
        for warning in warnings:
            print(f"  ⚠️  {warning}")

    if errors:
        print("\nErrors:")
        for error in errors:
            print(f"  ❌ {error}")
        print(f"\n❌ Configuration validation FAILED with {len(errors)} error(s)")
        sys.exit(1)
    else:
        print("\n✅ Configuration validation PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
