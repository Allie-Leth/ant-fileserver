import logging.config
from flask import Flask


from .config import config_map
from .extensions import jwt, cors, limiter
from .errors import register_error_handlers
from app.blueprints.auth.routes import auth_bp
from app.blueprints.firmware.routes import firmware_bp
from app.blueprints.firmware.service import FirmwareService

def create_app(config_name: str = "default") -> Flask:
    """
    Application factory: creates, configures, and returns a Flask app.
    
    Steps:
      1) Load & validate config
      2) Set up logging
      3) Initialize extensions (JWT, CORS, rate-limiter)
      4) Build your service layer
      5) Register blueprints (auth + firmware)
      6) Register centralized error handlers
    """
    
    # App & Config
    app = Flask(__name__)
    cfg_cls = config_map.get(config_name, config_map["default"])
    app.config.from_object(cfg_cls)
    cfg_cls.init_app(app)
    
    # Logging
    level = app.config["LOG_LEVEL"]
    logging.config.dictConfig({
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
                "level": level
            }
        },
        "root": {
            "handlers": ["console"],
            "level": level
        }
    })
    
    # Extensions
    jwt.init_app(app)
    cors.init_app(app)
    limiter.init_app(app)
    
    # Build Domain Service
    svc = FirmwareService(
        endpoint_url      = app.config["STORAGE_ENDPOINT"],
        bucket            = app.config["STORAGE_BUCKET"],
        access_key_id     = app.config["STORAGE_ACCESS_KEY_ID"],
        secret_access_key = app.config["STORAGE_SECRET_ACCESS_KEY"],
        region            = app.config["STORAGE_REGION"],
    )
    
    # Register Blueprints
    app.register_blueprint(auth_bp,     url_prefix="/api/v1/auth",
                           defaults={"svc": svc})
    app.register_blueprint(firmware_bp, url_prefix="/api/v1/firmware",
                           defaults={"svc": svc})
    
    # Error Handlers
    register_error_handlers(app)
    
    return app