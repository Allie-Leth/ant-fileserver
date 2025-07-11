# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a Flask-based REST API for firmware file management using MinIO S3-compatible storage. The repository contains:

- **Application**: Flask REST API with JWT authentication and role-based access control
- **Storage Integration**: MinIO S3-compatible backend for firmware file storage
- **Testing Framework**: Comprehensive unit, integration, and API test suites
- **Containerization**: Docker multi-stage builds for production deployment
- **Kubernetes Deployment**: Kustomize-based configuration management

## Key Technologies

- **Framework**: Flask 3.1+ with blueprints for modular API design
- **Authentication**: Flask-JWT-Extended with API key and JWT token support
- **Storage**: MinIO S3-compatible object storage via boto3
- **Configuration**: Environment-driven configuration with validation
- **Testing**: pytest with coverage reporting (pytest-cov)
- **Linting**: Ruff for fast Python code quality and formatting
- **Containerization**: Docker with Python 3.12 slim base image
- **Deployment**: Kubernetes with Kustomize overlays for environment management

## Common Commands

### Development and Testing
```bash
# Set up development environment
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run development server
python -m flask run --debug

# Run all tests with coverage
pytest tests/ --cov=app --cov-report=html

# Run specific test suites
pytest tests/unit/          # Unit tests only
pytest tests/integration/   # Integration tests (requires MinIO)
pytest tests/api/           # API endpoint tests
```

### Code Quality and Linting
```bash
# Check code quality with ruff
ruff check app/ tests/

# Format code with ruff
ruff format app/ tests/

# Fix auto-fixable issues
ruff check app/ tests/ --fix

# Run all quality checks
ruff check app/ tests/ && ruff format --check app/ tests/
```

### Container Operations
```bash
# Build container image
docker build -t ant-fileserver:latest .

# Run container locally
docker run -p 5000:5000 \
  -e STORAGE_ENDPOINT=http://localhost:9000 \
  -e STORAGE_BUCKET=firmware \
  -e JWT_SECRET_KEY=dev-secret \
  ant-fileserver:latest

# Build and push to registry
docker build -t registry.example.com/ant-fileserver:v1.0.0 .
docker push registry.example.com/ant-fileserver:v1.0.0
```

### Kubernetes Deployment
```bash
# Validate Kubernetes manifests
kustomize build k8s/app/overlays/prod | kubeconform -strict

# Preview deployment changes
kubectl diff -f <(kustomize build k8s/app/overlays/prod)

# Apply production deployment
kubectl apply -f <(kustomize build k8s/app/overlays/prod)

# Check deployment status
kubectl get pods -l app=ant-fileserver
kubectl logs deployment/ant-fileserver --follow
```

### API Testing
```bash
# Test authentication endpoint
curl -X POST http://localhost:5000/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"api_key": "dev-key"}'

# Test firmware upload (requires JWT token)
curl -X POST http://localhost:5000/api/v1/firmware/upload \
  -H "Authorization: Bearer <jwt-token>" \
  -F "file=@firmware.bin"

# List firmware files
curl -H "X-API-Key: dev-key" \
  http://localhost:5000/api/v1/firmware/files
```

## Directory Structure

```
ant-fileserver/
├── app/                        # Flask application code
│   ├── __init__.py            # Application factory
│   ├── config.py              # Configuration management
│   ├── models.py              # Data models and schemas
│   ├── extensions.py          # Flask extensions setup
│   ├── errors.py              # Error handling
│   └── blueprints/            # API route blueprints
│       ├── auth/              # Authentication endpoints
│       │   └── routes.py      # JWT token generation
│       └── firmware/          # Firmware management
│           ├── routes.py      # API endpoints
│           ├── schema.py      # Request/response schemas
│           └── service.py     # Business logic and storage
├── k8s/                       # Kubernetes deployment
│   └── app/
│       ├── base/              # Base Kubernetes resources
│       │   ├── deployment.yaml
│       │   ├── service.yaml
│       │   └── kustomization.yaml
│       └── overlays/          # Environment-specific configs
│           ├── dev/           # Development environment
│           └── prod/          # Production environment
├── tests/                     # Test suites
│   ├── conftest.py           # pytest fixtures
│   ├── unit/                 # Unit tests
│   ├── integration/          # Integration tests with MinIO
│   └── api/                  # API endpoint tests
├── scripts/                   # Development scripts
│   └── dev-integration.sh    # Integration test helper
├── requirements.txt           # Production dependencies
├── requirements-dev.txt       # Development dependencies
├── pyproject.toml            # Project configuration (ruff, black)
├── pytest.ini               # pytest configuration
└── Dockerfile                # Container build definition
```

## Architecture Notes

### Application Structure
- **Factory Pattern**: Flask app created via `create_app()` function in `app/__init__.py`
- **Blueprint Organization**: API routes organized by functionality (auth, firmware)
- **Service Layer**: Business logic separated from route handlers in service modules
- **Configuration Management**: Environment-driven config with validation in `config.py`

### Authentication Model
- **API Keys**: Static keys with role-based permissions (`API_KEY_ROLES` environment variable)
- **JWT Tokens**: Short-lived tokens generated from valid API keys
- **Role-Based Access**: Admin and uploader roles with different endpoint permissions
- **Security**: Rate limiting and CORS protection enabled

### Storage Strategy
- **MinIO Integration**: S3-compatible object storage for firmware files
- **Boto3 Client**: AWS SDK for Python used for storage operations
- **Environment Configuration**: Storage credentials and settings via environment variables
- **Error Handling**: Comprehensive error handling for storage operations

## Important Patterns

### Complex Task Documentation Standard
For any complex development task (migrations, major refactoring, multi-component changes), **ALWAYS** create a dedicated `{task_name}_GUIDE.md` file that includes:
- Comprehensive analysis of current state
- Step-by-step implementation plan
- Validation against existing infrastructure
- Testing procedures and requirements
- Rollback procedures
- Post-completion cleanup steps

Examples:
- `MIGRATION_GUIDE.md` - For GitLab to GitHub migration
- `REFACTORING_GUIDE.md` - For major code restructuring
- `DEPLOYMENT_GUIDE.md` - For production deployment changes

### When Adding New API Endpoints
1. Define request/response schemas in appropriate `schema.py` file
2. Implement business logic in service layer (`service.py`)
3. Create route handlers in blueprint `routes.py` file
4. Add authentication and authorization decorators as needed
5. Write comprehensive tests (unit, integration, API)

### When Modifying Storage Logic
1. Update service layer methods in `firmware/service.py`
2. Ensure proper error handling and logging
3. Update integration tests in `tests/integration/`
4. Test with actual MinIO instance using development scripts
5. Validate changes don't break existing API contracts

### When Updating Kubernetes Configuration
1. Modify base resources in `k8s/app/base/` if changes apply to all environments
2. Use overlay patches in `k8s/app/overlays/` for environment-specific changes
3. Validate with `kubeconform` before applying
4. Test deployment in development environment first
5. Follow blue-green deployment patterns for production updates

### Configuration Management
- Use environment variables for all runtime configuration
- Validate required configuration at application startup
- Use `config.py` for centralized configuration loading and validation
- Never commit secrets or credentials to the repository
- Use Kubernetes secrets for sensitive configuration in production

## Testing Strategy

### Unit Tests (`tests/unit/`)
- Test individual functions and classes in isolation
- Mock external dependencies (MinIO, JWT, etc.)
- Focus on business logic and edge cases
- Aim for >90% code coverage

### Integration Tests (`tests/integration/`)
- Test interactions with real MinIO instance
- Use docker-compose for test infrastructure
- Validate storage operations end-to-end
- Test configuration loading and validation

### API Tests (`tests/api/`)
- Test complete HTTP request/response cycles
- Validate authentication and authorization
- Test error handling and edge cases
- Use realistic test data and scenarios

### Test Execution
```bash
# Run all tests with coverage
pytest tests/ --cov=app --cov-report=html

# Run tests with verbose output
pytest tests/ -v

# Run specific test files
pytest tests/unit/test_firmware_services.py -v

# Run tests matching pattern
pytest tests/ -k "test_upload" -v
```

## Security Best Practices

### Authentication and Authorization
- Always validate JWT tokens on protected endpoints
- Use role-based access control for different operations
- Implement rate limiting to prevent abuse
- Log authentication failures for security monitoring

### Storage Security
- Use environment variables for storage credentials
- Validate file uploads (type, size, content)
- Implement proper error handling without leaking information
- Use secure random generation for file IDs and tokens

### Configuration Security
- Never commit plaintext secrets to repository
- Use Kubernetes secrets for production credentials
- Validate all configuration values at startup
- Use secure defaults for all configuration options

## Deployment Best Practices

### Container Security
- Use non-root user in container (defined in Dockerfile)
- Use minimal base image (python:3.12-slim)
- Multi-stage builds to reduce image size
- Regular security scanning of base images

### Kubernetes Security
- Use security contexts for all containers
- Implement resource limits and requests
- Use network policies for traffic control
- Regular security updates for all components

### Monitoring and Logging
- Structured logging throughout application
- Monitor key metrics (response times, error rates)
- Set up alerting for critical failures
- Log security events and authentication attempts

## Git Best Practices

### Commit Standards
All commits must follow conventional commit format:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types:**
- `feat`: New feature or enhancement
- `fix`: Bug fix or correction
- `config`: Configuration changes
- `docs`: Documentation updates
- `refactor`: Code restructuring without functional changes
- `test`: Test additions or modifications
- `ops`: Operational/infrastructure changes

**Scopes:**
- `api`: API endpoint changes
- `auth`: Authentication/authorization changes
- `storage`: Storage-related changes
- `k8s`: Kubernetes configuration changes
- `tests`: Test-related changes
- `docker`: Container-related changes

#### Examples
```bash
# Good commit messages
feat(api): add firmware metadata endpoint with version tracking
fix(auth): resolve JWT token expiration validation issue
config(k8s): update resource limits for production deployment
test(integration): add MinIO connection retry logic tests

# Bad commit messages
Update stuff
Fix bugs
Add new feature
```

#### Claude Code Commit Format (MANDATORY)
When using Claude Code, ALL commits must use this exact format:
```bash
git commit -m "$(cat <<'EOF'
<type>(<scope>): <description>

[detailed description]

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

### Pre-Commit Requirements

Before committing changes, ALWAYS:

1. **Run all tests**:
   ```bash
   pytest tests/ --cov=app
   ```

2. **Check code quality**:
   ```bash
   ruff check app/ tests/
   ruff format --check app/ tests/
   ```

3. **Validate Kubernetes manifests**:
   ```bash
   kustomize build k8s/app/overlays/prod | kubeconform -strict
   ```

4. **Check for secrets or sensitive data**:
   ```bash
   grep -r "password\|token\|key\|secret" --include="*.py" --exclude-dir=tests app/
   ```

### Branch Strategy

- **main**: Production-ready code only
- **develop**: Integration branch for new features
- **feature/***: Feature development branches
- **hotfix/***: Critical bug fixes for production

All changes must go through pull request review before merging to main.

### Change Management Process

1. **Create Feature Branch**: Start from develop branch
2. **Implement Changes**: Follow coding standards and patterns
3. **Write Tests**: Ensure comprehensive test coverage
4. **Validate Quality**: Run all linting and testing tools
5. **Update Documentation**: Update relevant documentation files
6. **Submit Pull Request**: Include detailed description and testing notes

## Emergency Procedures

### Quick Rollback
```bash
# Kubernetes rollback
kubectl rollout undo deployment/ant-fileserver

# Docker container restart
kubectl delete pods -l app=ant-fileserver

# Scale down for maintenance
kubectl scale deployment ant-fileserver --replicas=0
```

### Debug Common Issues
```bash
# Check application logs
kubectl logs deployment/ant-fileserver --tail=100

# Test storage connectivity
kubectl exec deployment/ant-fileserver -- python -c "
from app.blueprints.firmware.service import FirmwareService
svc = FirmwareService('http://minio:9000', 'firmware', 'key', 'secret', 'us-east-1')
print('Storage test:', svc.list_files())
"

# Validate configuration
kubectl describe configmap ant-fileserver-config
kubectl describe secret ant-fileserver-secrets
```

### Security Incident Response
1. Immediately revoke compromised API keys or JWT secrets
2. Update configuration with new credentials
3. Restart all application instances
4. Review logs for unauthorized access
5. Update sealed secrets with new credentials

## Development Workflow

The repository supports local development with comprehensive testing:

1. **Local Setup**: Use virtual environment with all development dependencies
2. **Code Quality**: Pre-commit hooks enforce code standards
3. **Testing**: Multiple test suites for different aspects of the application
4. **Integration**: Scripts for testing with real MinIO instances
5. **Deployment**: Kustomize-based Kubernetes deployment with environment overlays

For optimal development experience, always:
- Use virtual environment for dependency isolation
- Run tests frequently during development
- Use linting tools integrated into your editor
- Test API endpoints manually with provided curl examples
- Validate Kubernetes changes before applying to cluster