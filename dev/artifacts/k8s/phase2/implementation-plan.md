# Phase 2: Security & Networking Implementation Plan

## Overview

Phase 2 focuses on network security, ingress configuration, and environment-specific overlays. We'll implement NetworkPolicies, configure TLS ingress, and create overlays for local testing.

## Objectives

1. **Network Security**: Implement NetworkPolicies to control traffic
2. **Ingress Configuration**: Set up HTTPS ingress with cert-manager
3. **Local Testing**: Create local overlay for k3s testing
4. **MinIO Integration**: Verify connectivity to existing MinIO

## Prerequisites Check

- [x] Phase 1 complete (base manifests)
- [x] Ingress-nginx installed
- [x] cert-manager configured
- [x] MinIO running in cluster
- [ ] DNS records for api.scopecreep.productions
- [ ] Cloudflare API token available

## Task Breakdown

### 2.1 NetworkPolicy Implementation

**File**: `k8s/app/base/networkpolicy.yaml`

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: ant-fileserver
spec:
  podSelector:
    matchLabels:
      app: ant-fileserver
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx
    - podSelector: {}  # Allow from same namespace
    ports:
    - protocol: TCP
      port: 8000
  egress:
  - to:
    - namespaceSelector: {}
    ports:
    - protocol: TCP
      port: 53  # DNS
    - protocol: UDP
      port: 53  # DNS
  - to:
    - namespaceSelector:
        matchLabels:
          name: minio
    ports:
    - protocol: TCP
      port: 9000  # MinIO
```

### 2.2 Local Overlay Creation

**Directory**: `k8s/app/overlays/local/`

1. **kustomization.yaml**:
```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: ant-local

bases:
  - ../../base

images:
  - name: ant-fileserver
    newName: ant-fileserver
    newTag: test

configMapGenerator:
  - name: ant-fileserver-config
    behavior: merge
    literals:
      - LOG_LEVEL=debug
      - FLASK_ENV=development
      - STORAGE_ENDPOINT=http://minio.minio.svc.cluster.local:9000
      - STORAGE_BUCKET=ant-fileserver-dev

secretGenerator:
  - name: ant-fileserver-secrets
    files:
      - secrets.env
```

2. **secrets.env.template**:
```env
STORAGE_ACCESS_KEY_ID=your-minio-access-key
STORAGE_SECRET_ACCESS_KEY=your-minio-secret-key
JWT_SECRET_KEY=your-jwt-secret
API_KEY_ROLES={"test-key": ["uploader", "admin"]}
```

### 2.3 Dev Ingress Configuration

**File**: `k8s/app/overlays/dev/ingress.yaml`

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: ant-fileserver
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-cloudflare-prod
    nginx.ingress.kubernetes.io/rewrite-target: /$1
    nginx.ingress.kubernetes.io/proxy-body-size: "50m"
    nginx.ingress.kubernetes.io/rate-limit: "100"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - api.scopecreep.productions
    secretName: ant-fileserver-tls
  rules:
  - host: api.scopecreep.productions
    http:
      paths:
      - path: /api/v1/firmware/(.*)
        pathType: Prefix
        backend:
          service:
            name: ant-fileserver
            port:
              number: 80
```

### 2.4 Testing Scripts

**File**: `scripts/k8s/test-phase2.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "Phase 2 Testing Suite"
echo "===================="

# Test NetworkPolicy
echo "1. Testing NetworkPolicy..."
kubectl apply -k k8s/app/base/
kubectl get networkpolicy -n ant-local

# Test MinIO connectivity
echo "2. Testing MinIO connectivity..."
kubectl run test-minio --rm -it --image=busybox --restart=Never -- \
  wget -O- http://minio.minio.svc.cluster.local:9000/minio/health/live

# Test Ingress
echo "3. Testing Ingress configuration..."
kubectl apply -f k8s/app/overlays/dev/ingress.yaml -n ant --dry-run=server

echo "All Phase 2 tests complete!"
```

## Implementation Order

1. **NetworkPolicy** (30 min)
   - Create networkpolicy.yaml
   - Add to base kustomization
   - Test connectivity

2. **Local Overlay** (45 min)
   - Create overlay structure
   - Configure for local MinIO
   - Test deployment

3. **Dev Ingress** (30 min)
   - Create ingress manifest
   - Verify cert-manager annotations
   - Test with dry-run

4. **Integration Testing** (1 hour)
   - Deploy to local namespace
   - Verify MinIO connectivity
   - Test health endpoints through service

## Success Criteria

- [ ] NetworkPolicy allows ingress-nginx traffic
- [ ] NetworkPolicy allows MinIO egress
- [ ] Local overlay deploys successfully
- [ ] Application connects to MinIO
- [ ] Dev ingress validates correctly
- [ ] Health checks pass through service

## Risk Mitigation

1. **NetworkPolicy too restrictive**: Start permissive, tighten gradually
2. **MinIO connection fails**: Verify service DNS and credentials
3. **Ingress misconfiguration**: Test with kubectl dry-run first
4. **Certificate issues**: Ensure DNS records exist before applying

## Next Steps After Phase 2

- Phase 3: Production readiness (HPA, PDB, monitoring)
- Phase 4: GitOps automation
- Phase 5: Observability (metrics, logging, tracing)