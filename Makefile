# ANT Fileserver Development Makefile

.PHONY: help install dev test lint format check clean pre-push

# Use virtual environment if available
VENV := $(if $(wildcard .venv/bin/python),.venv/bin/,)
PYTHON := $(VENV)python
PIP := $(VENV)pip
PYTEST := $(VENV)pytest
RUFF := $(VENV)ruff

# Default target
help:  ## Show this help message
	@echo "ANT Fileserver Development Commands"
	@echo "=================================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies
	$(PIP) install -r requirements.txt -r requirements-dev.txt

dev: install  ## Set up development environment
	@echo "Setting up development environment..."
	@echo "Installing pre-commit hooks..."
	$(VENV)pre-commit install
	@echo "Development environment ready!"

test:  ## Run all tests
	$(PYTEST) tests/ -v

test-unit:  ## Run unit tests only
	$(PYTEST) tests/unit/ -v

test-api:  ## Run API tests only
	$(PYTEST) tests/api/ -v

test-integration:  ## Run integration tests only
	$(PYTEST) tests/integration/ -v

test-k8s:  ## Run Kubernetes validation tests
	$(PYTEST) tests/test_k8s_validation.py -v -m "not slow"

test-k8s-full:  ## Run all Kubernetes tests including slow ones
	$(PYTEST) tests/test_k8s_validation.py -v

lint:  ## Run linting
	$(RUFF) check app/ tests/
	$(RUFF) format --check app/ tests/

lint-fix:  ## Run linting with auto-fix
	$(RUFF) check app/ tests/ --fix
	$(RUFF) format app/ tests/
	$(VENV)isort app/ tests/

format: lint-fix  ## Format code (alias for lint-fix)

type-check:  ## Run type checking
	$(VENV)mypy app/

security:  ## Run security checks
	$(VENV)safety check

check: lint type-check security  ## Run all code quality checks

validate-k8s:  ## Validate Kubernetes manifests
	./scripts/k8s/validate-all.sh

pre-push:  ## Run pre-push validation
	./scripts/pre-push.sh

clean:  ## Clean up generated files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/ .coverage

run:  ## Run the application locally
	$(PYTHON) run.py

docker-build:  ## Build Docker image
	docker build -t ant-fileserver:local .

docker-run:  ## Run Docker container locally
	docker run -p 8000:8000 ant-fileserver:local

# Development workflow shortcuts
quick: lint-fix test-unit  ## Quick development check (format + unit tests)
full: clean install check test validate-k8s  ## Full validation (everything)