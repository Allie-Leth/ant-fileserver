# Testing Guide

## Overview

The ANT Fileserver uses a comprehensive testing strategy covering unit tests, integration tests, API tests, and Kubernetes validation. This guide covers all testing procedures and tools.

## Testing Architecture

```
tests/
├── unit/                    # Unit tests
├── integration/            # Integration tests
├── api/                   # API endpoint tests
└── load/                  # Performance tests

scripts/k8s/               # Kubernetes testing
├── test-phase1-application.sh
├── test-phase2-security.sh
├── test-phase3-production.sh
├── test-integration.sh
├── validate-all.sh
└── load-test-hpa.sh
```

## Unit Testing

### Framework

Using pytest for Python unit tests:

```bash
# Install test dependencies
pip install pytest pytest-cov pytest-mock

# Run all unit tests
pytest tests/unit/

# Run with coverage
pytest tests/unit/ --cov=app --cov-report=html

# Run specific test file
pytest tests/unit/test_storage.py
```

### Test Structure

Example unit test:

```python
# tests/unit/test_storage.py
import pytest
from unittest.mock import Mock, patch
from app.utils.storage import StorageClient

class TestStorageClient:
    @pytest.fixture
    def storage_client(self):
        with patch('app.utils.storage.Minio'):
            client = StorageClient()
            client.init_app(Mock())
            return client
    
    def test_upload_file(self, storage_client):
        # Test file upload functionality
        file_data = b"test firmware content"
        filename = "test-v1.0.0.bin"
        
        result = storage_client.upload_file(file_data, filename)
        assert result['filename'] == filename
        assert result['size'] == len(file_data)
```

### Coverage Requirements

- Minimum 80% code coverage
- Critical paths require 100% coverage
- Exclude test files and config from coverage

## Integration Testing

### Database Integration

Test with real MinIO instance:

```python
# tests/integration/test_minio_integration.py
import pytest
from minio import Minio
from app import create_app

@pytest.mark.integration
class TestMinIOIntegration:
    @pytest.fixture
    def app(self):
        return create_app('testing')
    
    def test_real_upload_download(self, app):
        # Test with actual MinIO connection
        with app.app_context():
            # Upload test file
            # Download and verify
            # Clean up
```

### Running Integration Tests

```bash
# Start MinIO for testing
docker run -d -p 9000:9000 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data

# Run integration tests
pytest tests/integration/ -m integration

# Cleanup
docker stop $(docker ps -q -f ancestor=minio/minio)
```

## API Testing

### Endpoint Testing

Test all API endpoints:

```python
# tests/api/test_firmware_api.py
import pytest
from app import create_app

class TestFirmwareAPI:
    @pytest.fixture
    def client(self):
        app = create_app('testing')
        return app.test_client()
    
    def test_list_firmware(self, client):
        response = client.get('/api/v1/firmware',
                            headers={'X-API-Key': 'test-key'})
        assert response.status_code == 200
        assert 'firmware' in response.json
    
    def test_upload_firmware(self, client):
        data = {
            'file': (BytesIO(b'firmware content'), 'test.bin'),
            'version': '1.0.0',
            'device_type': 'sensor'
        }
        response = client.post('/api/v1/firmware',
                             headers={'X-API-Key': 'test-key'},
                             data=data,
                             content_type='multipart/form-data')
        assert response.status_code == 201
```

### API Test Suite

Complete test coverage script:

```bash
#!/bin/bash
# scripts/test-api.sh

echo "Testing API Endpoints..."

# Test health endpoints
curl -f http://localhost:8000/health
curl -f http://localhost:8000/ready

# Test firmware list
curl -f -H "X-API-Key: test-key" http://localhost:8000/api/v1/firmware

# Test upload
curl -f -X POST -H "X-API-Key: test-key" \
  -F "file=@test-firmware.bin" \
  -F "version=1.0.0" \
  -F "device_type=test" \
  http://localhost:8000/api/v1/firmware

echo "API tests completed!"
```

## Kubernetes Testing

### Phase 1: Application Testing

Tests core Kubernetes resources:

```bash
./scripts/k8s/test-phase1-application.sh
```

Tests performed:
- Kustomize build validation
- Deployment configuration
- Service configuration
- ConfigMap and ServiceAccount
- Security contexts
- Resource limits
- Health probes

### Phase 2: Security Testing

Tests security configurations:

```bash
./scripts/k8s/test-phase2-security.sh
```

Tests performed:
- NetworkPolicy rules
- Ingress configuration
- TLS settings
- Pod Security Standards
- RBAC permissions
- Security headers

### Phase 3: Production Testing

Tests production features:

```bash
./scripts/k8s/test-phase3-production.sh
```

Tests performed:
- HorizontalPodAutoscaler
- PodDisruptionBudget
- Anti-affinity rules
- ServiceMonitor
- Resource scaling
- High availability

### Integration Testing

Comprehensive overlay testing:

```bash
./scripts/k8s/test-integration.sh
```

Tests all overlays work correctly:
- Local overlay
- Dev overlay
- Staging overlay
- Production overlay

### Master Validation

Run all tests:

```bash
./scripts/k8s/validate-all.sh

# Output:
# Phase 1: 57 tests
# Phase 2: 22 tests
# Phase 3: 33 tests
# Integration: 60 tests
# Total: 172 tests
```

## Load Testing

### HPA Load Testing

Test auto-scaling behavior:

```bash
# Install hey
go install github.com/rakyll/hey@latest

# Run load test
./scripts/k8s/load-test-hpa.sh ant-staging 300
```

Load test phases:
1. Warm-up: 30s, 10 concurrent
2. Ramp-up: 60s, 50 concurrent
3. Peak load: 300s, 100 concurrent
4. Cool-down: Monitor scale-down

### Performance Benchmarks

Expected performance metrics:
- Response time: < 100ms (p95)
- Throughput: > 1000 req/s
- Error rate: < 0.1%
- CPU usage: < 70% average

## Test Automation

### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: pytest tests/unit/
        language: system
        pass_filenames: false
      - id: k8s-validate
        name: k8s-validate
        entry: ./scripts/k8s/validate-all.sh
        language: system
        pass_filenames: false
```

### CI/CD Pipeline

```yaml
# .github/workflows/test.yml
name: Test Suite

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-test.txt
      - name: Run unit tests
        run: pytest tests/unit/ --cov=app
      
  k8s-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Install tools
        run: |
          curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
          chmod +x kubectl
          sudo mv kubectl /usr/local/bin/
      - name: Run K8s validation
        run: ./scripts/k8s/validate-all.sh
```

## Test Data Management

### Fixtures

Standard test fixtures:

```python
# tests/conftest.py
import pytest
from app import create_app

@pytest.fixture
def app():
    app = create_app('testing')
    return app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def test_firmware():
    return {
        'content': b'test firmware binary data',
        'filename': 'test-v1.0.0.bin',
        'version': '1.0.0',
        'device_type': 'test-device'
    }
```

### Mock Data

MinIO mock for unit tests:

```python
@pytest.fixture
def mock_storage():
    with patch('app.utils.storage.Minio') as mock:
        yield mock
```

## Test Environment Setup

### Local Testing

```bash
# Set up test environment
export FLASK_ENV=testing
export API_KEYS=test-key-1,test-key-2
export STORAGE_ENDPOINT=localhost:9000
export STORAGE_ACCESS_KEY=minioadmin
export STORAGE_SECRET_KEY=minioadmin

# Run application for testing
python run.py
```

### Docker Compose Testing

```yaml
# docker-compose.test.yml
version: '3.8'
services:
  app:
    build: .
    environment:
      - FLASK_ENV=testing
      - API_KEYS=test-key
      - STORAGE_ENDPOINT=minio:9000
    depends_on:
      - minio
  
  minio:
    image: minio/minio
    command: server /data
    environment:
      - MINIO_ROOT_USER=minioadmin
      - MINIO_ROOT_PASSWORD=minioadmin
```

## Testing Best Practices

### 1. Test Naming

- Use descriptive test names
- Follow pattern: `test_<what>_<condition>_<expected>`
- Example: `test_upload_firmware_invalid_type_returns_400`

### 2. Test Isolation

- Each test should be independent
- Use fixtures for setup/teardown
- Mock external dependencies

### 3. Test Coverage

- Critical paths: 100% coverage
- Business logic: > 90% coverage
- Overall target: > 80% coverage

### 4. Performance

- Keep unit tests fast (< 1s each)
- Use marks for slow tests
- Run integration tests separately

### 5. Documentation

- Document complex test scenarios
- Include examples in docstrings
- Maintain test data documentation

## Troubleshooting Tests

### Common Issues

1. **Import Errors**
   ```bash
   # Ensure PYTHONPATH includes project root
   export PYTHONPATH="${PYTHONPATH}:$(pwd)"
   ```

2. **MinIO Connection**
   ```bash
   # Check MinIO is running
   docker ps | grep minio
   nc -zv localhost 9000
   ```

3. **Kubernetes Tests Failing**
   ```bash
   # Ensure kubectl is configured
   kubectl version
   kubectl cluster-info
   ```

### Debug Mode

Run tests with verbose output:

```bash
# Python tests
pytest -vvs tests/

# Kubernetes tests
bash -x ./scripts/k8s/test-phase1-application.sh
```

## Continuous Improvement

### Metrics to Track

- Test execution time
- Test coverage percentage
- Test failure rate
- Flaky test identification

### Regular Reviews

- Weekly: Review test failures
- Monthly: Update test coverage
- Quarterly: Refactor test suite