# ANT Fileserver

A secure, scalable firmware management API service built with Flask and designed for Kubernetes deployment.

## Features

- **RESTful API** for firmware file management
- **MinIO Integration** for object storage
- **API Key Authentication** for secure access
- **Kubernetes Ready** with production-grade features:
  - Auto-scaling (HPA)
  - High availability (PDB)
  - Network security (NetworkPolicies)
  - Monitoring (Prometheus metrics)
  - Load balancing (Anti-affinity rules)

## Quick Start

### Local Development

```bash
# Clone repository
git clone https://github.com/Allie-Leth/ant-fileserver.git
cd ant-fileserver

# Install dependencies
make install

# Set up development environment
make dev

# Run tests
make test

# Start application
make run
```

### Kubernetes Deployment

```bash
# Deploy to local environment
kubectl apply -k k8s/app/overlays/local/

# Deploy to staging
kubectl apply -k k8s/app/overlays/staging/

# Deploy to production
kubectl apply -k k8s/app/overlays/prod/
```

## API Endpoints

- `GET /health` - Health check
- `GET /ready` - Readiness check
- `GET /api/v1/firmware` - List firmware files
- `GET /api/v1/firmware/<id>` - Get firmware details
- `GET /api/v1/firmware/<id>/download` - Download firmware
- `POST /api/v1/firmware` - Upload firmware
- `DELETE /api/v1/firmware/<id>` - Delete firmware

## Development

### Available Commands

```bash
make help           # Show all available commands
make dev            # Set up development environment
make test           # Run all tests
make lint           # Run linting
make format         # Format code
make pre-push       # Run pre-push validation
make clean          # Clean up generated files
```

### Pre-Push Validation

Before pushing changes, run:

```bash
make pre-push
```

This runs all CI checks locally including:
- Code formatting and linting
- Unit and API tests
- Kubernetes validation
- Security checks

## Documentation

Comprehensive documentation is available in the `docs/` directory:

- [Application Architecture](docs/APPLICATION_ARCHITECTURE.md)
- [API Reference](docs/API_REFERENCE.md)
- [Kubernetes Infrastructure](docs/KUBERNETES_INFRASTRUCTURE.md)
- [Deployment Guide](docs/DEPLOYMENT_GUIDE.md)
- [Testing Guide](docs/TESTING_GUIDE.md)
- [Operations Guide](docs/OPERATIONS_GUIDE.md)
- [Development Guide](docs/DEVELOPMENT_GUIDE.md)
- [Security Documentation](docs/SECURITY.md)

## Technology Stack

- **Application**: Python 3.11, Flask 3.0
- **Storage**: MinIO Object Storage
- **Container**: Docker, OCI-compliant images
- **Orchestration**: Kubernetes 1.28+
- **Configuration**: Kustomize
- **Monitoring**: Prometheus, Grafana
- **Ingress**: NGINX Ingress Controller
- **TLS**: cert-manager with Let's Encrypt

## License

MIT License - see LICENSE file for details.