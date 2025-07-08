"""
Flask extension instances.

Provides:
- `jwt`: JWTManager for handling JSON Web Tokens.
- `cors`: CORS for cross-origin resource sharing support.
- `limiter`: Limiter for rate limiting with default thresholds.
"""

from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

jwt = JWTManager()
cors = CORS()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
)
