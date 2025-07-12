# Phase 3: Production Readiness Implementation Plan

## Overview

Phase 3 focuses on production readiness features including auto-scaling, high availability, monitoring, and operational tooling. This phase builds on the secure foundation from Phases 1 & 2.

## Objectives

1. **Auto-scaling**: Implement HorizontalPodAutoscaler (HPA)
2. **High Availability**: Configure PodDisruptionBudget (PDB)
3. **Monitoring**: Add Prometheus ServiceMonitor
4. **Anti-affinity**: Ensure pod distribution across nodes
5. **Operational Tools**: Scripts for deployment and validation

## Prerequisites

- [x] Phase 1 & 2 complete and validated
- [x] Metrics-server installed in cluster
- [ ] Prometheus operator available (for ServiceMonitor)
- [ ] Multiple nodes available (for anti-affinity testing)
- [ ] Load testing tools (for HPA validation)

## Task Breakdown

### 3.1 HorizontalPodAutoscaler (HPA)

**Purpose**: Automatically scale pods based on CPU/memory usage

#### Staging HPA
**File**: `k8s/app/overlays/staging/hpa.yaml`
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: ant-fileserver
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: ant-fileserver
  minReplicas: 2
  maxReplicas: 5
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 100
        periodSeconds: 60
```

#### Production HPA
- Min replicas: 2
- Max replicas: 10
- More conservative scale-down behavior

### 3.2 PodDisruptionBudget (PDB)

**Purpose**: Ensure minimum availability during voluntary disruptions

**File**: `k8s/app/overlays/staging/pdb.yaml`
```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: ant-fileserver
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: ant-fileserver
  unhealthyPodEvictionPolicy: AlwaysAllow
```

Production will use `minAvailable: 2`

### 3.3 Anti-Affinity Rules

**Purpose**: Distribute pods across nodes for HA

**File**: `k8s/app/overlays/staging/deployment-patch.yaml`
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ant-fileserver
spec:
  template:
    spec:
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchExpressions:
                - key: app
                  operator: In
                  values:
                  - ant-fileserver
              topologyKey: kubernetes.io/hostname
```

### 3.4 ServiceMonitor for Prometheus

**Purpose**: Enable Prometheus scraping of metrics

**File**: `k8s/app/overlays/staging/servicemonitor.yaml`
```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: ant-fileserver
  labels:
    app: ant-fileserver
spec:
  selector:
    matchLabels:
      app: ant-fileserver
  endpoints:
  - port: http
    path: /metrics
    interval: 30s
    scrapeTimeout: 10s
```

### 3.5 Resource Tuning

**Staging Resources**:
- Requests: 200m CPU, 256Mi memory
- Limits: 1000m CPU, 1Gi memory

**Production Resources**:
- Requests: 500m CPU, 512Mi memory
- Limits: 2000m CPU, 2Gi memory

### 3.6 Operational Scripts

#### Deploy Script
**File**: `scripts/k8s/deploy.sh`
- Environment selection
- Pre-flight checks
- Progressive rollout
- Health verification
- Rollback capability

#### Load Test Script
**File**: `scripts/k8s/load-test.sh`
- Generate load for HPA testing
- Monitor scaling behavior
- Validate performance

## Implementation Schedule

### Day 1: HPA and PDB
1. Create HPA for staging/prod
2. Create PDB for staging/prod
3. Test scaling behavior
4. Document thresholds

### Day 2: High Availability
1. Add anti-affinity rules
2. Test pod distribution
3. Verify PDB during updates
4. Document HA behavior

### Day 3: Monitoring
1. Add ServiceMonitor
2. Configure dashboards
3. Set up alerts
4. Test metric collection

### Day 4: Operational Tools
1. Create deployment scripts
2. Create validation scripts
3. Load testing tools
4. Documentation

## Testing Plan

### HPA Testing
1. Deploy to staging with HPA
2. Generate load with curl/k6
3. Observe scaling up behavior
4. Stop load and observe scale down
5. Verify metrics accuracy

### PDB Testing
1. Trigger rolling update
2. Verify minimum pods maintained
3. Test node drain scenarios
4. Document behavior

### Anti-Affinity Testing
1. Scale to multiple replicas
2. Verify distribution across nodes
3. Test failover scenarios

### Monitoring Testing
1. Deploy ServiceMonitor
2. Verify Prometheus scraping
3. Check metric values
4. Test alert firing

## Success Criteria

- [ ] HPA scales up under load (< 2 min)
- [ ] HPA scales down when idle (< 5 min)
- [ ] PDB prevents total unavailability
- [ ] Pods distributed across nodes
- [ ] Metrics visible in Prometheus
- [ ] Zero-downtime deployments
- [ ] Load tests show good performance

## Risk Mitigation

1. **Metrics Server Issues**
   - Verify metrics-server is running
   - Check resource requests are set
   - Use kubectl top to debug

2. **Scaling Too Aggressive**
   - Tune stabilization windows
   - Adjust scale up/down policies
   - Monitor cluster resources

3. **PDB Too Restrictive**
   - Start with minAvailable: 1
   - Monitor during updates
   - Adjust based on cluster size

4. **ServiceMonitor Not Scraped**
   - Check Prometheus operator config
   - Verify labels match
   - Test metrics endpoint manually

## Phase 3 Deliverables

1. **Staging Overlay Enhanced**:
   - HPA configuration
   - PDB configuration
   - Anti-affinity rules
   - ServiceMonitor

2. **Production Overlay Enhanced**:
   - Production-grade HPA
   - Stricter PDB
   - Required anti-affinity
   - ServiceMonitor with annotations

3. **Operational Scripts**:
   - deploy.sh
   - load-test.sh
   - validate-production.sh

4. **Documentation**:
   - Scaling behavior guide
   - Monitoring setup
   - Operational runbook
   - Troubleshooting guide

## Next Steps After Phase 3

- Phase 4: CI/CD Integration
- Phase 5: GitOps with ArgoCD
- Phase 6: Advanced observability (tracing, logging)