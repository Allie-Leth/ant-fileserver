"""Gunicorn configuration file for ant-fileserver.

This module configures Gunicorn WSGI server settings for production deployment
including worker processes, logging, and request handling parameters.
"""

import os

# Server socket
bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
backlog = 2048

# Worker processes
# Use environment variable for explicit control in containerized environments
# Default to 2 workers which is suitable for most microservices
workers = int(
    os.environ.get("GUNICORN_WORKERS", os.environ.get("WEB_CONCURRENCY", "2"))
)
worker_class = "sync"  # Best for CPU-bound Flask apps
worker_connections = 1000  # Only used by async workers
max_requests = 1000  # Restart workers after N requests to prevent memory leaks
max_requests_jitter = 50  # Randomize restart to avoid all workers restarting at once
timeout = 60  # Increased timeout for file upload operations
keepalive = 2  # Keep connections alive for 2 seconds

# Restart workers after this many seconds
graceful_timeout = 30

# Logging configuration for container environments
# Log to stdout/stderr for container log aggregation
accesslog = "-"  # stdout
errorlog = "-"  # stderr
# Include forwarded IP and request duration for better observability
access_log_format = (
    '%({x-forwarded-for}i)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'
)
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")

# Process naming
proc_name = "ant-fileserver"

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# Security configuration
# Trust forwarded headers from Nginx Ingress Controller
forwarded_allow_ips = "*"  # Safe in Kubernetes as ingress is trusted
secure_scheme_headers = {
    "X-FORWARDED-PROTOCOL": "https",
    "X-FORWARDED-PROTO": "https",
    "X-FORWARDED-SSL": "on",
}

# Request limits to prevent DoS attacks
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# StatsD integration (optional)
statsd_host = os.environ.get("STATSD_HOST")
if statsd_host:
    statsd_prefix = "ant-fileserver"

# Application preloading
# Set to False to allow code reloading in development
# Set to True in production for better memory usage
preload_app = os.environ.get("GUNICORN_PRELOAD", "false").lower() == "true"


def pre_fork(server, worker):
    """Called just before a worker is forked."""
    server.log.info("Forking worker %s", worker.pid)


def post_fork(server, worker):
    """Called just after a worker is forked."""
    server.log.info("Worker spawned (pid: %s)", worker.pid)


def worker_int(worker):
    """Called just after a worker exited on SIGINT or SIGQUIT."""
    worker.log.info("worker received INT or QUIT signal")


def pre_exec(server):
    """Called just before a new master process is forked."""
    server.log.info("Forking new master process")


def when_ready(server):
    """Called just after the server is started."""
    server.log.info("Server is ready. Listening at: %s", server.cfg.bind)


def worker_abort(worker):
    """Called when a worker received the SIGABRT signal."""
    worker.log.info("Worker received SIGABRT signal")


def on_exit(server):
    """Called just before the master process exits."""
    server.log.info("Server is shutting down")
