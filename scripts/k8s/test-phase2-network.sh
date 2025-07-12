#!/usr/bin/env bash
set -euo pipefail

# Phase 2 Network Testing Script
# Tests NetworkPolicy, Ingress, and MinIO connectivity

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

# Test counter
TESTS_RUN=0
TESTS_PASSED=0

run_test() {
    local test_name="$1"
    local test_cmd="$2"
    
    TESTS_RUN=$((TESTS_RUN + 1))
    log "Running test: $test_name"
    
    if eval "$test_cmd"; then
        success "✅ $test_name"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        error "❌ $test_name"
        return 1
    fi
}

main() {
    log "Phase 2 Network Testing Suite"
    log "============================="
    
    # Test 1: Validate NetworkPolicy manifest
    run_test "NetworkPolicy validation" \
        "kubectl kustomize k8s/app/base/ | grep -q 'kind: NetworkPolicy'"
    
    # Test 2: Check NetworkPolicy rules
    run_test "NetworkPolicy has ingress rules" \
        "kubectl kustomize k8s/app/base/ | awk '/kind: NetworkPolicy/,0' | grep -q 'ingress:'"
    
    run_test "NetworkPolicy has egress rules" \
        "kubectl kustomize k8s/app/base/ | grep -A30 'kind: NetworkPolicy' | grep -q 'egress:'"
    
    run_test "NetworkPolicy allows DNS" \
        "kubectl kustomize k8s/app/base/ | grep -A50 'kind: NetworkPolicy' | grep -q 'port: 53'"
    
    run_test "NetworkPolicy allows MinIO" \
        "kubectl kustomize k8s/app/base/ | grep -A50 'kind: NetworkPolicy' | grep -q 'port: 9000'"
    
    # Test 3: Validate local overlay
    run_test "Local overlay builds" \
        "kubectl kustomize k8s/app/overlays/local/ > /dev/null 2>&1"
    
    run_test "Local overlay removes NetworkPolicy" \
        "! kubectl kustomize k8s/app/overlays/local/ | grep -q 'kind: NetworkPolicy'"
    
    run_test "Local overlay sets debug logging" \
        "kubectl kustomize k8s/app/overlays/local/ 2>/dev/null | grep -q 'LOG_LEVEL: debug'"
    
    # Test 4: Validate dev ingress
    run_test "Dev overlay includes ingress" \
        "kubectl kustomize k8s/app/overlays/dev/ | grep -q 'kind: Ingress'"
    
    run_test "Ingress has TLS configuration" \
        "kubectl kustomize k8s/app/overlays/dev/ | awk '/kind: Ingress/,0' | grep -q 'tls:'"
    
    run_test "Ingress uses cert-manager" \
        "kubectl kustomize k8s/app/overlays/dev/ | grep -q 'cert-manager.io/cluster-issuer'"
    
    run_test "Ingress has rate limiting" \
        "kubectl kustomize k8s/app/overlays/dev/ | grep -q 'nginx.ingress.kubernetes.io/rate-limit'"
    
    # Test 5: MinIO connectivity (if cluster available)
    if kubectl cluster-info &> /dev/null; then
        log "Testing MinIO connectivity..."
        
        # Check if MinIO namespace exists
        if kubectl get namespace minio &> /dev/null; then
            run_test "MinIO namespace exists" "true"
            
            run_test "MinIO service is accessible" \
                "kubectl -n minio get service minio &> /dev/null"
            
            # Test MinIO health endpoint
            if kubectl -n minio get service minio &> /dev/null; then
                log "Testing MinIO health endpoint..."
                kubectl run minio-test --rm -i --restart=Never \
                    --image=busybox \
                    --command -- sh -c \
                    "wget -qO- --timeout=5 http://minio.minio.svc.cluster.local:9000/minio/health/live && echo 'MinIO is healthy'" \
                    && success "MinIO health check passed" \
                    || warning "MinIO health check failed - check credentials"
            fi
        else
            warning "MinIO namespace not found - skipping connectivity tests"
        fi
    else
        warning "No Kubernetes cluster available - skipping runtime tests"
    fi
    
    # Summary
    echo
    log "Test Results Summary"
    log "==================="
    log "Tests Run: $TESTS_RUN"
    if [ $TESTS_PASSED -eq $TESTS_RUN ]; then
        success "Tests Passed: $TESTS_PASSED ✨"
        log "Phase 2 network configuration validated!"
        exit 0
    else
        error "Tests Failed: $((TESTS_RUN - TESTS_PASSED))"
        log "Please fix the issues above."
        exit 1
    fi
}

# Run if called directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi