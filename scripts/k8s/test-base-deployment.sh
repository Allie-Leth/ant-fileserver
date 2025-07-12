#!/usr/bin/env bash
set -euo pipefail

# Kubernetes Deployment Testing Script
# 
# This script tests the actual deployment of the ant-fileserver
# in a test namespace, validating runtime behavior.

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Configuration
TEST_NAMESPACE="${TEST_NAMESPACE:-ant-test}"
TEST_TIMEOUT="${TEST_TIMEOUT:-300}"  # 5 minutes
CLEANUP="${CLEANUP:-true}"

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

# Cleanup function
cleanup() {
    if [ "$CLEANUP" = "true" ]; then
        log "Cleaning up test namespace..."
        kubectl delete namespace "$TEST_NAMESPACE" --ignore-not-found=true --wait=false
    else
        warning "Cleanup disabled - namespace $TEST_NAMESPACE retained for debugging"
    fi
}

# Set trap for cleanup
trap cleanup EXIT

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

# Wait for condition with timeout
wait_for_condition() {
    local condition="$1"
    local timeout="$2"
    local interval="${3:-5}"
    local elapsed=0
    
    while ! eval "$condition"; do
        if [ $elapsed -ge $timeout ]; then
            return 1
        fi
        sleep $interval
        elapsed=$((elapsed + interval))
    done
    return 0
}

# Create test resources
create_test_resources() {
    log "Creating test namespace..."
    kubectl create namespace "$TEST_NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
    
    # Create minimal secrets for testing
    log "Creating test secrets..."
    kubectl create secret generic ant-fileserver-secrets \
        --namespace="$TEST_NAMESPACE" \
        --from-literal=STORAGE_ACCESS_KEY_ID=test-access-key \
        --from-literal=STORAGE_SECRET_ACCESS_KEY=test-secret-key \
        --from-literal=JWT_SECRET_KEY=test-jwt-secret \
        --from-literal=API_KEY_ROLES='{"test-key":["uploader"]}' \
        --dry-run=client -o yaml | kubectl apply -f -
    
    # Apply base manifests with test overrides
    log "Applying manifests..."
    kubectl kustomize k8s/app/base/ | \
        sed 's|image: ant-fileserver:latest|image: ant-fileserver:test|g' | \
        kubectl apply -n "$TEST_NAMESPACE" -f -
}

# Main test function
main() {
    log "Kubernetes Deployment Testing Suite"
    log "==================================="
    
    cd "$PROJECT_ROOT"
    
    # Check prerequisites
    if ! kubectl cluster-info &> /dev/null; then
        error "No Kubernetes cluster available. Please ensure kubectl is configured."
        exit 1
    fi
    
    # Create test resources
    create_test_resources
    
    # Test 1: Namespace created
    run_test "Namespace exists" \
        "kubectl get namespace $TEST_NAMESPACE"
    
    # Test 2: All resources created
    run_test "Deployment created" \
        "kubectl get deployment ant-fileserver -n $TEST_NAMESPACE"
    
    run_test "Service created" \
        "kubectl get service ant-fileserver -n $TEST_NAMESPACE"
    
    run_test "ServiceAccount created" \
        "kubectl get serviceaccount ant-fileserver -n $TEST_NAMESPACE"
    
    run_test "ConfigMap created" \
        "kubectl get configmap ant-fileserver-config -n $TEST_NAMESPACE"
    
    run_test "Secret exists" \
        "kubectl get secret ant-fileserver-secrets -n $TEST_NAMESPACE"
    
    # Test 3: Wait for deployment to be ready
    log "Waiting for deployment to be ready (timeout: ${TEST_TIMEOUT}s)..."
    if wait_for_condition \
        "kubectl rollout status deployment/ant-fileserver -n $TEST_NAMESPACE --timeout=10s &> /dev/null" \
        "$TEST_TIMEOUT"; then
        success "Deployment is ready"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        error "Deployment failed to become ready"
        kubectl describe pod -n "$TEST_NAMESPACE" -l app=ant-fileserver
        kubectl logs -n "$TEST_NAMESPACE" -l app=ant-fileserver --tail=50
    fi
    TESTS_RUN=$((TESTS_RUN + 1))
    
    # Test 4: Pod is running
    run_test "Pod is running" \
        "kubectl get pods -n $TEST_NAMESPACE -l app=ant-fileserver -o jsonpath='{.items[0].status.phase}' | grep -q Running"
    
    # Test 5: Security context applied
    POD_NAME=$(kubectl get pods -n "$TEST_NAMESPACE" -l app=ant-fileserver -o jsonpath='{.items[0].metadata.name}')
    
    if [ -n "$POD_NAME" ]; then
        run_test "Security context - non-root user" \
            "kubectl get pod $POD_NAME -n $TEST_NAMESPACE -o jsonpath='{.spec.securityContext.runAsUser}' | grep -q 1000"
        
        run_test "Security context - read-only filesystem" \
            "kubectl get pod $POD_NAME -n $TEST_NAMESPACE -o jsonpath='{.spec.containers[0].securityContext.readOnlyRootFilesystem}' | grep -q true"
        
        # Test 6: Resource limits applied
        run_test "Resource requests applied" \
            "kubectl get pod $POD_NAME -n $TEST_NAMESPACE -o jsonpath='{.spec.containers[0].resources.requests.cpu}' | grep -q 100m"
        
        run_test "Resource limits applied" \
            "kubectl get pod $POD_NAME -n $TEST_NAMESPACE -o jsonpath='{.spec.containers[0].resources.limits.memory}' | grep -q 512Mi"
        
        # Test 7: Environment variables
        run_test "ConfigMap environment loaded" \
            "kubectl exec $POD_NAME -n $TEST_NAMESPACE -- env | grep -q FLASK_ENV=production"
        
        run_test "Secret environment loaded" \
            "kubectl exec $POD_NAME -n $TEST_NAMESPACE -- env | grep -q STORAGE_ACCESS_KEY_ID"
        
        # Test 8: Volumes mounted
        run_test "Temp volume mounted" \
            "kubectl exec $POD_NAME -n $TEST_NAMESPACE -- ls -la /tmp > /dev/null 2>&1"
        
        # Test 9: Service endpoints
        run_test "Service has endpoints" \
            "kubectl get endpoints ant-fileserver -n $TEST_NAMESPACE -o jsonpath='{.subsets[0].addresses}' | grep -q ip"
        
        # Test 10: Network connectivity
        run_test "Service is reachable" \
            "kubectl run curl-test --image=curlimages/curl:latest --rm -i -n $TEST_NAMESPACE --restart=Never -- \
            curl -s -o /dev/null -w '%{http_code}' http://ant-fileserver/health | grep -E '200|404'"
    else
        error "No pod found - skipping pod-specific tests"
    fi
    
    # Summary
    echo
    log "Test Results Summary"
    log "==================="
    log "Tests Run: $TESTS_RUN"
    if [ $TESTS_PASSED -eq $TESTS_RUN ]; then
        success "Tests Passed: $TESTS_PASSED ✨"
        log "Base deployment tests passed!"
        exit 0
    else
        error "Tests Failed: $((TESTS_RUN - TESTS_PASSED))"
        log "Some tests failed. Check the logs above."
        exit 1
    fi
}

# Run if called directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi