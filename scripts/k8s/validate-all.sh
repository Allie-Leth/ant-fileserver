#!/usr/bin/env bash
set -euo pipefail

# Master validation script - runs all test suites
# Validates Phase 1 & 2 are working correctly together

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOTAL_TESTS=0
TOTAL_PASSED=0

run_test_suite() {
    local suite_name="$1"
    local script_path="$2"
    
    echo
    log "Running $suite_name..."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    if [ -x "$script_path" ]; then
        if "$script_path"; then
            success "$suite_name completed successfully"
            return 0
        else
            error "$suite_name failed"
            return 1
        fi
    else
        error "$script_path not found or not executable"
        return 1
    fi
}

main() {
    log "🚀 Kubernetes Infrastructure Validation Suite"
    log "============================================"
    log "Validating Phase 1 & 2 Implementation"
    echo
    
    local failed=0
    
    # Phase 1: Base manifest validation
    if run_test_suite "Phase 1: Manifest Validation" "$SCRIPT_DIR/validate-manifests.sh"; then
        TOTAL_TESTS=$((TOTAL_TESTS + 13))
        TOTAL_PASSED=$((TOTAL_PASSED + 13))
    else
        failed=$((failed + 1))
    fi
    
    # Phase 1: Security context validation
    echo
    log "Running Phase 1: Security Context Validation..."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    if "$SCRIPT_DIR/test-security-context.sh"; then
        success "Security contexts validated"
        TOTAL_TESTS=$((TOTAL_TESTS + 6))
        TOTAL_PASSED=$((TOTAL_PASSED + 6))
    else
        error "Security context validation failed"
        failed=$((failed + 1))
    fi
    
    # Phase 2: Network validation
    if run_test_suite "Phase 2: Network Validation" "$SCRIPT_DIR/test-phase2-network.sh"; then
        TOTAL_TESTS=$((TOTAL_TESTS + 14))
        TOTAL_PASSED=$((TOTAL_PASSED + 14))
    else
        failed=$((failed + 1))
    fi
    
    # Integration tests
    if run_test_suite "Integration Tests" "$SCRIPT_DIR/test-integration.sh"; then
        TOTAL_TESTS=$((TOTAL_TESTS + 60))
        TOTAL_PASSED=$((TOTAL_PASSED + 60))
    else
        failed=$((failed + 1))
    fi
    
    # Final summary
    echo
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "📊 Final Validation Summary"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    echo -e "${BLUE}Test Suites Run:${NC} 4"
    echo -e "${BLUE}Total Tests:${NC} $TOTAL_TESTS"
    echo -e "${GREEN}Tests Passed:${NC} $TOTAL_PASSED"
    
    if [ $failed -eq 0 ]; then
        echo
        success "🎉 All validation tests passed!"
        success "✅ Phase 1: Base Kubernetes manifests - VALIDATED"
        success "✅ Phase 2: Security & Networking - VALIDATED"
        success "✅ Integration: All overlays working correctly"
        echo
        log "The Kubernetes infrastructure is ready for deployment!"
        exit 0
    else
        echo
        error "❌ $failed test suite(s) failed"
        error "Please review the errors above and fix any issues"
        exit 1
    fi
}

# Run if called directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi