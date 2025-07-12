#!/usr/bin/env bash
set -euo pipefail

# HPA Load Testing Script
# Generates load to test auto-scaling behavior

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

NAMESPACE="${1:-ant-staging}"
DURATION="${2:-300}" # 5 minutes default
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

# Monitor HPA and pods in background
monitor_scaling() {
    log "Starting HPA monitor in background..."
    
    while true; do
        clear
        echo -e "${BLUE}=== HPA Scaling Monitor ===${NC}"
        echo -e "Time: $(date +'%H:%M:%S')"
        echo
        
        # Show HPA status
        kubectl get hpa -n $NAMESPACE --no-headers | while read line; do
            echo -e "${GREEN}HPA:${NC} $line"
        done
        echo
        
        # Show pod count and status
        POD_COUNT=$(kubectl get pods -n $NAMESPACE -l app=$DEPLOYMENT --no-headers | wc -l)
        READY_COUNT=$(kubectl get pods -n $NAMESPACE -l app=$DEPLOYMENT --no-headers | grep -c "Running" || true)
        echo -e "${GREEN}Pods:${NC} $READY_COUNT/$POD_COUNT ready"
        echo
        
        # Show pods with node distribution
        echo -e "${GREEN}Pod Distribution:${NC}"
        kubectl get pods -n $NAMESPACE -l app=$DEPLOYMENT -o wide --no-headers | \
            awk '{print $1, $3, $7}' | column -t
        echo
        
        # Show resource usage if available
        echo -e "${GREEN}Resource Usage:${NC}"
        kubectl top pods -n $NAMESPACE -l app=$DEPLOYMENT --no-headers 2>/dev/null || \
            echo "Metrics not yet available"
        
        sleep 10
    done
}

# Generate load using different methods
generate_load() {
    local target_url="$1"
    
    log "Starting load generation to $target_url"
    log "Duration: ${DURATION} seconds"
    
    # Method 1: Using hey if available
    if command -v hey &> /dev/null; then
        log "Using hey for load testing..."
        
        # Gradually increase load
        log "Phase 1: Warming up (30s, 10 concurrent)"
        hey -z 30s -c 10 -q 50 "$target_url/health" &
        
        sleep 35
        
        log "Phase 2: Increasing load (60s, 50 concurrent)"
        hey -z 60s -c 50 -q 100 "$target_url/health" &
        hey -z 60s -c 50 -q 100 "$target_url/ready" &
        
        sleep 65
        
        log "Phase 3: Peak load (${DURATION}s, 100 concurrent)"
        hey -z "${DURATION}s" -c 100 -q 200 "$target_url/health" &
        hey -z "${DURATION}s" -c 100 -q 200 "$target_url/ready" &
        
        wait
        
    # Method 2: Using curl in a loop
    else
        warning "hey not found, using curl for basic load testing"
        log "This will be less effective for HPA testing"
        
        END_TIME=$(($(date +%s) + DURATION))
        CONCURRENT=50
        
        for i in $(seq 1 $CONCURRENT); do
            (
                while [ $(date +%s) -lt $END_TIME ]; do
                    curl -s "$target_url/health" > /dev/null
                    curl -s "$target_url/ready" > /dev/null
                done
            ) &
        done
        
        wait
    fi
    
    success "Load generation complete"
}

# Main execution
main() {
    log "HPA Load Testing for $DEPLOYMENT in $NAMESPACE"
    log "============================================="
    
    # Check if deployment exists
    if ! kubectl get deployment $DEPLOYMENT -n $NAMESPACE &> /dev/null; then
        error "Deployment $DEPLOYMENT not found in namespace $NAMESPACE"
        exit 1
    fi
    
    # Check HPA exists
    if ! kubectl get hpa $DEPLOYMENT -n $NAMESPACE &> /dev/null; then
        error "HPA $DEPLOYMENT not found in namespace $NAMESPACE"
        exit 1
    fi
    
    # Get initial state
    log "Initial state:"
    kubectl get hpa,deployment -n $NAMESPACE
    
    # Start monitoring in background
    monitor_scaling &
    MONITOR_PID=$!
    
    # Setup port forward
    log "Setting up port forward..."
    kubectl port-forward -n $NAMESPACE svc/$DEPLOYMENT 8888:80 &
    PF_PID=$!
    sleep 5
    
    # Generate load
    generate_load "http://localhost:8888"
    
    # Cool down period
    log "Entering cool-down period (2 minutes)..."
    sleep 120
    
    # Final state
    log "Final state:"
    kubectl get hpa,deployment -n $NAMESPACE
    
    # Cleanup
    log "Cleaning up..."
    kill $MONITOR_PID 2>/dev/null || true
    kill $PF_PID 2>/dev/null || true
    
    success "Load testing complete!"
    
    # Show scaling summary
    log "=== Scaling Summary ==="
    kubectl describe hpa $DEPLOYMENT -n $NAMESPACE | grep -A10 "Events:" || \
        log "No scaling events found"
}

# Trap to ensure cleanup
trap 'kill $MONITOR_PID $PF_PID 2>/dev/null || true' EXIT

# Run if called directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi