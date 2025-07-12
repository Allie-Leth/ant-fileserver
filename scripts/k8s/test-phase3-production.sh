#!/usr/bin/env bash
set -euo pipefail

# Phase 3 Production Readiness Testing Script
# Tests HPA, PDB, Anti-affinity, and monitoring features

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

validate_overlay() {
    local overlay="$1"
    local name="$2"
    
    log "Validating $name overlay..."
    
    # Basic structure tests
    run_test "$name: Kustomize builds successfully" \
        "kubectl kustomize k8s/app/overlays/$overlay > /dev/null 2>&1"
    
    run_test "$name: Contains HPA" \
        "kubectl kustomize k8s/app/overlays/$overlay | grep -q 'kind: HorizontalPodAutoscaler'"
    
    run_test "$name: Contains PDB" \
        "kubectl kustomize k8s/app/overlays/$overlay | grep -q 'kind: PodDisruptionBudget'"
    
    run_test "$name: HPA has correct metrics" \
        "kubectl kustomize k8s/app/overlays/$overlay | awk '/kind: HorizontalPodAutoscaler/,0' | grep -q 'averageUtilization:'"
    
    run_test "$name: PDB has minAvailable" \
        "kubectl kustomize k8s/app/overlays/$overlay | awk '/kind: PodDisruptionBudget/,0' | grep -q 'minAvailable:'"
    
    run_test "$name: Anti-affinity configured" \
        "kubectl kustomize k8s/app/overlays/$overlay | grep -q 'podAntiAffinity:'"
    
    # Resource validation
    run_test "$name: Resources increased from base" \
        "kubectl kustomize k8s/app/overlays/$overlay | grep -A5 'resources:' | grep -E 'cpu: (200m|500m|1000m|2000m)|memory: (256Mi|512Mi|1Gi|2Gi)'"
}

main() {
    log "Phase 3 Production Readiness Testing Suite"
    log "=========================================="
    
    # Test 1: Validate staging overlay
    echo
    validate_overlay "staging" "Staging"
    
    # Staging-specific tests
    run_test "Staging: ServiceMonitor created" \
        "kubectl kustomize k8s/app/overlays/staging | grep -q 'kind: ServiceMonitor'"
    
    run_test "Staging: HPA min replicas is 2" \
        "kubectl kustomize k8s/app/overlays/staging | awk '/kind: HorizontalPodAutoscaler/,/---/' | grep 'minReplicas:' | grep -q '2'"
    
    run_test "Staging: HPA max replicas is 5" \
        "kubectl kustomize k8s/app/overlays/staging | awk '/kind: HorizontalPodAutoscaler/,/---/' | grep 'maxReplicas:' | grep -q '5'"
    
    run_test "Staging: PDB minAvailable is 1" \
        "kubectl kustomize k8s/app/overlays/staging | awk '/kind: PodDisruptionBudget/,/---/' | grep 'minAvailable:' | grep -q '1'"
    
    run_test "Staging: Ingress uses staging host" \
        "kubectl kustomize k8s/app/overlays/staging | grep -q 'host: api-staging.scopecreep.productions'"
    
    # Test 2: Validate production overlay
    echo
    validate_overlay "prod" "Production"
    
    # Production-specific tests
    run_test "Production: HPA min replicas is 2" \
        "kubectl kustomize k8s/app/overlays/prod | awk '/kind: HorizontalPodAutoscaler/,/---/' | grep 'minReplicas:' | grep -q '2'"
    
    run_test "Production: HPA max replicas is 10" \
        "kubectl kustomize k8s/app/overlays/prod | awk '/kind: HorizontalPodAutoscaler/,/---/' | grep 'maxReplicas:' | grep -q '10'"
    
    run_test "Production: PDB minAvailable is 2" \
        "kubectl kustomize k8s/app/overlays/prod | awk '/kind: PodDisruptionBudget/,/---/' | grep 'minAvailable:' | grep -q '2'"
    
    run_test "Production: Required anti-affinity" \
        "kubectl kustomize k8s/app/overlays/prod | grep -q 'requiredDuringSchedulingIgnoredDuringExecution:'"
    
    run_test "Production: Higher resource limits" \
        "kubectl kustomize k8s/app/overlays/prod | grep -A5 'limits:' | grep -q 'cpu: 2000m'"
    
    run_test "Production: Security headers configured" \
        "kubectl kustomize k8s/app/overlays/prod | grep -q 'X-Frame-Options: DENY'"
    
    # Test 3: HPA behavior validation
    echo
    log "=== HPA Behavior Validation ==="
    
    run_test "Staging: Scale down stabilization is 300s" \
        "kubectl kustomize k8s/app/overlays/staging | awk '/scaleDown:/,/scaleUp:/' | grep 'stabilizationWindowSeconds:' | grep -q '300'"
    
    run_test "Production: Scale down stabilization is 600s" \
        "kubectl kustomize k8s/app/overlays/prod | awk '/scaleDown:/,/scaleUp:/' | grep 'stabilizationWindowSeconds:' | grep -q '600'"
    
    run_test "HPA has both CPU and memory metrics" \
        "kubectl kustomize k8s/app/overlays/staging | awk '/kind: HorizontalPodAutoscaler/,0' | grep -c 'type: Resource' | grep -q '2'"
    
    # Test 4: Runtime checks (if cluster available)
    if kubectl cluster-info &> /dev/null; then
        echo
        log "=== Runtime Validation ==="
        
        run_test "Metrics server is running" \
            "kubectl get deployment -n kube-system metrics-server &> /dev/null"
        
        run_test "Can get node metrics" \
            "kubectl top nodes &> /dev/null"
        
        run_test "ServiceMonitor CRD exists" \
            "kubectl get crd servicemonitors.monitoring.coreos.com &> /dev/null"
        
        # Check if we have multiple nodes for anti-affinity
        local node_count=$(kubectl get nodes --no-headers | wc -l)
        if [ "$node_count" -gt 1 ]; then
            success "Multiple nodes available for anti-affinity testing ($node_count nodes)"
        else
            warning "Only $node_count node(s) available - anti-affinity testing limited"
        fi
    else
        warning "No cluster available - skipping runtime tests"
    fi
    
    # Test 5: Manifest syntax validation
    echo
    log "=== Syntax Validation ==="
    
    run_test "Staging manifests are valid" \
        "kubectl kustomize k8s/app/overlays/staging | kubectl create --dry-run=client -f - > /dev/null 2>&1"
    
    run_test "Production manifests are valid" \
        "kubectl kustomize k8s/app/overlays/prod | kubectl create --dry-run=client -f - > /dev/null 2>&1"
    
    # Summary
    echo
    log "Test Results Summary"
    log "==================="
    log "Tests Run: $TESTS_RUN"
    if [ $TESTS_PASSED -eq $TESTS_RUN ]; then
        success "Tests Passed: $TESTS_PASSED ✨"
        log "Phase 3 production readiness features validated!"
        echo
        success "✅ HPA configured for auto-scaling"
        success "✅ PDB ensures high availability"
        success "✅ Anti-affinity spreads pods across nodes"
        success "✅ ServiceMonitor ready for Prometheus"
        success "✅ Resources tuned for each environment"
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