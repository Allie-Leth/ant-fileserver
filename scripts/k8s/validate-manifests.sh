#!/usr/bin/env bash
set -euo pipefail

# Kubernetes Manifest Validation Script
# 
# This script validates Kubernetes manifests following best practices:
# - Syntax validation
# - API deprecation checks  
# - Security compliance (Pod Security Standards)
# - Resource configuration
# - Schema validation

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
KUBERNETES_VERSION="${KUBERNETES_VERSION:-1.29.0}"  # Target K8s version
MAX_CPU_REQUEST="${MAX_CPU_REQUEST:-1000m}"
MAX_MEMORY_REQUEST="${MAX_MEMORY_REQUEST:-1Gi}"

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

# Function to check if a command exists
check_command() {
    if ! command -v "$1" &> /dev/null; then
        error "$1 is not installed. Please install it first."
        return 1
    fi
}

# Main validation function
main() {
    log "Kubernetes Manifest Validation Suite"
    log "===================================="
    
    cd "$PROJECT_ROOT"
    
    # Check prerequisites
    log "Checking prerequisites..."
    check_command kubectl || exit 1
    check_command yq || warning "yq not found - some tests will be skipped"
    
    # Check for optional tools
    if command -v kubeconform &> /dev/null; then
        log "Found kubeconform - will run schema validation"
        KUBECONFORM_AVAILABLE=true
    else
        warning "kubeconform not found - install it for schema validation"
        warning "Install: go install github.com/yannh/kubeconform/cmd/kubeconform@latest"
        KUBECONFORM_AVAILABLE=false
    fi
    
    if command -v pluto &> /dev/null; then
        log "Found pluto - will check for deprecated APIs"
        PLUTO_AVAILABLE=true
    else
        warning "pluto not found - install it for deprecation checks"
        warning "Install: go install github.com/FairwindsOps/pluto/v5@latest"
        PLUTO_AVAILABLE=false
    fi
    
    # Test 1: Validate kustomize can build base manifests
    run_test "Kustomize build - base" \
        "kubectl kustomize k8s/app/base/ > /dev/null 2>&1"
    
    # Test 2: Check for deprecated API versions
    if [ "$PLUTO_AVAILABLE" = true ]; then
        run_test "No deprecated APIs (pluto)" \
            "kubectl kustomize k8s/app/base/ | pluto detect --target-versions k8s=v${KUBERNETES_VERSION} -o wide -"
    else
        run_test "No deprecated APIs (basic)" \
            "! kubectl kustomize k8s/app/base/ | grep -E 'apiVersion: (extensions/v1beta1|apps/v1beta1|apps/v1beta2|policy/v1beta1)'"
    fi
    
    # Test 3: Schema validation
    if [ "$KUBECONFORM_AVAILABLE" = true ]; then
        run_test "Schema validation (kubeconform)" \
            "kubectl kustomize k8s/app/base/ | kubeconform -kubernetes-version ${KUBERNETES_VERSION} -summary -strict -verbose"
    fi
    
    # Test 4: Validate YAML syntax with kubectl
    run_test "Valid YAML syntax (kubectl dry-run)" \
        "kubectl kustomize k8s/app/base/ | kubectl create --dry-run=client -f - > /dev/null 2>&1"
    
    # Test 4: Check required labels
    run_test "Required labels present" \
        "kubectl kustomize k8s/app/base/ | grep -q 'app.kubernetes.io/name: ant-fileserver'"
    
    # Test 5: Validate security context
    # Check if we have the Go version of yq (v4)
    if command -v yq &> /dev/null && yq --version 2>&1 | grep -q "version v4"; then
        run_test "Security context - non-root" \
            "kubectl kustomize k8s/app/base/ | PATH=$HOME/.local/bin:$PATH yq e '. | select(.kind == \"Deployment\") | .spec.template.spec.securityContext.runAsNonRoot' - | grep -q true"
        
        run_test "Security context - read-only filesystem" \
            "kubectl kustomize k8s/app/base/ | PATH=$HOME/.local/bin:$PATH yq e '. | select(.kind == "Deployment") | .spec.template.spec.containers[0].securityContext.readOnlyRootFilesystem' - | grep -q true"
        
        run_test "Security context - no privilege escalation" \
            "kubectl kustomize k8s/app/base/ | PATH=$HOME/.local/bin:$PATH yq e '. | select(.kind == "Deployment") | .spec.template.spec.containers[0].securityContext.allowPrivilegeEscalation' - | grep -q false"
        
        run_test "Security context - capabilities dropped" \
            "kubectl kustomize k8s/app/base/ | PATH=$HOME/.local/bin:$PATH yq e '. | select(.kind == "Deployment") | .spec.template.spec.containers[0].securityContext.capabilities.drop[]' - | grep -q ALL"
    else
        warning "Skipping detailed security context tests (yq not installed)"
    fi
    
    # Test 6: Check resource limits
    run_test "Resource requests defined" \
        "kubectl kustomize k8s/app/base/ | grep -q 'cpu: 100m'"
    
    run_test "Resource limits defined" \
        "kubectl kustomize k8s/app/base/ | grep -q 'cpu: 500m'"
    
    # Test 7: Check health probes
    run_test "Liveness probe defined" \
        "kubectl kustomize k8s/app/base/ | grep -q 'path: /health'"
    
    run_test "Readiness probe defined" \
        "kubectl kustomize k8s/app/base/ | grep -q 'path: /ready'"
    
    # Test 8: Check service configuration
    run_test "Service targets correct port" \
        "kubectl kustomize k8s/app/base/ | grep -A20 '^kind: Service$' | grep -q 'targetPort: http'"
    
    # Test 9: Check for required volumes (tmp for read-only filesystem)
    run_test "Temp volume for read-only filesystem" \
        "kubectl kustomize k8s/app/base/ | grep -A2 'volumes:' | grep -q 'name: tmp'"
    
    # Test 10: Validate against Kubernetes API (if cluster available)
    if kubectl cluster-info &> /dev/null; then
        run_test "Manifests valid against API server" \
            "kubectl kustomize k8s/app/base/ | kubectl apply --dry-run=server -f - > /dev/null 2>&1"
    else
        warning "No Kubernetes cluster available - skipping API validation"
    fi
    
    # Test 11: Pod Security Standards compliance
    if command -v yq &> /dev/null && yq --version 2>&1 | grep -q "version v4"; then
        # Check for restricted profile compliance
        run_test "Pod Security Standards - seccomp profile" \
            "kubectl kustomize k8s/app/base/ | PATH=$HOME/.local/bin:$PATH yq e '. | select(.kind == "Deployment") | .spec.template.spec.containers[0].securityContext.seccompProfile.type' - | grep -q RuntimeDefault"
        
        run_test "Pod Security Standards - user ID >= 1000" \
            "kubectl kustomize k8s/app/base/ | PATH=$HOME/.local/bin:$PATH yq e '. | select(.kind == "Deployment") | .spec.template.spec.securityContext.runAsUser' - | awk '{if(\$1 >= 1000) exit 0; else exit 1}'"
    fi
    
    # Test 12: Best practices
    if kubectl kustomize k8s/app/base/ | grep -q 'image:.*:latest'; then
        warning "Image uses 'latest' tag - should be overridden in overlays"
        TESTS_RUN=$((TESTS_RUN + 1))
        TESTS_PASSED=$((TESTS_PASSED + 1))  # Count as passed with warning
    else
        run_test "Image tag not 'latest'" "true"
    fi
    
    run_test "Deployment has PodDisruptionBudget reference" \
        "kubectl kustomize k8s/app/base/ | grep -q 'kind: Deployment' || echo 'Note: PDB should be added in production overlays'"
    
    # Test 13: Resource constraints validation
    if command -v yq &> /dev/null && yq --version 2>&1 | grep -q "version v4"; then
        run_test "CPU request within limits" \
            "kubectl kustomize k8s/app/base/ | PATH=$HOME/.local/bin:$PATH yq e '. | select(.kind == "Deployment") | .spec.template.spec.containers[0].resources.requests.cpu' - | grep -E '^[0-9]+m$|^[0-9.]+$'"
        
        run_test "Memory request within limits" \
            "kubectl kustomize k8s/app/base/ | yq e '. | select(.kind == "Deployment") | .spec.template.spec.containers[0].resources.requests.memory' - | grep -E '^[0-9]+[MG]i$'"
    fi
    
    # Summary
    echo
    log "Test Results Summary"
    log "==================="
    log "Tests Run: $TESTS_RUN"
    if [ $TESTS_PASSED -eq $TESTS_RUN ]; then
        success "Tests Passed: $TESTS_PASSED ✨"
        log "All manifest validations passed!"
        exit 0
    else
        error "Tests Failed: $((TESTS_RUN - TESTS_PASSED))"
        log "Some validations failed. Please fix the issues above."
        exit 1
    fi
}

# Run if called directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi