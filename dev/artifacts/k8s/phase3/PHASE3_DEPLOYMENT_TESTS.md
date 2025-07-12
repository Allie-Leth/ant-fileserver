# Phase 3 Deployment Testing Guide

## Overview

This guide covers the deployment and testing procedures for Phase 3 production readiness features: HPA, PDB, Anti-affinity, and Monitoring.

## Test Scripts Created

### 1. Static Validation Tests
**Script**: `scripts/k8s/test-phase3-production.sh`
- Validates manifest structure
- Checks HPA/PDB configurations
- Verifies anti-affinity rules
- Tests ServiceMonitor setup
- **Status**: ✅ All 33 tests passing

### 2. Deployment Testing
**Script**: `scripts/k8s/deploy-phase3-staging.sh`
- Deploys to staging namespace
- Tests HPA metrics collection
- Validates PDB enforcement
- Checks pod distribution
- Verifies ServiceMonitor

### 3. Load Testing
**Script**: `scripts/k8s/load-test-hpa.sh`
- Generates controlled load
- Monitors HPA scaling behavior
- Shows real-time pod scaling
- Tests scale-up and scale-down

## Testing Procedures

### Step 1: Run Static Tests
```bash
./scripts/k8s/test-phase3-production.sh
```
Expected: All 33 tests should pass

### Step 2: Deploy to Staging
```bash
./scripts/k8s/deploy-phase3-staging.sh
```
This will:
1. Create `ant-staging` namespace
2. Deploy staging overlay
3. Run automated tests
4. Show deployment summary

### Step 3: Load Testing (Optional)
```bash
# Install hey for better load testing
go install github.com/rakyll/hey@latest

# Run load test (5 minutes default)
./scripts/k8s/load-test-hpa.sh ant-staging 300

# Or shorter test (2 minutes)
./scripts/k8s/load-test-hpa.sh ant-staging 120
```

## Expected Behaviors

### HPA Scaling
1. **Initial State**: 2 replicas (minimum)
2. **Under Load**: Should scale up to 5 replicas when CPU > 70%
3. **Cool Down**: Gradually scale back after 5 minutes
4. **Metrics**: Should show CPU and memory utilization

### PDB Protection
1. **Normal Operations**: Allows pod evictions
2. **Critical State**: Blocks evictions that would violate minAvailable
3. **Rolling Updates**: Ensures service continuity

### Anti-Affinity
1. **Staging**: Preferred distribution (best effort)
2. **Production**: Required distribution (enforced)
3. **Result**: Pods spread across available nodes

### Monitoring
1. **ServiceMonitor**: Created in staging namespace
2. **Prometheus**: Should discover and scrape metrics
3. **Endpoint**: Expects /metrics on port 8000

## Manual Verification Commands

```bash
# Watch HPA scaling
kubectl get hpa -n ant-staging -w

# Check pod distribution
kubectl get pods -n ant-staging -o wide

# Test PDB
kubectl get pdb -n ant-staging
kubectl describe pdb ant-fileserver -n ant-staging

# Check metrics
kubectl top pods -n ant-staging
kubectl top nodes

# View ServiceMonitor
kubectl get servicemonitor -n ant-staging
kubectl describe servicemonitor ant-fileserver -n ant-staging
```

## Troubleshooting

### HPA Not Scaling
1. Check metrics-server: `kubectl top nodes`
2. Verify resource requests are set
3. Check HPA targets: `kubectl describe hpa -n ant-staging`

### PDB Issues
1. Ensure enough replicas are running
2. Check pod health status
3. Verify selector matches pods

### Anti-Affinity Not Working
1. Need multiple nodes in cluster
2. Check pod events for scheduling issues
3. Verify affinity rules in pod spec

### Monitoring Issues
1. Check Prometheus operator is installed
2. Verify ServiceMonitor labels match Prometheus selector
3. Ensure app exposes /metrics endpoint

## Next Steps

After successful testing:
1. Deploy to production with similar process
2. Set up Grafana dashboards
3. Configure alerting rules
4. Document scaling policies
5. Create runbooks for operations