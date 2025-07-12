# Application Architecture

## Overview

The ANT Fileserver is built using Flask 3.0 with a modular blueprint architecture. It provides a RESTful API for firmware file management with MinIO as the object storage backend.

## Architecture Diagram

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│                 │     │                  │     │                 │
│  Client Apps    │────▶│  ANT Fileserver  │────▶│  MinIO Storage  │
│                 │     │                  │     │                 │
└─────────────────┘     └──────────────────┘     └─────────────────┘
         │                       │                         │
         │                       ▼                         │
         │              ┌──────────────────┐              │
         └──────────────│   Kubernetes    │──────────────┘
                        │  Infrastructure │
                        └──────────────────┘
```

## Core Components

### 1. Application Factory (`app/__init__.py`)

The application uses the factory pattern for flexibility:

```python
def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    storage_client.init_app(app)
    
    # Register blueprints
    from app.blueprints.firmware import firmware_bp
    from app.blueprints.health import health_bp
    
    app.register_blueprint(firmware_bp, url_prefix='/api/v1/firmware')
    app.register_blueprint(health_bp)
    
    return app
```

### 2. Configuration Management (`app/config.py`)

Environment-based configuration with security defaults:

```python
class Config:
    # Core settings
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')
    API_KEYS = [key.strip() for key in os.environ.get('API_KEYS', '').split(',')]
    
    # Storage settings
    STORAGE_ENDPOINT = os.environ.get('STORAGE_ENDPOINT', 'localhost:9000')
    STORAGE_ACCESS_KEY = os.environ.get('STORAGE_ACCESS_KEY')
    STORAGE_SECRET_KEY = os.environ.get('STORAGE_SECRET_KEY')
    STORAGE_BUCKET = os.environ.get('STORAGE_BUCKET', 'ant-firmware')
    STORAGE_SECURE = os.environ.get('STORAGE_SECURE', 'true').lower() == 'true'
    
    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
```

### 3. Blueprints

#### Firmware Blueprint (`app/blueprints/firmware.py`)
Handles all firmware-related operations:

- **GET /api/v1/firmware** - List firmware files
- **GET /api/v1/firmware/<fid>** - Download specific firmware
- **POST /api/v1/firmware** - Upload new firmware
- **DELETE /api/v1/firmware/<fid>** - Delete firmware

#### Health Blueprint (`app/blueprints/health.py`)
Kubernetes health checks:

- **GET /health** - Liveness probe
- **GET /ready** - Readiness probe

### 4. Storage Client (`app/utils/storage.py`)

MinIO integration with error handling:

```python
class StorageClient:
    def init_app(self, app):
        self.client = Minio(
            app.config['STORAGE_ENDPOINT'],
            access_key=app.config['STORAGE_ACCESS_KEY'],
            secret_key=app.config['STORAGE_SECRET_KEY'],
            secure=app.config['STORAGE_SECURE']
        )
        self.bucket = app.config['STORAGE_BUCKET']
        self._ensure_bucket()
    
    def upload_file(self, file_data, file_name, metadata=None):
        # Implementation with error handling
        
    def download_file(self, file_name):
        # Implementation with streaming support
        
    def list_files(self, prefix=None):
        # Implementation with pagination
```

### 5. Authentication (`app/utils/auth.py`)

API key-based authentication:

```python
def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key or api_key not in current_app.config['API_KEYS']:
            return jsonify({'error': 'Invalid or missing API key'}), 401
        return f(*args, **kwargs)
    return decorated_function
```

### 6. Data Models (`app/models.py`)

Firmware metadata structure:

```python
class FirmwareMetadata:
    def __init__(self, filename, version, device_type, size, checksum, uploaded_at):
        self.filename = filename
        self.version = version
        self.device_type = device_type
        self.size = size
        self.checksum = checksum
        self.uploaded_at = uploaded_at
    
    def to_dict(self):
        return {
            'filename': self.filename,
            'version': self.version,
            'device_type': self.device_type,
            'size': self.size,
            'checksum': self.checksum,
            'uploaded_at': self.uploaded_at.isoformat()
        }
```

## Security Features

### 1. Authentication
- API key authentication required for all firmware operations
- Keys stored securely in environment variables
- No hardcoded credentials

### 2. Input Validation
- File type validation (allowed extensions)
- File size limits
- Metadata validation
- SQL injection prevention

### 3. Error Handling
- Structured error responses
- No sensitive information in errors
- Proper HTTP status codes
- Request ID tracking

### 4. Logging
- Structured JSON logging
- No sensitive data in logs
- Configurable log levels
- Request/response logging

## Performance Considerations

### 1. Streaming Downloads
- Large files streamed directly from MinIO
- No full file loading in memory
- Efficient byte-range support

### 2. Connection Pooling
- MinIO client connection reuse
- Configurable timeouts
- Retry logic for transient failures

### 3. Caching Headers
- ETag support for firmware files
- Cache-Control headers
- Last-Modified timestamps

## Error Handling

### Global Error Handler
```python
@app.errorhandler(Exception)
def handle_exception(e):
    if isinstance(e, HTTPException):
        return jsonify({'error': e.description}), e.code
    
    # Log the error
    app.logger.error(f'Unhandled exception: {str(e)}')
    
    # Return generic error in production
    if app.config['ENV'] == 'production':
        return jsonify({'error': 'Internal server error'}), 500
    else:
        return jsonify({'error': str(e)}), 500
```

### Storage Error Handling
- Connection failures
- Bucket not found
- Permission errors
- Network timeouts

## Monitoring Integration

### Metrics Endpoint
The application can expose Prometheus metrics:

```python
# /metrics endpoint for Prometheus
@app.route('/metrics')
def metrics():
    # Return prometheus formatted metrics
    return generate_metrics()
```

### Health Checks
- **/health**: Basic liveness check
- **/ready**: Checks MinIO connectivity

## Development Considerations

### 1. Environment Variables
Required environment variables:
- `STORAGE_ENDPOINT`
- `STORAGE_ACCESS_KEY`
- `STORAGE_SECRET_KEY`
- `API_KEYS`

### 2. Local Development
```bash
# .env file for local development
FLASK_ENV=development
FLASK_DEBUG=1
STORAGE_ENDPOINT=localhost:9000
STORAGE_ACCESS_KEY=minioadmin
STORAGE_SECRET_KEY=minioadmin
API_KEYS=dev-key-1,dev-key-2
```

### 3. Testing
- Unit tests for each component
- Integration tests with MinIO
- API endpoint tests
- Load testing support

## Future Enhancements

1. **Database Integration**
   - PostgreSQL for metadata
   - File indexing
   - Search capabilities

2. **Enhanced Security**
   - OAuth2 authentication
   - Role-based access control
   - Audit logging

3. **Performance**
   - Redis caching
   - CDN integration
   - Async uploads

4. **Features**
   - Firmware versioning
   - Delta updates
   - Signature verification