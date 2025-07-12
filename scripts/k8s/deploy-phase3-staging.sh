#!/usr/bin/env bash
set -euo pipefail

# Phase 3 Staging Deployment and Testing Script
# Deploys the staging environment and tests HPA, PDB, and monitoring

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

NAMESPACE="ant-staging"
DEPLOYMENT="ant-fileserver"

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

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        error "kubectl not found. Please install kubectl."
        exit 1
    fi
    
    # Check cluster connection
    if ! kubectl cluster-info &> /dev/null; then
        error "Cannot connect to Kubernetes cluster."
        exit 1
    fi
    
    # Check metrics-server
    if ! kubectl get deployment -n kube-system metrics-server &> /dev/null; then
        error "metrics-server not found. HPA will not work without it."
        exit 1
    fi
    
    # Check for hey (load testing tool)
    if ! command -v hey &> /dev/null; then
        warning "hey not found. Install with: go install github.com/rakyll/hey@latest"
        warning "Load testing will be skipped."
    fi
    
    success "Prerequisites check passed"
}

# Create namespace
create_namespace() {
    log "Creating namespace $NAMESPACE..."
    
    if kubectl get namespace $NAMESPACE &> /dev/null; then
        warning "Namespace $NAMESPACE already exists"
    else
        kubectl create namespace $NAMESPACE
        success "Namespace created"
    fi
    
    # Label namespace for NetworkPolicy
    kubectl label namespace $NAMESPACE name=$NAMESPACE --overwrite
}

# Deploy staging environment
deploy_staging() {
    log "Deploying staging environment..."
    
    # Apply the manifests
    kubectl apply -k k8s/app/overlays/staging/
    
    success "Manifests applied"
    
    # Wait for deployment
    log "Waiting for deployment to be ready..."
    kubectl wait --for=condition=available --timeout=300s \
        deployment/$DEPLOYMENT -n $NAMESPACE
    
    success "Deployment is ready"
}

# Test HPA functionality
test_hpa() {
    log "=== Testing HorizontalPodAutoscaler ==="
    
    # Check HPA status
    log "HPA Status:"
    kubectl get hpa -n $NAMESPACE
    
    # Get current replica count
    CURRENT_REPLICAS=$(kubectl get deployment $DEPLOYMENT -n $NAMESPACE -o jsonpath='{.status.replicas}')
    log "Current replicas: $CURRENT_REPLICAS"
    
    # Check HPA targets
    log "Waiting for HPA to report metrics..."
    local attempts=0
    while [ $attempts -lt 30 ]; do
        if kubectl get hpa $DEPLOYMENT -n $NAMESPACE | grep -v "unknown"; then
            break
        fi
        sleep 10
        attempts=$((attempts + 1))
    done
    
    kubectl describe hpa $DEPLOYMENT -n $NAMESPACE
    
    # Generate load if hey is available
    if command -v hey &> /dev/null; then
        log "Generating load to test auto-scaling..."
        
        # Get service endpoint
        SERVICE_IP=$(kubectl get svc $DEPLOYMENT -n $NAMESPACE -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "")
        if [ -z "$SERVICE_IP" ]; then
            SERVICE_IP=$(kubectl get svc $DEPLOYMENT -n $NAMESPACE -o jsonpath='{.spec.clusterIP}')
            warning "Using ClusterIP $SERVICE_IP - load test may need to run from within cluster"
        fi
        
        # Port forward for testing
        log "Setting up port forward..."
        kubectl port-forward -n $NAMESPACE svc/$DEPLOYMENT 8080:80 &
        PF_PID=$!
        sleep 5
        
        # Run load test
        log "Running load test (60 seconds)..."
        hey -z 60s -c 50 -q 100 http://localhost:8080/health || true
        
        # Monitor scaling
        log "Monitoring HPA scaling..."
        for i in {1..12}; do
            kubectl get hpa,deployment -n $NAMESPACE
            sleep 10
        done
        
        # Clean up port forward
        kill $PF_PID 2>/dev/null || true
    fi
    
    success "HPA testing complete"
}

# Test PDB functionality
test_pdb() {
    log "=== Testing PodDisruptionBudget ==="
    
    # Check PDB status
    kubectl get pdb -n $NAMESPACE
    kubectl describe pdb $DEPLOYMENT -n $NAMESPACE
    
    # Get current pods
    PODS=$(kubectl get pods -n $NAMESPACE -l app=$DEPLOYMENT -o name)
    POD_COUNT=$(echo "$PODS" | wc -l)
    
    log "Current pod count: $POD_COUNT"
    
    if [ $POD_COUNT -ge 2 ]; then
        log "Testing PDB by attempting to evict a pod..."
        
        # Try to evict a pod
        FIRST_POD=$(echo "$PODS" | head -1 | cut -d'/' -f2)
        
        if kubectl create --dry-run=server -n $NAMESPACE -f - <<EOF
apiVersion: policy/v1
kind: Eviction
metadata:
  name: $FIRST_POD
  namespace: $NAMESPACE
spec:
  deleteOptions:
    gracePeriodSeconds: 30
EOF
        then
            success "PDB would allow eviction (healthy pods available)"
        else
            warning "PDB would block eviction (would violate disruption budget)"
        fi
    else
        warning "Need at least 2 pods to test PDB effectively"
    fi
    
    success "PDB testing complete"
}

# Test anti-affinity
test_antiaffinity() {
    log "=== Testing Pod Anti-Affinity ==="
    
    # Get pod distribution
    log "Pod distribution across nodes:"
    kubectl get pods -n $NAMESPACE -l app=$DEPLOYMENT -o wide
    
    # Check node distribution
    NODE_DISTRIBUTION=$(kubectl get pods -n $NAMESPACE -l app=$DEPLOYMENT \
        -o jsonpath='{range .items[*]}{.spec.nodeName}{"\n"}{end}' | sort | uniq -c)
    
    echo "$NODE_DISTRIBUTION"
    
    # Verify anti-affinity rules
    log "Checking anti-affinity configuration..."
    kubectl get pod -n $NAMESPACE -l app=$DEPLOYMENT -o yaml | \
        grep -A20 "affinity:" | grep -E "(podAntiAffinity|topologyKey)" || \
        warning "Anti-affinity rules not found in pod spec"
    
    success "Anti-affinity testing complete"
}

# Test monitoring
test_monitoring() {
    log "=== Testing ServiceMonitor ==="
    
    # Check if ServiceMonitor exists
    if kubectl get servicemonitor -n $NAMESPACE $DEPLOYMENT &> /dev/null; then
        success "ServiceMonitor found"
        kubectl describe servicemonitor -n $NAMESPACE $DEPLOYMENT
        
        # Check if Prometheus is scraping
        log "Checking if Prometheus operator picked up the ServiceMonitor..."
        
        # Look for Prometheus pods
        PROM_NS=$(kubectl get pods --all-namespaces -l app.kubernetes.io/name=prometheus -o jsonpath='{.items[0].metadata.namespace}' 2>/dev/null || echo "")
        
        if [ -n "$PROM_NS" ]; then
            log "Found Prometheus in namespace: $PROM_NS"
            # Could add more specific scraping validation here
        else
            warning "Prometheus not found - cannot verify scraping"
        fi
    else
        error "ServiceMonitor not found"
    fi
    
    success "Monitoring testing complete"
}

# Cleanup function
cleanup() {
    log "=== Cleanup ==="
    
    read -p "Do you want to delete the staging deployment? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        kubectl delete -k k8s/app/overlays/staging/ || true
        kubectl delete namespace $NAMESPACE || true
        success "Cleanup complete"
    else
        log "Keeping staging deployment"
    fi
}

# Main execution
main() {
    log "Phase 3 Staging Deployment and Testing"
    log "======================================"
    
    check_prerequisites
    
    create_namespace
    
    deploy_staging
    
    # Wait for pods to be fully ready
    log "Waiting for pods to stabilize..."
    sleep 30
    
    # Run tests
    test_hpa
    echo
    
    test_pdb
    echo
    
    test_antiaffinity
    echo
    
    test_monitoring
    echo
    
    # Summary
    log "=== Deployment Summary ==="
    kubectl get all,hpa,pdb,servicemonitor -n $NAMESPACE
    
    success "Phase 3 staging deployment testing complete!"
    
    # Cleanup
    cleanup
}

# Trap to ensure cleanup on exit
PF_PID=""
trap 'if [ -n "$PF_PID" ]; then kill $PF_PID 2>/dev/null || true; fi' EXIT

# Run if called directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi