# Production-ready minimal image (<128MB)
# Uses Alpine Linux throughout for compatibility
# Stage 1: Builder
FROM python:3.12-alpine AS builder

# Install build dependencies for Alpine
RUN apk add --no-cache \
    build-base \
    gcc \
    musl-dev \
    libffi-dev \
    python3-dev

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Strip out unnecessary AWS services from botocore
# Keep only S3 and core required files
RUN cd /opt/venv/lib/python3.12/site-packages/botocore/data && \
    mkdir -p /tmp/keep && \
    # Keep only essential services and data files
    for item in s3 sts endpoints.json partitions.json sdk-default-configuration.json _retry.json; do \
        [ -e "$item" ] && mv "$item" /tmp/keep/ || true; \
    done && \
    # Remove all other services
    find . -maxdepth 1 -type d ! -name '.' -exec rm -rf {} + && \
    rm -f *.json || true && \
    # Restore kept items
    mv /tmp/keep/* . && \
    rmdir /tmp/keep

# Clean up virtual environment
RUN find /opt/venv -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    find /opt/venv -type d -name "*.dist-info" ! -name "METADATA" -exec rm -rf {} + 2>/dev/null || true && \
    find /opt/venv -type f -name "*.pyc" -delete && \
    find /opt/venv -type f -name "*.pyo" -delete && \
    find /opt/venv -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true && \
    find /opt/venv -type d -name "test" -exec rm -rf {} + 2>/dev/null || true && \
    rm -rf /opt/venv/lib/python3.12/site-packages/pip* && \
    rm -rf /opt/venv/lib/python3.12/site-packages/setuptools* && \
    rm -rf /opt/venv/lib/python3.12/site-packages/wheel*

# Stage 2: Runtime with Alpine for compatibility and size
FROM python:3.12-alpine

# Install minimal runtime dependencies and remove pip/setuptools for security
RUN apk add --no-cache libffi && \
    pip uninstall -y pip setuptools wheel 2>/dev/null || true && \
    rm -rf /usr/local/lib/python3.12/ensurepip && \
    rm -rf /usr/local/lib/python3.12/site-packages/pip* && \
    rm -rf /usr/local/lib/python3.12/site-packages/setuptools*

# Copy optimized virtual environment
COPY --from=builder /opt/venv /opt/venv

# Set Python path
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copy application code
COPY app app/
COPY wsgi.py .
COPY gunicorn.conf.py .

# Create non-root user
RUN adduser -D -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["gunicorn", "-c", "gunicorn.conf.py", "wsgi:application"]