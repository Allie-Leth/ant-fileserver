# ANT Fileserver Development Makefile

.PHONY: help install dev test lint format check clean pre-push

# Default target
help:  ## Show this help message
	@echo "ANT Fileserver Development Commands"
	@echo "=================================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies
	pip install -r requirements.txt -r requirements-dev.txt

dev: install  ## Set up development environment
	@echo "Setting up development environment..."
	@echo "Installing pre-commit hooks..."
	pre-commit install
	@echo "Development environment ready!"

test:  ## Run all tests
	pytest tests/ -v

test-unit:  ## Run unit tests only
	pytest tests/unit/ -v

test-api:  ## Run API tests only
	pytest tests/api/ -v

test-integration:  ## Run integration tests only
	pytest tests/integration/ -v

test-k8s:  ## Run Kubernetes validation tests
	pytest tests/test_k8s_validation.py -v -m "not slow"

test-k8s-full:  ## Run all Kubernetes tests including slow ones
	pytest tests/test_k8s_validation.py -v

lint:  ## Run linting
	ruff check app/ tests/
	ruff format --check app/ tests/

lint-fix:  ## Run linting with auto-fix
	ruff check app/ tests/ --fix
	ruff format app/ tests/
	isort app/ tests/

format: lint-fix  ## Format code (alias for lint-fix)

type-check:  ## Run type checking
	mypy app/

security:  ## Run security checks
	safety check

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
	python run.py

docker-build:  ## Build Docker image
	docker build -t ant-fileserver:local .

docker-run:  ## Run Docker container locally
	docker run -p 8000:8000 ant-fileserver:local

# Development workflow shortcuts
quick: lint-fix test-unit  ## Quick development check (format + unit tests)
full: clean install check test validate-k8s  ## Full validation (everything)