# Development Guide

## Overview

This guide covers local development setup, coding standards, contribution guidelines, and best practices for developing the ANT Fileserver.

## Development Environment Setup

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Kubernetes (k3s/minikube for local)
- Git
- VS Code or preferred IDE

### Local Setup

1. **Clone Repository**
   ```bash
   git clone https://github.com/yourorg/ant-fileserver.git
   cd ant-fileserver
   ```

2. **Python Virtual Environment**
   ```bash
   # Create virtual environment
   python -m venv venv
   
   # Activate virtual environment
   # Linux/Mac:
   source venv/bin/activate
   # Windows:
   venv\Scripts\activate
   
   # Install dependencies
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

3. **Environment Variables**
   ```bash
   # Copy example env file
   cp .env.example .env
   
   # Edit .env with your settings
   FLASK_ENV=development
   FLASK_DEBUG=1
   LOG_LEVEL=DEBUG
   API_KEYS=dev-key-1,dev-key-2
   STORAGE_ENDPOINT=localhost:9000
   STORAGE_ACCESS_KEY=minioadmin
   STORAGE_SECRET_KEY=minioadmin
   STORAGE_BUCKET=ant-firmware-dev
   ```

4. **Start MinIO**
   ```bash
   # Using Docker
   docker run -d \
     -p 9000:9000 \
     -p 9001:9001 \
     --name minio-dev \
     -e MINIO_ROOT_USER=minioadmin \
     -e MINIO_ROOT_PASSWORD=minioadmin \
     minio/minio server /data --console-address ":9001"
   
   # Access MinIO console at http://localhost:9001
   ```

5. **Run Application**
   ```bash
   # Development mode with auto-reload
   python run.py
   
   # Or using Flask CLI
   flask run --debug
   ```

### Docker Development

```yaml
# docker-compose.dev.yml
version: '3.8'
services:
  app:
    build:
      context: .
      dockerfile: Dockerfile.dev
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    environment:
      - FLASK_ENV=development
      - FLASK_DEBUG=1
    depends_on:
      - minio
    command: flask run --host=0.0.0.0 --port=8000 --reload
  
  minio:
    image: minio/minio
    ports:
      - "9000:9000"
      - "9001:9001"
    environment:
      - MINIO_ROOT_USER=minioadmin
      - MINIO_ROOT_PASSWORD=minioadmin
    command: server /data --console-address ":9001"
    volumes:
      - minio_data:/data

volumes:
  minio_data:
```

Run with Docker Compose:
```bash
docker-compose -f docker-compose.dev.yml up
```

## Project Structure

```
ant-fileserver/
├── app/                      # Application code
│   ├── __init__.py          # App factory
│   ├── config.py            # Configuration
│   ├── models.py            # Data models
│   ├── blueprints/          # API blueprints
│   │   ├── __init__.py
│   │   ├── firmware.py      # Firmware endpoints
│   │   └── health.py        # Health endpoints
│   └── utils/               # Utilities
│       ├── __init__.py
│       ├── auth.py          # Authentication
│       ├── storage.py       # Storage client
│       └── validators.py    # Input validation
├── tests/                   # Test suites
│   ├── unit/               # Unit tests
│   ├── integration/        # Integration tests
│   └── conftest.py         # Test fixtures
├── k8s/                    # Kubernetes manifests
├── scripts/                # Utility scripts
├── docs/                   # Documentation
├── requirements.txt        # Production dependencies
├── requirements-dev.txt    # Dev dependencies
├── Dockerfile             # Container image
├── .env.example           # Environment template
├── .gitignore            # Git ignore rules
├── .pre-commit-config.yaml # Pre-commit hooks
└── run.py                # Application entry point
```

## Coding Standards

### Python Style Guide

Follow PEP 8 with these additions:

```python
# Good: Clear, descriptive names
def upload_firmware_file(file_data: bytes, metadata: dict) -> dict:
    """Upload firmware file to storage.
    
    Args:
        file_data: Binary firmware data
        metadata: File metadata including version and device_type
        
    Returns:
        dict: Upload result with file details
        
    Raises:
        StorageError: If upload fails
    """
    pass

# Bad: Unclear names, no type hints
def upload(f, m):
    pass
```

### Code Formatting

Use Black for consistent formatting:

```bash
# Format all Python files
black app/ tests/

# Check formatting without changes
black --check app/ tests/

# Configure in pyproject.toml
[tool.black]
line-length = 88
target-version = ['py311']
```

### Linting

Use flake8 and pylint:

```bash
# Run flake8
flake8 app/ tests/

# Run pylint
pylint app/

# Configure in .flake8
[flake8]
max-line-length = 88
extend-ignore = E203, W503
exclude = venv,__pycache__
```

### Type Hints

Use type hints for all functions:

```python
from typing import Optional, Dict, List, Tuple
from werkzeug.datastructures import FileStorage

def process_firmware_upload(
    file: FileStorage,
    version: str,
    device_type: str,
    metadata: Optional[Dict[str, str]] = None
) -> Tuple[str, int]:
    """Process firmware file upload.
    
    Returns:
        Tuple of (response_data, status_code)
    """
    pass
```

## API Development

### Adding New Endpoints

1. **Create Blueprint**
   ```python
   # app/blueprints/new_feature.py
   from flask import Blueprint, jsonify, request
   from app.utils.auth import require_api_key
   
   new_feature_bp = Blueprint('new_feature', __name__)
   
   @new_feature_bp.route('/new-endpoint', methods=['GET'])
   @require_api_key
   def get_new_feature():
       # Implementation
       return jsonify({'result': 'success'})
   ```

2. **Register Blueprint**
   ```python
   # app/__init__.py
   from app.blueprints.new_feature import new_feature_bp
   
   app.register_blueprint(new_feature_bp, url_prefix='/api/v1')
   ```

3. **Add Tests**
   ```python
   # tests/unit/test_new_feature.py
   def test_get_new_feature(client, auth_headers):
       response = client.get('/api/v1/new-endpoint', headers=auth_headers)
       assert response.status_code == 200
       assert response.json['result'] == 'success'
   ```

### Error Handling

Consistent error responses:

```python
from flask import jsonify
from werkzeug.exceptions import HTTPException

class APIError(Exception):
    """Base API error class."""
    status_code = 500
    
    def __init__(self, message, status_code=None, payload=None):
        super().__init__()
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload
    
    def to_dict(self):
        rv = dict(self.payload or ())
        rv['error'] = self.message
        return rv

@app.errorhandler(APIError)
def handle_api_error(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response
```

## Testing

### Writing Tests

```python
# tests/unit/test_example.py
import pytest
from app import create_app

class TestExample:
    @pytest.fixture
    def app(self):
        """Create test application."""
        return create_app('testing')
    
    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return app.test_client()
    
    def test_example_endpoint(self, client):
        """Test example endpoint."""
        response = client.get('/api/v1/example')
        assert response.status_code == 200
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/unit/test_storage.py

# Run with verbose output
pytest -v

# Run only marked tests
pytest -m "not integration"
```

### Test Coverage

Maintain minimum 80% coverage:

```bash
# Generate coverage report
coverage run -m pytest
coverage report
coverage html

# View HTML report
open htmlcov/index.html
```

## Database Migrations

If using SQLAlchemy:

```bash
# Initialize migrations
flask db init

# Create migration
flask db migrate -m "Add user table"

# Apply migration
flask db upgrade

# Rollback migration
flask db downgrade
```

## Documentation

### API Documentation

Use docstrings for all endpoints:

```python
@firmware_bp.route('/<firmware_id>', methods=['GET'])
@require_api_key
def get_firmware(firmware_id):
    """Get firmware file details.
    
    Args:
        firmware_id: Unique firmware identifier
        
    Returns:
        JSON response with firmware metadata
        
    Status Codes:
        200: Success
        404: Firmware not found
        401: Unauthorized
    """
    pass
```

### Code Comments

```python
# Good: Explains why, not what
# Use exponential backoff to avoid overwhelming the storage service
retry_delay = min(2 ** attempt, 60)

# Bad: Redundant comment
# Increment counter by 1
counter += 1
```

## Version Control

### Git Workflow

1. **Feature Branch**
   ```bash
   git checkout -b feature/add-new-endpoint
   ```

2. **Commit Messages**
   ```bash
   # Good: Descriptive with context
   git commit -m "feat(api): add firmware versioning endpoint
   
   - Add GET /api/v1/firmware/:id/versions
   - Return version history with metadata
   - Include pagination support"
   
   # Bad: Vague
   git commit -m "update api"
   ```

3. **Pull Request**
   - Create from feature branch
   - Add description and testing notes
   - Request review
   - Address feedback

### Commit Message Format

Follow Conventional Commits:

```
<type>(<scope>): <subject>

<body>

<footer>
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Formatting
- `refactor`: Code restructuring
- `test`: Adding tests
- `chore`: Maintenance

## Continuous Integration

### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
  
  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
  
  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: pytest tests/unit/
        language: system
        pass_filenames: false
```

Install hooks:
```bash
pip install pre-commit
pre-commit install
```

### GitHub Actions

```yaml
# .github/workflows/ci.yml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      - run: black --check .
      - run: flake8 .
      - run: pytest --cov=app
```

## Performance Optimization

### Profiling

```python
# Profile specific functions
import cProfile
import pstats

def profile_function():
    profiler = cProfile.Profile()
    profiler.enable()
    
    # Code to profile
    expensive_operation()
    
    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(10)
```

### Caching

```python
from flask_caching import Cache

cache = Cache(config={'CACHE_TYPE': 'simple'})

@cache.cached(timeout=300)
def get_firmware_list():
    # Expensive operation cached for 5 minutes
    return storage_client.list_files()
```

## Security Best Practices

1. **Never commit secrets**
   ```bash
   # Use environment variables
   API_KEY = os.environ.get('API_KEY')
   
   # Not hardcoded
   API_KEY = 'secret-key-123'  # Never do this!
   ```

2. **Validate all inputs**
   ```python
   from marshmallow import Schema, fields, validate
   
   class FirmwareUploadSchema(Schema):
       version = fields.Str(required=True, validate=validate.Regexp(r'^\d+\.\d+\.\d+$'))
       device_type = fields.Str(required=True, validate=validate.Length(min=1, max=50))
   ```

3. **Use secure defaults**
   ```python
   # Secure session configuration
   app.config['SESSION_COOKIE_SECURE'] = True
   app.config['SESSION_COOKIE_HTTPONLY'] = True
   app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
   ```

## Debugging

### Local Debugging

```python
# Enable debug mode
export FLASK_DEBUG=1

# Use debugger
import pdb; pdb.set_trace()

# Or IPython debugger
import ipdb; ipdb.set_trace()
```

### Remote Debugging

VS Code launch.json:
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: Flask",
      "type": "python",
      "request": "launch",
      "module": "flask",
      "env": {
        "FLASK_APP": "run.py",
        "FLASK_ENV": "development"
      },
      "args": ["run", "--no-debugger", "--no-reload"],
      "jinja": true
    }
  ]
}
```

## Contributing

### Code Review Checklist

- [ ] Tests pass
- [ ] Code follows style guide
- [ ] Documentation updated
- [ ] No hardcoded secrets
- [ ] Error handling implemented
- [ ] Performance considered
- [ ] Security reviewed

### Release Process

1. Update version in `__version__.py`
2. Update CHANGELOG.md
3. Create git tag
4. Push tag to trigger CI/CD
5. Monitor deployment