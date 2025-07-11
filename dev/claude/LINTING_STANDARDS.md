# Ant Firmware API - Linting Standards

This document establishes the definitive source of truth for all linting and code quality standards across the Ant Firmware API project.

## Overview

Consistent linting standards ensure:
- **Reliability**: Same results across local development and CI/CD
- **Quality**: Catch syntax errors and maintain code standards
- **Compatibility**: Consistent behavior across different environments
- **Maintainability**: Clear expectations for all contributors

## Python Linting

### Standard Tool: `ruff`

**Version**: `>= 0.1.0`
**Installation**: `pip install ruff`

### Configuration File: `pyproject.toml`

```toml
[tool.ruff]
line-length = 88
target-version = "py312"

[tool.ruff.lint]
select = [
  "F",   # Pyflakes
  "E",   # pycodestyle errors
  "B",   # flake8-bugbear
  "C4",  # flake8-comprehensions
  "I",   # isort
  "UP",  # pyupgrade
  "ARG", # flake8-unused-arguments
  "D",   # pydocstyle
  "PL"   # pylint
]
ignore = ["E501"]  # Line too long (handled by black)

[tool.ruff.lint.pydocstyle]
convention = "google"
```

### Code Formatting: `black`

**Version**: `>= 23.0.0`
**Configuration**:
```toml
[tool.black]
line-length = 88
target-version = ["py312"]
```

### Usage in Development

```bash
# Install tools
pip install ruff black

# Check code quality
ruff check app/ tests/

# Format code
black app/ tests/

# Fix auto-fixable issues
ruff check app/ tests/ --fix
```

## YAML Linting

### Standard Tool: `yamllint`

**Version**: `>= 1.35.0`
**Installation**: `pip install yamllint`

### Configuration File: `.yamllint.yml`

```yaml
extends: default
rules:
  # Syntax validation (REQUIRED)
  syntax: error
  
  # Style rules (WARNINGS - don't fail CI/CD)
  document-start: disable
  line-length:
    max: 120
    level: warning
  trailing-spaces:
    level: warning
  indentation:
    spaces: 2
    level: warning
  brackets:
    level: warning
  truthy:
    allowed-values: ['true', 'false', 'yes', 'no']
    level: warning
  comments:
    min-spaces-from-content: 1
    level: warning
  new-line-at-end-of-file:
    level: warning
```

### Usage in CI/CD

```bash
# Install yamllint
pip install yamllint

# Validate all YAML files
yamllint -f parsable .

# Check specific files
yamllint k8s/app/base/*.yaml
```

## Kubernetes Manifest Validation

### Standard Tools

1. **Schema Validation**: `kubeconform` >= 0.6.0
2. **Kustomize Build**: `kustomize` >= 5.0.0

### Configuration

```bash
# Kubeconform with strict validation
kubeconform -strict -ignore-missing-schemas -summary -verbose

# Kustomize validation with build
kustomize build k8s/app/overlays/prod --validate
```

### Validation Commands

```bash
# Validate base manifests
kustomize build k8s/app/base | kubeconform -strict

# Validate production overlay
kustomize build k8s/app/overlays/prod | kubeconform -strict

# Validate development overlay
kustomize build k8s/app/overlays/dev | kubeconform -strict
```

## Docker Linting

### Standard Tool: `hadolint`

**Version**: `>= 2.12.0`
**Installation**: `docker pull hadolint/hadolint`

### Configuration: `.hadolint.yaml`

```yaml
ignored:
  - DL3008  # Pin versions in apt-get install
  - DL3009  # Delete apt-get lists
failure-threshold: error
```

### Usage

```bash
# Lint Dockerfile
docker run --rm -i hadolint/hadolint < Dockerfile

# With configuration file
docker run --rm -i -v $(pwd)/.hadolint.yaml:/hadolint.yaml hadolint/hadolint --config /hadolint.yaml < Dockerfile
```

## Flask/API Specific Standards

### Import Organization

Use `ruff` with isort rules for consistent imports:

```python
# Standard library imports
import json
import logging
from typing import Any, Dict

# Third-party imports
from flask import Flask, request, jsonify
from marshmallow import Schema, fields

# Local application imports
from app.config import get_config
from app.models import FirmwareModel
```

### API Response Standards

```python
# Consistent error response format
{
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Descriptive error message",
        "details": {}
    }
}

# Consistent success response format
{
    "data": {
        "firmware_id": "12345",
        "filename": "firmware.bin"
    },
    "meta": {
        "version": "v1",
        "timestamp": "2025-07-11T12:00:00Z"
    }
}
```

### Docstring Standards (Google Style)

```python
def upload_firmware(file_data: bytes, filename: str) -> Dict[str, Any]:
    """Upload firmware file to storage backend.
    
    Args:
        file_data: Binary data of the firmware file.
        filename: Original filename of the uploaded file.
        
    Returns:
        Dictionary containing upload result and metadata.
        
    Raises:
        ValidationError: If file validation fails.
        StorageError: If storage operation fails.
    """
```

## Pre-commit Configuration

### Configuration File: `.pre-commit-config.yaml`

```yaml
repos:
  - repo: https://github.com/charliermarsh/ruff-pre-commit
    rev: v0.1.8
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format

  - repo: https://github.com/adrienverge/yamllint.git
    rev: v1.35.1
    hooks:
      - id: yamllint
        args: [-c=.yamllint.yml]

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
```

### Installation and Usage

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run on all files
pre-commit run --all-files
```

## CI/CD Integration Standards

### Required Linting Steps

All CI/CD pipelines MUST include these validation steps:

1. **Python Code**: `ruff check` and `ruff format --check`
2. **YAML Syntax**: `yamllint` with exit code check
3. **Kubernetes Manifests**: `kubeconform` validation
4. **Docker**: `hadolint` validation

### GitHub Actions Integration

```yaml
name: Code Quality

on: [push, pull_request]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
          
      - name: Install dependencies
        run: |
          pip install ruff yamllint
          
      - name: Lint Python code
        run: |
          ruff check app/ tests/
          ruff format --check app/ tests/
          
      - name: Lint YAML files
        run: |
          yamllint -f parsable .
          
      - name: Validate Kubernetes manifests
        run: |
          # Install kubeconform and kustomize
          kustomize build k8s/app/overlays/prod | kubeconform -strict
          
      - name: Lint Dockerfile
        run: |
          docker run --rm -i hadolint/hadolint < Dockerfile
```

## Testing Standards

### Code Coverage Requirements

- **Minimum Coverage**: 80% line coverage
- **Critical Path Coverage**: 95%+ for authentication and storage components
- **Test Types**: Unit, integration, and API tests

### Test File Organization

```python
# test_firmware_service.py
"""Tests for firmware service module.

This module tests the FirmwareService class functionality including
upload, download, and metadata operations.
"""

import pytest
from unittest.mock import Mock, patch

from app.blueprints.firmware.service import FirmwareService


class TestFirmwareService:
    """Test cases for FirmwareService class."""
    
    def test_upload_success(self, mock_storage):
        """Test successful firmware upload."""
        # Test implementation
```

## Environment Consistency

### Development Environment

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install development dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Set up pre-commit hooks
pre-commit install
```

### Docker Environment

Use consistent base images and tool versions:

```dockerfile
# Multi-stage build for linting
FROM python:3.12-slim as linter
COPY requirements-dev.txt .
RUN pip install -r requirements-dev.txt
COPY . .
RUN ruff check app/ tests/ && \
    ruff format --check app/ tests/
```

## Error Handling Standards

### Exit Codes

- **0**: All linting passed
- **1**: Syntax errors or critical issues found (fail CI/CD)
- **2**: Style warnings only (log but proceed)

### Error Output Format

Use consistent, parsable output formats:

```bash
# Good: Parsable format for CI/CD
ruff check app/ --format=json
yamllint -f parsable .

# Good: Human-readable for development
ruff check app/
yamllint .
```

## Component-Specific Standards

### Flask Application (`app/`)

- **Import Order**: Standard, third-party, local imports
- **Function Length**: Maximum 50 lines per function
- **Class Complexity**: Maximum 10 methods per class
- **Docstrings**: Required for all public functions and classes

### Kubernetes Manifests (`k8s/`)

- **Resource Naming**: Use kebab-case with app prefix
- **Label Standards**: Include app, version, and component labels
- **Annotation Format**: Use standard Kubernetes annotations
- **Security Context**: Always specify security context for containers

### Test Files (`tests/`)

- **Naming Convention**: `test_*.py` for test files
- **Class Organization**: Group tests by functionality
- **Mock Usage**: Use pytest fixtures for consistent mocking
- **Assertion Style**: Use descriptive assertion messages

## Maintenance

This document and associated configurations should be:

1. **Reviewed quarterly** for tool updates and best practices
2. **Updated immediately** when CI/CD failures indicate linting issues
3. **Versioned** with semantic versioning for breaking changes
4. **Tested** in isolated environments before project-wide adoption

## Implementation Checklist

- [ ] Create `.yamllint.yml` in project root
- [ ] Update `pyproject.toml` with ruff configuration
- [ ] Add `.pre-commit-config.yaml` configuration
- [ ] Install and configure pre-commit hooks
- [ ] Update CI/CD pipeline with linting steps
- [ ] Document component-specific linting requirements
- [ ] Train team on new standards and tools

---

**Last Updated**: 2025-07-11  
**Version**: 1.0.0  
**Maintained By**: Development Team