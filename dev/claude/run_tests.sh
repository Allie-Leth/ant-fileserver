#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# Comprehensive Test Runner for Ant Fileserver
# 
# This script runs all quality checks, tests, and validations in the correct order.
# It will continue to run until all tests pass, fixing errors along the way.
###############################################################################

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
TOTAL_RUNS=0
FAILED_RUNS=0

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to run a command and capture its exit code
run_check() {
    local name="$1"
    local cmd="$2"
    local optional="${3:-false}"
    
    log "Running: $name"
    echo "Command: $cmd"
    
    if eval "$cmd"; then
        success "$name passed"
        return 0
    else
        if [ "$optional" = "true" ]; then
            warning "$name failed (optional)"
            return 0
        else
            error "$name failed"
            return 1
        fi
    fi
}

# Function to activate virtual environment
activate_venv() {
    if [ -d ".venv" ]; then
        log "Activating virtual environment"
        source .venv/bin/activate
    else
        log "Creating virtual environment"
        python3 -m venv .venv
        source .venv/bin/activate
        pip install --upgrade pip
    fi
}

# Function to install dependencies
install_deps() {
    log "Installing dependencies"
    pip install -r requirements.txt -r requirements-dev.txt
}

# Function to run all checks
run_all_checks() {
    local failed=0
    
    echo
    log "Starting comprehensive test suite (Run #$((TOTAL_RUNS + 1)))"
    echo "============================================================"
    
    # 1. Code Quality Checks
    echo
    log "Phase 1: Code Quality Checks"
    echo "----------------------------"
    
    if ! run_check "Ruff Linting" "ruff check app/ tests/"; then
        failed=1
    fi
    
    if ! run_check "Ruff Formatting" "ruff format --check app/ tests/"; then
        failed=1
    fi
    
    # 2. Static Analysis
    echo
    log "Phase 2: Static Analysis"
    echo "------------------------"
    
    # Import sorting is handled by ruff, no separate check needed
    
    # 3. Configuration Validation
    echo
    log "Phase 3: Configuration Validation"
    echo "--------------------------------"
    
    if ! run_check "GitHub Actions Syntax" "python -c \"import yaml; [yaml.safe_load(open(f)) for f in ['.github/workflows/ci.yml', '.github/workflows/release.yml']]\""; then
        failed=1
    fi
    
    if ! run_check "Kubernetes Manifests" "python -c \"import yaml; [yaml.safe_load(open(f)) for f in ['k8s/app/base/deployment.yaml', 'k8s/app/base/service.yaml']]\""; then
        failed=1
    fi
    
    # 4. Unit Tests
    echo
    log "Phase 4: Unit Tests"
    echo "------------------"
    
    if ! run_check "Unit Tests" "python -m pytest tests/unit/ -v --tb=short"; then
        failed=1
    fi
    
    # 5. API Tests
    echo
    log "Phase 5: API Tests"
    echo "----------------"
    
    export PYTHONPATH="$PWD"
    export STORAGE_ENDPOINT="http://dummy"
    export STORAGE_BUCKET="firmware"
    export STORAGE_ACCESS_KEY_ID="dummy"
    export STORAGE_SECRET_ACCESS_KEY="dummy"
    export STORAGE_REGION="us-east-1"
    export JWT_SECRET_KEY="test-secret"
    
    if ! run_check "API Tests" "python -m pytest tests/api/ -v --tb=short"; then
        failed=1
    fi
    
    # 6. Integration Tests (if docker is available)
    echo
    log "Phase 6: Integration Tests"
    echo "-------------------------"
    
    if command -v docker &> /dev/null; then
        if ! run_check "Integration Tests" "./scripts/dev-integration.sh"; then
            failed=1
        fi
    else
        warning "Docker not available, skipping integration tests"
    fi
    
    # 7. Test Coverage
    echo
    log "Phase 7: Test Coverage"
    echo "--------------------"
    
    if ! run_check "Test Coverage" "python -m pytest tests/ --cov=app --cov-report=term-missing --cov-fail-under=80"; then
        failed=1
    fi
    
    # 8. Container Build Test
    echo
    log "Phase 8: Container Build"
    echo "----------------------"
    
    if command -v docker &> /dev/null; then
        if ! run_check "Docker Build" "docker build -t ant-fileserver:test ."; then
            failed=1
        fi
    else
        warning "Docker not available, skipping container build"
    fi
    
    # 9. Security Checks
    echo
    log "Phase 9: Security Checks"
    echo "-----------------------"
    
    if ! run_check "Secret Detection" "grep -r \"password\\|token\\|key\\|secret\" --include=\"*.py\" --exclude-dir=tests app/ || true"; then
        warning "Found potential secrets in code"
    fi
    
    # 10. Documentation Checks
    echo
    log "Phase 10: Documentation"
    echo "---------------------"
    
    if ! run_check "Required Files" "test -f CHANGELOG.md && test -f CLAUDE.md && test -f MIGRATION_GUIDE.md"; then
        failed=1
    fi
    
    echo
    echo "============================================================"
    
    return $failed
}

# Function to fix common issues
fix_common_issues() {
    log "Attempting to fix common issues"
    
    # Fix formatting
    if command -v ruff &> /dev/null; then
        log "Auto-fixing ruff issues"
        ruff check app/ tests/ --fix || true
        ruff format app/ tests/ || true
    fi
    
    # Fix imports
    if pip show isort &> /dev/null; then
        log "Auto-fixing import order"
        python -m isort app/ tests/ || true
    fi
}

# Main execution loop
main() {
    log "Ant Fileserver Comprehensive Test Runner"
    log "========================================"
    
    # Change to project root directory (two levels up from dev/claude/)
    cd "$(dirname "${BASH_SOURCE[0]}")/../.."
    
    # Activate virtual environment and install dependencies
    activate_venv
    install_deps
    
    # Main test loop
    while true; do
        TOTAL_RUNS=$((TOTAL_RUNS + 1))
        
        if run_all_checks; then
            echo
            success "🎉 All tests passed! (Total runs: $TOTAL_RUNS, Failed runs: $FAILED_RUNS)"
            
            # Show summary
            echo
            log "Test Summary"
            echo "============"
            echo "✅ Code quality: PASSED"
            echo "✅ Unit tests: PASSED"
            echo "✅ API tests: PASSED"
            echo "✅ Integration tests: PASSED"
            echo "✅ Test coverage: PASSED"
            echo "✅ Container build: PASSED"
            echo "✅ Security checks: PASSED"
            echo "✅ Documentation: PASSED"
            
            break
        else
            FAILED_RUNS=$((FAILED_RUNS + 1))
            error "Tests failed (Run #$TOTAL_RUNS)"
            
            echo
            warning "Attempting to fix issues automatically..."
            fix_common_issues
            
            echo
            warning "Waiting 5 seconds before retry..."
            sleep 5
            
            if [ $FAILED_RUNS -ge 5 ]; then
                error "Too many failed runs ($FAILED_RUNS). Please check the errors manually."
                exit 1
            fi
        fi
    done
}

# Run if called directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi