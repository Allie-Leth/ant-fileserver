"""Application factory module.

Exposes `create_app`, which:
  1) Loads & validates config
  2) Sets up logging
  3) Initializes extensions (JWT, CORS, rate-limiter)
  4) Builds the FirmwareService and FactoryService
  5) Registers auth, firmware, and factory blueprints
  6) Registers centralized error handlers
"""

import logging.config
from datetime import UTC, datetime

from flask import Flask

from app.blueprints.auth.routes import auth_bp
from app.blueprints.factory.routes import factory_bp
from app.blueprints.factory.service import FactoryService
from app.blueprints.firmware.routes import firmware_bp
from app.blueprints.firmware.service import FirmwareService
from app.blueprints.ops.routes import health_bp, ops_bp

from .config import config_map
from .errors import register_error_handlers
from .extensions import cors, jwt, limiter


def create_app(config_name: str = "default") -> Flask:
    """Application factory: configures and returns a Flask app instance."""
    # ── App & Config ───────────────────────────────────────────────────────
    app = Flask(__name__)
    cfg_cls = config_map.get(config_name, config_map["default"])
    app.config.from_object(cfg_cls)
    cfg_cls.init_app(app)

    # Store application start time for metrics
    app.config["START_TIME"] = datetime.now(UTC)

    # ── Logging ────────────────────────────────────────────────────────────
    level = app.config["LOG_LEVEL"]
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "[%(asctime)s] %(levelname)8s %(name)s: %(message)s"
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "level": level,
                }
            },
            "root": {"handlers": ["console"], "level": level},
        }
    )

    app.config.update(
        JWT_TOKEN_LOCATION=["headers", "json"],
        JWT_JSON_KEY="access_token",
    )

    # ── Extensions ─────────────────────────────────────────────────────────
    jwt.init_app(app)
    cors.init_app(app)
    limiter.init_app(app)

    # ── Domain Services ────────────────────────────────────────────────────
    # Store service instances on the app for access via current_app
    app.firmware_service = FirmwareService(
        endpoint_url=app.config["STORAGE_ENDPOINT"],
        bucket=app.config["STORAGE_BUCKET"],
        access_key_id=app.config["STORAGE_ACCESS_KEY_ID"],
        secret_access_key=app.config["STORAGE_SECRET_ACCESS_KEY"],
        region=app.config["STORAGE_REGION"],
    )

    app.factory_service = FactoryService(
        endpoint_url=app.config["STORAGE_ENDPOINT"],
        bucket=app.config["STORAGE_BUCKET"],
        access_key_id=app.config["STORAGE_ACCESS_KEY_ID"],
        secret_access_key=app.config["STORAGE_SECRET_ACCESS_KEY"],
        region=app.config["STORAGE_REGION"],
    )

    # ── Register Blueprints ───────────────────────────────────────────────
    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(firmware_bp, url_prefix="/api/v1/firmware")
    app.register_blueprint(factory_bp, url_prefix="/api/v1/factory")

    # Register ops blueprints (no authentication required)
    app.register_blueprint(health_bp)  # Direct /health and /ready endpoints
    app.register_blueprint(ops_bp)  # /api/v1/ops/health, /api/v1/ops/ready, etc.

    # ── Error Handlers ─────────────────────────────────────────────────────
    register_error_handlers(app)

    return app
