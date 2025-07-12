# ant-fileserver Kubernetes Implementation Task Plan

## Overview

This document provides a detailed, step-by-step plan for implementing the Kubernetes infrastructure for ant-fileserver. Each task includes specific implementation details, validation steps, and rollback procedures.

## Timeline

- **Week 1**: Foundation & Base Infrastructure
- **Week 2**: Environment Configurations & Supporting Resources
- **Week 3**: Testing, Documentation & Production Readiness

## Pre-requisites

- [x] k3s cluster running (verified)
- [x] kubectl configured and working
- [x] MinIO instance available (running in minio namespace)
- [x] Cloudflare tunnel configured (cluster-cloudflared in tunnels namespace)
- [x] Ingress-nginx with MetalLB (192.168.1.240)
- [x] cert-manager with Cloudflare DNS-01 issuer
- [ ] Docker installed for local image builds
- [ ] kubeconform installed for manifest validation
- [x] Git feature branch created: `feature/k8s-infrastructure`
- [x] MinIO credentials exist: ant-fileserver-prod-creds

## Phase 1: Foundation (Days 1-3) ✅ COMPLETE

### 1.1 Base Manifest Creation

#### Task: Create Base Deployment
- [x] Create `k8s/app/base/deployment.yaml`
  ```yaml
  apiVersion: apps/v1
  kind: Deployment
  metadata:
    name: ant-fileserver
    labels:
      app: ant-fileserver
      app.kubernetes.io/name: ant-fileserver
      app.kubernetes.io/component: api
  ```
- [x] Add container specification with image placeholder
- [x] Configure ports (8000)
- [x] Add environment variable references (configMapRef, secretRef)

**Validation**: `kubeconform k8s/app/base/deployment.yaml`

#### Task: Add Security Context
- [x] Add pod-level security context:
  - [x] `runAsNonRoot: true`
  - [x] `runAsUser: 1000`
  - [x] `fsGroup: 1000`
- [x] Add container-level security context:
  - [x] `allowPrivilegeEscalation: false`
  - [x] `readOnlyRootFilesystem: true`
  - [x] `runAsNonRoot: true`
  - [x] `capabilities.drop: [ALL]`
  - [x] `seccompProfile.type: RuntimeDefault`

**Test**: Deploy to local cluster and verify security context is applied

#### Task: Configure Resource Management
- [x] Add resource requests:
  - [x] CPU: 100m
  - [x] Memory: 128Mi
- [x] Add resource limits:
  - [x] CPU: 500m
  - [x] Memory: 512Mi

**Note**: Adjust based on actual application profiling

#### Task: Implement Health Checks
- [x] Add readiness probe:
  - [x] Path: /ready
  - [x] Initial delay: 5s
  - [x] Period: 10s
- [x] Add liveness probe:
  - [x] Path: /health
  - [x] Initial delay: 10s
  - [x] Period: 30s

**Test**: Verify endpoints exist in application code

### 1.2 Service Configuration

#### Task: Create Service Manifest
- [x] Create `k8s/app/base/service.yaml`
- [x] Type: ClusterIP
- [x] Port: 80 → targetPort: 8000
- [x] Add proper labels and selectors

### 1.3 Configuration Management

#### Task: Create ConfigMap Template
- [x] Create `k8s/app/base/configmap.yaml`
- [x] Add base configuration:
  - [x] LOG_LEVEL: info
  - [x] FLASK_ENV: production
  - [x] STORAGE_REGION: us-east-1

#### Task: Create ServiceAccount
- [x] Create `k8s/app/base/serviceaccount.yaml`
- [x] Name: ant-fileserver
- [x] Add necessary labels

### 1.4 Base Kustomization

#### Task: Create Base Kustomization
- [x] Create `k8s/app/base/kustomization.yaml`
- [x] List all resources
- [x] Add common labels
- [x] Add name prefix/suffix if needed

**Validation**: `kubectl kustomize k8s/app/base/`

### 1.5 Fix Missing Dependencies

#### Task: Update requirements.txt
- [x] Add `gunicorn` to requirements.txt
- [x] Specify version: `gunicorn==21.2.0`
- [x] Commit change

## Phase 2: Security & Networking (Days 4-5)

### 2.1 Network Policies

#### Task: Create NetworkPolicy
- [ ] Create `k8s/app/base/networkpolicy.yaml`
- [ ] Configure ingress rules:
  - [ ] Allow from ingress-nginx namespace
  - [ ] Allow from same namespace (for debugging)
- [ ] Configure egress rules:
  - [ ] Allow DNS (port 53)
  - [ ] Allow MinIO (port 9000)

**Test**: Deploy and verify connectivity

### 2.2 RBAC Configuration

#### Task: Define RBAC Rules (if needed)
- [ ] Assess if application needs Kubernetes API access
- [ ] If yes, create Role/RoleBinding
- [ ] If no, document that default ServiceAccount is sufficient

## Phase 3: Environment Overlays (Days 6-10)

### 3.1 Local Environment

#### Task: Create Local Overlay Structure
- [ ] Create `k8s/app/overlays/local/` directory
- [ ] Create `kustomization.yaml`
- [ ] Set namespace: ant-local
- [ ] Configure image: ant-fileserver:latest

#### Task: Local Configuration
- [ ] Create `config-patch.yaml`:
  - [ ] LOG_LEVEL: debug
  - [ ] FLASK_ENV: development
  - [ ] STORAGE_ENDPOINT: http://minio.minio.svc.cluster.local:9000
  - [ ] STORAGE_BUCKET: minio-local

#### Task: Local Secrets Template
- [ ] Create `secrets.yaml.template`
- [ ] Document required values
- [ ] Add to .gitignore: `secrets.yaml`

#### Task: Local MinIO Connection
- [ ] Use existing MinIO in minio namespace
- [ ] Service endpoint: minio.minio.svc.cluster.local:9000
- [ ] Copy credentials pattern from ant-fileserver-prod-creds
- [ ] Create local secrets file (git-ignored)

**Test**: Full local deployment

### 3.2 Dev Environment

#### Task: Update Dev Overlay
- [ ] Modify existing `k8s/app/overlays/dev/kustomization.yaml`
- [ ] Update image tag strategy
- [ ] Add resource constraints patch

#### Task: Dev Ingress
- [ ] Create `ingress.yaml`
- [ ] Host: api-dev.scopecreep.productions
- [ ] Path: /api/v1/firmware/(.*)
- [ ] PathType: Prefix
- [ ] IngressClassName: nginx
- [ ] TLS with cert-manager annotation
- [ ] Certificate issuer: letsencrypt-cloudflare-prod

### 3.3 Staging Environment

#### Task: Create Staging Overlay
- [ ] Create `k8s/app/overlays/staging/` directory
- [ ] Copy structure from dev
- [ ] Increase replicas: 2
- [ ] Add TLS configuration

#### Task: Staging Reliability
- [ ] Create `pdb.yaml` (PodDisruptionBudget)
  - [ ] minAvailable: 1
- [ ] Create `hpa.yaml` (HorizontalPodAutoscaler)
  - [ ] min: 2, max: 5
  - [ ] CPU target: 70%

### 3.4 Production Environment

#### Task: Create Production Overlay
- [ ] Create `k8s/app/overlays/prod/` directory
- [ ] Configure production values
- [ ] Strict resource limits
- [ ] Add anti-affinity rules

#### Task: Production Scaling
- [ ] Configure HPA:
  - [ ] min: 2, max: 10
  - [ ] CPU target: 70%
  - [ ] Memory target: 80%
- [ ] Configure PDB:
  - [ ] minAvailable: 2

#### Task: Production Monitoring
- [ ] Add Prometheus annotations
- [ ] Configure scrape settings
- [ ] Document metric endpoints

## Phase 4: Validation & Testing (Days 11-13)

### 4.1 Manifest Validation

#### Task: Automated Validation
- [ ] Create `scripts/validate-manifests.sh`
- [ ] Run kubeconform on all manifests
- [ ] Check Kubernetes API deprecations
- [ ] Validate kustomize builds

### 4.2 Deployment Testing

#### Task: Local Testing Script
- [ ] Create `scripts/deploy-local.sh`
- [ ] Include namespace creation
- [ ] Apply manifests
- [ ] Wait for rollout
- [ ] Run smoke tests

#### Task: Integration Tests
- [ ] Test MinIO connectivity
- [ ] Test API endpoints
- [ ] Verify health checks
- [ ] Check resource usage

### 4.3 Documentation

#### Task: Deployment Guide
- [ ] Document deployment process for each environment
- [ ] Include rollback procedures
- [ ] Add troubleshooting section

#### Task: Operations Runbook
- [ ] Scaling procedures
- [ ] Update procedures
- [ ] Incident response
- [ ] Monitoring setup

## Phase 5: CI/CD Integration (Days 14-15)

### 5.1 GitHub Actions Updates

#### Task: Update CI Pipeline
- [ ] Add manifest validation step
- [ ] Add kustomize build test
- [ ] Update image tagging strategy

#### Task: Deployment Automation
- [ ] Dev: Auto-deploy on merge to dev
- [ ] Staging: Auto-deploy on merge to staging
- [ ] Prod: Manual approval required

### 5.2 GitOps Setup

#### Task: Document GitOps Flow
- [ ] Branch protection rules
- [ ] PR requirements
- [ ] Deployment triggers
- [ ] Rollback procedures

## Success Criteria

### Phase 1 Complete When:
- All base manifests created and validated
- Security context properly configured
- Resource limits defined
- Health checks working

### Phase 2 Complete When:
- Network policies tested
- Security scanning passed
- RBAC documented

### Phase 3 Complete When:
- All environment overlays created
- Each environment deployable
- Configuration properly separated

### Phase 4 Complete When:
- All validation passing
- Deployment tested in each environment
- Documentation complete

### Phase 5 Complete When:
- CI/CD pipeline updated
- GitOps workflow documented
- Production deployment successful

## Rollback Plan

For any phase that fails:
1. Identify the specific commit that introduced the issue
2. Revert the commit: `git revert <commit-hash>`
3. Re-run validation and tests
4. Document the issue and fix
5. Create new commit with corrected implementation

## Notes

- Each task should be a separate commit
- Run validation after each commit
- Test deployments incrementally
- Document any deviations from plan

## Tracking

Use this checklist to track progress. Check off items as completed and note any issues encountered.