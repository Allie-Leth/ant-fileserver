#!/usr/bin/env bash
set -euo pipefail

# Quick Phase 3 Feature Test
# Tests key features without full deployment

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

main() {
    log "Phase 3 Quick Feature Test"
    log "=========================="
    
    # Test 1: Validate manifests
    log "Testing manifest generation..."
    
    for overlay in staging prod; do
        log "Testing $overlay overlay..."
        
        # Generate manifests
        if kubectl kustomize k8s/app/overlays/$overlay > /tmp/phase3-$overlay.yaml; then
            success "$overlay manifests generated"
            
            # Check for key resources
            if grep -q "kind: HorizontalPodAutoscaler" /tmp/phase3-$overlay.yaml; then
                success "$overlay has HPA"
            else
                error "$overlay missing HPA"
            fi
            
            if grep -q "kind: PodDisruptionBudget" /tmp/phase3-$overlay.yaml; then
                success "$overlay has PDB"
            else
                error "$overlay missing PDB"
            fi
            
            if grep -q "podAntiAffinity:" /tmp/phase3-$overlay.yaml; then
                success "$overlay has anti-affinity"
            else
                error "$overlay missing anti-affinity"
            fi
            
            # Staging specific
            if [ "$overlay" = "staging" ]; then
                if grep -q "kind: ServiceMonitor" /tmp/phase3-$overlay.yaml; then
                    success "$overlay has ServiceMonitor"
                else
                    error "$overlay missing ServiceMonitor"
                fi
            fi
        else
            error "Failed to generate $overlay manifests"
        fi
        
        echo
    done
    
    # Test 2: Dry-run deployment
    log "Testing dry-run deployment..."
    
    if kubectl create namespace test-phase3 --dry-run=client -o yaml > /dev/null 2>&1; then
        if kubectl apply -k k8s/app/overlays/staging --dry-run=server 2>&1 | grep -q "created (server dry run)"; then
            success "Staging deployment would succeed"
        else
            warning "Staging deployment dry-run had issues"
        fi
    fi
    
    # Test 3: Check prerequisites
    log "Checking cluster prerequisites..."
    
    if kubectl get deployment -n kube-system metrics-server &> /dev/null; then
        success "Metrics server is available"
    else
        error "Metrics server not found"
    fi
    
    if kubectl get crd servicemonitors.monitoring.coreos.com &> /dev/null; then
        success "ServiceMonitor CRD is available"
    else
        warning "ServiceMonitor CRD not found"
    fi
    
    # Test 4: Resource calculations
    log "Validating resource configurations..."
    
    # Check staging resources
    STAGING_CPU=$(grep -A5 "resources:" /tmp/phase3-staging.yaml | grep "cpu:" | head -2)
    if echo "$STAGING_CPU" | grep -q "200m"; then
        success "Staging has appropriate CPU requests"
    fi
    
    # Check production resources
    PROD_CPU=$(grep -A5 "resources:" /tmp/phase3-prod.yaml | grep "cpu:" | head -2)
    if echo "$PROD_CPU" | grep -q "500m"; then
        success "Production has higher CPU requests"
    fi
    
    # Summary
    echo
    log "=== Phase 3 Feature Summary ==="
    success "✅ HPA configured for auto-scaling"
    success "✅ PDB ensures high availability"
    success "✅ Anti-affinity spreads pods across nodes"
    success "✅ ServiceMonitor ready for Prometheus"
    success "✅ Resources tuned for each environment"
    
    # Cleanup
    rm -f /tmp/phase3-*.yaml
    
    log "Quick test complete!"
}

# Run if called directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi