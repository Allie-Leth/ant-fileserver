import logging
from flask import jsonify
from werkzeug.exceptions import HTTPException


logger = logging.getLogger(__name__)

# Domain Errors
class FirmwareError(Exception):
    """Base class for all firmware-related errors."""
    pass

class DeviceNotFoundError(FirmwareError):
    """Raised when a device is not found."""
    pass
        
class VersionNotFoundError(FirmwareError):
    """Raised when a specific firmware version is not found."""
    pass

class StorageError(FirmwareError):
    """Raised when S3/List or JSON parsing fails in a non-recoverable way."""
    pass


# Error Config

_ERROR_HANDLING = {
    DeviceNotFoundError: {"Code": 404, "tag": "device_not_found", "level": "info"},
    VersionNotFoundError: {"Code": 404, "tag": "version_not_found", "level": "info"},
    StorageError: {"Code": 500, "tag": "storage_error", "level": "warning"},
    FirmwareError: {"Code": 500, "tag": "firmware_error", "level": "info"},
}

def register_error_handlers(app):
    """
    Register each domain error based on the _ERROR_HANDLING config.
    """
    for exc_cls, opts in _ERROR_HANDLING.items():
        def _make_handler(opts):
            def _handler(exc):
                log_fn = getattr(logger, opts["level"])
                # Stack trace for errors
                log_fn(f"{opts['tag']}: {exc}", exc_info=(opts["level"] == "error"))
                payload = {"error": opts["tag"], "message": str(exc)}
                return jsonify(payload), opts["Code"]
            return _handler
        
        app.register_error_handler(exc_cls, _make_handler(opts))
        
        
    @app.errorHandler(Exception)
    def handle_unexpected_error(exc):
        code = exc.code if isinstance(exc, HTTPException) else 500
        msg = str(exc) if app.config.get("DEBUG") else "Internal Server Error"
        logger.error("unexpected_error: %s", exc, exc_info=True)
        return jsonify({"error": "unexpected_error", "message": msg}), code