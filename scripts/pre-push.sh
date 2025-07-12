#!/usr/bin/env bash
set -euo pipefail

# Pre-push validation script
# Runs all checks locally to ensure CI pipeline will pass

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo -e "${RED}Error: Not in a git repository${NC}"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

log() {
    echo -e "${BLUE}[$(date +'%H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Track failures
FAILED_CHECKS=()

run_check() {
    local check_name="$1"
    local check_cmd="$2"
    
    log "Running: $check_name"
    if eval "$check_cmd"; then
        success "$check_name passed"
        return 0
    else
        error "$check_name failed"
        FAILED_CHECKS+=("$check_name")
        return 1
    fi
}

# Header
echo -e "${BLUE}=== Pre-Push Validation ===${NC}"
echo -e "This script runs all CI checks locally"
echo

# 1. Check Python environment
log "Checking Python environment..."
if [ -f ".venv/bin/python" ]; then
    PYTHON=".venv/bin/python"
    PIP=".venv/bin/pip"
    # Add venv to PATH temporarily
    export PATH=".venv/bin:$PATH"
    success "Using virtual environment"
else
    PYTHON="python3"
    PIP="pip3"
    warning "Not using virtual environment"
fi

# 2. Install/upgrade dependencies
log "Checking dependencies..."
$PIP install -q --upgrade pip
$PIP install -q -r requirements.txt -r requirements-dev.txt
success "Dependencies installed"

# 3. Linting checks
echo
echo -e "${BLUE}=== Linting Phase ===${NC}"

# Ruff linting
run_check "Ruff check" \
    "ruff check app/ tests/ --fix" || true

# Ruff formatting
run_check "Ruff format" \
    "ruff format app/ tests/" || true

# Black formatting (if ruff format fails)
if command -v black &> /dev/null; then
    run_check "Black formatting" \
        "black app/ tests/" || true
fi

# isort for imports
if command -v isort &> /dev/null; then
    run_check "Import sorting" \
        "isort app/ tests/" || true
fi

# 4. Type checking (optional but recommended)
echo
echo -e "${BLUE}=== Type Checking ===${NC}"
if command -v mypy &> /dev/null && [ "${RUN_MYPY:-false}" = "true" ]; then
    run_check "MyPy type checking" \
        "mypy app/ --ignore-missing-imports" || true
else
    warning "mypy type checking disabled (set RUN_MYPY=true to enable)"
fi

# 5. Unit tests
echo
echo -e "${BLUE}=== Unit Tests ===${NC}"
run_check "Unit tests" \
    "pytest tests/unit/ -v --tb=short" || true

# 6. API tests
echo
echo -e "${BLUE}=== API Tests ===${NC}"
run_check "API tests" \
    "pytest tests/api/ -v --tb=short" || true

# 7. Integration tests (optional - requires MinIO)
echo
echo -e "${BLUE}=== Integration Tests ===${NC}"
if docker ps | grep -q minio; then
    run_check "Integration tests" \
        "pytest tests/integration/ -v --tb=short" || true
else
    warning "MinIO not running, skipping integration tests"
    log "To run integration tests locally:"
    echo "  docker run -d -p 9000:9000 -e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=minioadmin minio/minio server /data"
fi

# 8. Kubernetes validation
echo
echo -e "${BLUE}=== Kubernetes Validation ===${NC}"

# Check if kubectl is available
if command -v kubectl &> /dev/null; then
    # Quick K8s tests only
    run_check "K8s quick validation" \
        "./scripts/k8s/test-phase3-quick.sh" || true
    
    # Full validation (optional - takes longer)
    if [ "${RUN_FULL_K8S:-false}" = "true" ]; then
        run_check "K8s full validation" \
            "./scripts/k8s/validate-all.sh" || true
    else
        log "Skipping full K8s validation (set RUN_FULL_K8S=true to enable)"
    fi
else
    warning "kubectl not installed, skipping K8s validation"
fi

# 9. Security checks
echo
echo -e "${BLUE}=== Security Checks ===${NC}"

# Check for secrets
run_check "Secret scanning" \
    "! grep -r -E '(password|secret|key|token)\\s*=\\s*[\"'\''][^\"'\'']+[\"'\'']' app/ --exclude-dir=__pycache__" || true

# Safety check for known vulnerabilities (disabled due to tool bug)
if command -v safety &> /dev/null && [ "${RUN_SAFETY:-false}" = "true" ]; then
    run_check "Dependency vulnerabilities" \
        "safety check --json" || true
else
    warning "safety check disabled (set RUN_SAFETY=true to enable)"
fi

# 10. Documentation checks
echo
echo -e "${BLUE}=== Documentation ===${NC}"
run_check "README exists" \
    "[ -f README.md ]" || true

run_check "Docs folder exists" \
    "[ -d docs/ ]" || true

# Summary
echo
echo -e "${BLUE}=== Summary ===${NC}"
if [ ${#FAILED_CHECKS[@]} -eq 0 ]; then
    success "All checks passed! ✨"
    echo -e "${GREEN}Ready to push to GitHub${NC}"
    
    # Show git status
    echo
    log "Git status:"
    git status --short
    
    # Offer to push
    echo
    read -p "Do you want to push now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        BRANCH=$(git rev-parse --abbrev-ref HEAD)
        # Detect remote name (origin, github, etc.)
        REMOTE=$(git remote | grep -E "^(origin|github)$" | head -1)
        if [ -z "$REMOTE" ]; then
            REMOTE=$(git remote | head -1)
        fi
        log "Pushing to $REMOTE/$BRANCH..."
        git push "$REMOTE" "$BRANCH"
    fi
else
    error "Failed checks:"
    for check in "${FAILED_CHECKS[@]}"; do
        echo "  - $check"
    done
    echo
    error "Please fix the issues above before pushing"
    exit 1
fi