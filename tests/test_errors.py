import pytest
from flask import Flask
from werkzeug.exceptions import NotFound

from app.errors import (
    register_error_handlers,
    _ERROR_HANDLING,
    DeviceNotFoundError,
    VersionNotFoundError,
    DuplicateVersionError,
    ChecksumMismatchError,
    StorageError,
    FirmwareError,
)


# Helper: tiny throw-route factory
def make_throw_route(app, rule, exc):
    @app.route(rule)
    def _route():
        raise exc
    return _route



# Parametric test for every domain error in the map
@pytest.mark.parametrize(
    "exc_cls, exp",
    [
        (DeviceNotFoundError("no device"),     _ERROR_HANDLING[DeviceNotFoundError]),
        (VersionNotFoundError("v123"),         _ERROR_HANDLING[VersionNotFoundError]),
        (DuplicateVersionError("1.0.0"),       _ERROR_HANDLING[DuplicateVersionError]),
        (ChecksumMismatchError("bad sha"),     _ERROR_HANDLING[ChecksumMismatchError]),
        (StorageError("disk full"),            _ERROR_HANDLING[StorageError]),
        (FirmwareError("general failure"),     _ERROR_HANDLING[FirmwareError]),
    ],
)
def test_domain_errors_mapped(exc_cls, exp):
    app = Flask(__name__)
    register_error_handlers(app)
    make_throw_route(app, "/", exc_cls)

    with app.test_client() as c:
        res = c.get("/")
        body = res.get_json()

    assert res.status_code == exp["Code"]
    #   {"error": <tag>, "message": <original str(exc)>}
    assert body["error"] == exp["tag"]
    assert body["message"] == str(exc_cls)



# Unexpected / non-domain errors → 500
def test_unexpected_error():
    app = Flask(__name__)
    register_error_handlers(app)
    app.config["DEBUG"] = True

    # route raises Werkzeug's 404 *manually* so we know it's not in our map
    make_throw_route(app, "/boom", NotFound("manual - not mapped"))

    with app.test_client() as c:
        res = c.get("/boom")
        body = res.get_json()

    assert res.status_code == 404            # because NotFound carries .code = 404
    assert body["error"] == "unexpected_error"
    assert "manual - not mapped" in body["message"]