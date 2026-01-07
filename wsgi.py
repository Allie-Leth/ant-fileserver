"""WSGI entry point for ant-fileserver.

This module provides the WSGI application instance for production deployment
with Gunicorn. It handles configuration selection based on FLASK_ENV and
creates the Flask application using the factory pattern.
"""

import os
import sys
from pathlib import Path

# Ensure the project root is in the Python path
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app import create_app  # noqa: E402

# Select configuration based on FLASK_ENV
flask_env = os.environ.get("FLASK_ENV", "production")

# Create the Flask application
application = create_app(flask_env)

# Gunicorn looks for 'application' by default, but we'll also
# expose it as 'app' for compatibility
app = application

if __name__ == "__main__":
    # This block is not used by Gunicorn but allows direct execution
    # for debugging purposes
    print(f"Starting ant-fileserver in {flask_env} mode...")
    application.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000")),
        debug=(flask_env == "development"),
    )
