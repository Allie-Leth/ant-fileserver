# ANT Fileserver Documentation

## Overview

The ANT Fileserver is a Flask-based API service designed to manage firmware files with secure storage in MinIO. It provides a RESTful API for firmware operations and is deployed on Kubernetes with production-ready features including auto-scaling, high availability, and monitoring.

## Documentation Index

### 1. [Application Architecture](./APPLICATION_ARCHITECTURE.md)
- Flask application structure
- Blueprint organization
- Configuration management
- Security implementation
- Health check endpoints

### 2. [API Reference](./API_REFERENCE.md)
- Complete API documentation
- Endpoint specifications
- Request/response formats
- Authentication details
- Error handling

### 3. [Kubernetes Infrastructure](./KUBERNETES_INFRASTRUCTURE.md)
- Manifest organization
- Base configuration
- Environment overlays
- Security policies
- Production features

### 4. [Deployment Guide](./DEPLOYMENT_GUIDE.md)
- Prerequisites
- Local development
- Staging deployment
- Production deployment
- GitOps workflow

### 5. [Testing Documentation](./TESTING_GUIDE.md)
- Unit testing
- Integration testing
- Kubernetes validation
- Load testing
- Test automation

### 6. [Operations Guide](./OPERATIONS_GUIDE.md)
- Monitoring setup
- Metrics and alerts
- Troubleshooting
- Scaling strategies
- Maintenance procedures

### 7. [Development Guide](./DEVELOPMENT_GUIDE.md)
- Local setup
- Code standards
- Contributing guidelines
- CI/CD pipeline
- Best practices

### 8. [Security Documentation](./SECURITY.md)
- Security policies
- Network policies
- RBAC configuration
- Secret management
- Compliance features

## Quick Start

### Local Development
```bash
# Clone repository
git clone https://github.com/yourusername/ant-fileserver.git
cd ant-fileserver

# Install dependencies
pip install -r requirements.txt

# Run locally
python run.py
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

## Project Structure

```
ant-fileserver/
├── app/                    # Flask application
│   ├── __init__.py        # App factory
│   ├── config.py          # Configuration
│   ├── models.py          # Data models
│   ├── blueprints/        # API blueprints
│   │   ├── firmware.py    # Firmware endpoints
│   │   └── health.py      # Health checks
│   └── utils/             # Utilities
│       ├── auth.py        # Authentication
│       ├── storage.py     # MinIO client
│       └── validators.py  # Input validation
├── k8s/                   # Kubernetes manifests
│   └── app/
│       ├── base/          # Base configuration
│       └── overlays/      # Environment configs
├── scripts/               # Automation scripts
│   └── k8s/              # Kubernetes scripts
├── tests/                 # Test suites
├── docs/                  # Documentation
└── dev/                   # Development artifacts
```

## Key Features

### Application Features
- RESTful API for firmware management
- MinIO object storage integration
- API key authentication
- Health and readiness endpoints
- Structured logging
- Error handling

### Infrastructure Features
- **High Availability**: Multi-replica deployments with PodDisruptionBudgets
- **Auto-scaling**: HorizontalPodAutoscaler based on CPU/memory
- **Security**: NetworkPolicies, Pod Security Standards, RBAC
- **Monitoring**: Prometheus metrics, ServiceMonitor integration
- **Load Balancing**: Anti-affinity rules for pod distribution
- **GitOps Ready**: Kustomize-based configuration management

## Technology Stack

- **Application**: Python 3.11, Flask 3.0
- **Storage**: MinIO Object Storage
- **Container**: Docker, OCI-compliant images
- **Orchestration**: Kubernetes 1.28+
- **Configuration**: Kustomize
- **Monitoring**: Prometheus, Grafana
- **Ingress**: NGINX Ingress Controller
- **TLS**: cert-manager with Let's Encrypt

## Support

For issues, questions, or contributions:
- Create an issue in the repository
- Check existing documentation
- Review the troubleshooting guide