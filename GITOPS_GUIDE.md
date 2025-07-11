# Ant Firmware API - GitOps Implementation Guide

> **Auto-generated documentation** - Do not edit manually. 
> Run documentation update commands as needed.
> 
> *Last updated: 2025-07-11*

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Component Catalog](#component-catalog)
3. [Deployment Patterns](#deployment-patterns)
4. [Security Patterns](#security-patterns)
5. [Operations Guide](#operations-guide)
6. [Decision Records](#decision-records)
7. [Quick Reference](#quick-reference)

---

## Architecture Overview

### Technology Stack
- **Application**: Flask-based REST API for firmware file management
- **Storage**: MinIO S3-compatible object storage
- **Authentication**: JWT-based API authentication with role-based access
- **Containerization**: Docker with multi-stage builds
- **Deployment**: Kubernetes with Kustomize overlays
- **Testing**: pytest with unit, integration, and API tests
- **Linting**: Ruff for Python code quality

### Component Categories

#### Core Application Components
- **Flask API**: REST endpoints for firmware upload/download/management
- **Authentication Service**: JWT token validation and role-based access control
- **Storage Service**: MinIO integration for firmware file storage
- **Configuration Management**: Environment-based configuration loading

#### Infrastructure Components  
- **Kubernetes Manifests**: Deployment, service, and configuration resources
- **Kustomize Overlays**: Environment-specific configurations (dev/prod)
- **Docker Container**: Multi-stage build with Python 3.12 runtime

### Environment Strategy
- **Development**: Local development with environment variables
- **Production**: Kubernetes deployment with sealed secrets
- **Testing**: Isolated test environment with mocked storage

---

## Component Catalog

### API Application (`ant-fileserver/`)
- **Type**: Flask REST API
- **Version**: Python 3.12
- **Dependencies**: Flask, Flask-JWT-Extended, boto3, marshmallow
- **Configuration**: Environment-driven configuration with validation
- **Storage**: MinIO S3-compatible backend
- **Authentication**: API key and JWT token based

### Kubernetes Infrastructure (`k8s/`)
- **Base Manifests**: Core deployment, service, and configuration
- **Dev Overlay**: Development-specific configurations
- **Production Overlay**: Production deployment settings
- **Kustomize**: Configuration management and patching

### Testing Framework (`tests/`)
- **Unit Tests**: Component isolation testing
- **Integration Tests**: MinIO storage integration
- **API Tests**: End-to-end API validation
- **Coverage**: Code coverage reporting with pytest-cov

---

## Deployment Patterns

### Standard Project Structure
```
ant-fileserver/
├── app/                    # Flask application code
│   ├── blueprints/        # API route blueprints
│   │   ├── auth/          # Authentication endpoints
│   │   └── firmware/      # Firmware management endpoints
│   ├── config.py          # Configuration management
│   ├── models.py          # Data models and schemas
│   └── extensions.py      # Flask extensions setup
├── k8s/                   # Kubernetes manifests
│   └── app/
│       ├── base/          # Base Kubernetes resources
│       └── overlays/      # Environment-specific configs
│           ├── dev/
│           └── prod/
├── tests/                 # Test suites
│   ├── unit/              # Unit tests
│   ├── integration/       # Integration tests
│   └── api/               # API tests
├── requirements.txt       # Python dependencies
├── pyproject.toml         # Project configuration
└── Dockerfile             # Container build definition
```

### Kustomize Overlay Pattern
1. **Base**: Common Kubernetes resources shared across environments
2. **Dev Overlay**: Development-specific patches and configurations
3. **Prod Overlay**: Production deployment settings and scaling
4. **Patches**: Strategic merge patches for environment differences

### Deployment Commands
```bash
# Validate Kubernetes manifests
kustomize build k8s/app/overlays/prod | kubeconform -strict

# Preview changes
kubectl diff -f <(kustomize build k8s/app/overlays/prod)

# Apply deployment
kubectl apply -f <(kustomize build k8s/app/overlays/prod)

# Check deployment status
kubectl get pods -l app=ant-fileserver
kubectl logs deployment/ant-fileserver
```

---

## Security Patterns

### Authentication & Authorization
- **API Keys**: Static API keys with role-based permissions
- **JWT Tokens**: Short-lived tokens for session management
- **Role-Based Access**: Admin and uploader roles with different permissions
- **Rate Limiting**: Request rate limiting to prevent abuse

### Secret Management
- **Environment Variables**: Sensitive configuration via environment
- **Kubernetes Secrets**: Encrypted storage credentials and JWT keys
- **No Plaintext Secrets**: Never commit credentials to repository
- **Rotation Strategy**: Regular rotation of API keys and storage credentials

### Secret Creation Workflow
```bash
# Create Kubernetes secret for storage credentials
kubectl create secret generic ant-fileserver-storage \
  --from-literal=endpoint=https://minio.example.com \
  --from-literal=access-key-id=<access-key> \
  --from-literal=secret-access-key=<secret-key> \
  --from-literal=bucket=firmware-bucket \
  --dry-run=client -o yaml | \
kubeseal --scope cluster-wide -o yaml > sealed-storage-secret.yaml

# Create secret for JWT signing key
kubectl create secret generic ant-fileserver-jwt \
  --from-literal=secret-key=<generated-secret> \
  --dry-run=client -o yaml | \
kubeseal --scope cluster-wide -o yaml > sealed-jwt-secret.yaml
```

### Container Security
- **Non-root User**: Application runs as non-privileged user
- **Read-only Filesystem**: Container filesystem mounted read-only where possible
- **Minimal Base Image**: Python slim image for reduced attack surface
- **Security Scanning**: Regular container image vulnerability scanning

---

## Operations Guide

### Daily Operations
```bash
# Check application health
kubectl get pods -l app=ant-fileserver
kubectl logs deployment/ant-fileserver --tail=50

# Verify storage connectivity
kubectl exec deployment/ant-fileserver -- python -c "from app.blueprints.firmware.service import FirmwareService; print('Storage OK')"

# Check API endpoints
curl -H "X-API-Key: dev-key" https://api.example.com/api/v1/firmware/files
```

### Development Workflow
```bash
# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run tests
pytest tests/ --cov=app --cov-report=html

# Code quality checks
ruff check app/ tests/
ruff format --check app/ tests/

# Run development server
python -m flask run --debug
```

### GitHub Actions CI/CD
```bash
# Check workflow status
gh workflow list
gh run list --workflow=ci.yml

# View specific workflow run
gh run view <run-id> --log

# Trigger workflow manually (if configured)
gh workflow run ci.yml

# Check container registry
gh api /user/packages?package_type=container
```

### Production Monitoring
```bash
# Resource utilization
kubectl top pods -l app=ant-fileserver
kubectl describe pod <pod-name>

# Application metrics
kubectl logs deployment/ant-fileserver | grep -E "(ERROR|WARNING)"

# Storage health
# MinIO health checks would be integrated here
```

### Emergency Procedures
```bash
# Quick rollback via Kubernetes
kubectl rollout undo deployment/ant-fileserver

# Scale down for maintenance
kubectl scale deployment ant-fileserver --replicas=0

# Force pod restart
kubectl delete pods -l app=ant-fileserver
```

---

## Decision Records

### DR-001: Flask Framework Selection
**Date**: 2025-07-11  
**Status**: Accepted  
**Context**: Need lightweight, flexible web framework for firmware API  
**Decision**: Use Flask with blueprints for modular API design  
**Consequences**: Simple to develop and test, extensive ecosystem, good for microservices

### DR-002: MinIO for Object Storage
**Date**: 2025-07-11  
**Status**: Accepted  
**Context**: Need S3-compatible storage for firmware files  
**Decision**: Use MinIO as S3-compatible backend  
**Consequences**: Self-hosted option, S3 API compatibility, cost-effective

### DR-003: JWT Authentication
**Date**: 2025-07-11  
**Status**: Accepted  
**Context**: Need stateless authentication for API  
**Decision**: Use JWT tokens with API key bootstrap  
**Consequences**: Stateless authentication, scalable, industry standard

### DR-004: Ruff for Python Linting
**Date**: 2025-07-11  
**Status**: Accepted  
**Context**: Need fast, comprehensive Python linting  
**Decision**: Use Ruff instead of multiple tools (flake8, isort, etc.)  
**Consequences**: Single tool, faster execution, comprehensive rule set

---

## Quick Reference

### Common Commands

#### Development
```bash
# Start development server
python -m flask run --debug

# Run all tests
pytest tests/ --cov=app

# Code formatting
black app/ tests/
ruff check app/ tests/ --fix

# Build container locally
docker build -t ant-fileserver:latest .
```

#### Deployment
```bash
# Apply Kubernetes configuration
kubectl apply -f <(kustomize build k8s/app/overlays/prod)

# Check deployment
kubectl get deployment ant-fileserver
kubectl get pods -l app=ant-fileserver

# View logs
kubectl logs deployment/ant-fileserver --follow
```

#### Testing
```bash
# Unit tests only
pytest tests/unit/

# Integration tests (requires MinIO)
pytest tests/integration/

# API tests
pytest tests/api/

# Coverage report
pytest tests/ --cov=app --cov-report=html
```

### Troubleshooting

#### Application Won't Start
1. Check environment variables: `kubectl describe pod <pod-name>`
2. Verify secrets are mounted: `kubectl get secrets`
3. Check storage connectivity: Review MinIO endpoint configuration
4. Review application logs: `kubectl logs deployment/ant-fileserver`

#### Authentication Issues
1. Verify JWT secret is properly configured
2. Check API key roles configuration: `API_KEY_ROLES` environment variable
3. Test token generation: Use `/api/v1/auth/token` endpoint
4. Validate token format and expiration

#### Storage Problems
1. Test MinIO connectivity: Check endpoint URL and credentials
2. Verify bucket exists and is accessible
3. Check network policies and firewall rules
4. Review storage service logs

#### Performance Issues
1. Check resource limits: `kubectl describe pod <pod-name>`
2. Monitor memory and CPU usage: `kubectl top pods`
3. Review application metrics and logs
4. Analyze storage I/O performance

### File Locations

#### Key Configuration Files
- **Application Config**: `app/config.py`
- **Kubernetes Base**: `k8s/app/base/`
- **Production Overlay**: `k8s/app/overlays/prod/`
- **Development Overlay**: `k8s/app/overlays/dev/`

#### Important Scripts
- **Development Integration**: `scripts/dev-integration.sh`
- **Container Build**: `Dockerfile`
- **Test Configuration**: `pytest.ini`

### Environment Variables

#### Required Configuration
- `STORAGE_ENDPOINT`: MinIO endpoint URL
- `STORAGE_BUCKET`: Storage bucket name
- `STORAGE_ACCESS_KEY_ID`: MinIO access key
- `STORAGE_SECRET_ACCESS_KEY`: MinIO secret key
- `JWT_SECRET_KEY`: JWT signing secret

#### Optional Configuration
- `STORAGE_REGION`: Storage region (default: us-east-1)
- `API_KEY_ROLES`: JSON mapping of API keys to roles
- `LOG_LEVEL`: Logging level (default: INFO)
- `DEBUG`: Enable debug mode (default: False)

---

*This guide is maintained alongside the project. Update as architecture or deployment patterns change.*