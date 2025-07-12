# ant-fileserver Kubernetes Infrastructure

## Overview

This directory contains the complete Kubernetes infrastructure design and implementation plan for the ant-fileserver API service. The ant-fileserver is a Flask-based OTA firmware service that stores binaries in MinIO and exposes a secure REST API to IoT devices.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          External Traffic                            │
│                         (Internet Users)                             │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
┌───────────────────────────────┴─────────────────────────────────────┐
│                    Cloudflare Tunnel (cloudflared)                   │
│                    Deployment: cluster-cloudflared                   │
│                    Namespace: tunnels                                │
│                    Replicas: 2 (HA)                                  │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
┌───────────────────────────────┴─────────────────────────────────────┐
│                      Ingress Controller (nginx)                      │
│                    IngressClass: nginx                               │
│                    MetalLB: lan-pool                                 │
│                    ModSecurity: Enabled                              │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
┌───────────────────────────────┴─────────────────────────────────────┐
│                         Ingress Resource                             │
│                    Host: api.scopecreep.productions                  │
│                    Path: /api/v1/firmware/*                          │
│                    TLS: cert-manager (Let's Encrypt)                 │
│                    Issuer: letsencrypt-cloudflare-prod              │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
┌───────────────────────────────┴─────────────────────────────────────┐
│                      Service (ant-fileserver)                        │
│                      Type: ClusterIP                                 │
│                      Port: 80 → 8000                                 │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
    ┌───────────────────────────┴───────────────────────────┐
    │                                                       │
┌───┴────────────────┐  ┌──────────────────┐  ┌───────────┴──────────┐
│   Deployment       │  │  ConfigMap       │  │   Secret             │
│   ant-fileserver   │──│  (app-config)    │  │  (minio-creds)       │
│                    │  │                  │  │                      │
│ Replicas:          │  │ - LOG_LEVEL      │  │ - ACCESS_KEY_ID      │
│ - Local: 1         │  │ - FLASK_ENV      │  │ - SECRET_ACCESS_KEY  │
│ - Dev: 1-3         │  │ - STORAGE_BUCKET │  │ - JWT_SECRET_KEY     │
│ - Staging: 2-5     │  │ - STORAGE_REGION │  │ - API_KEY_ROLES      │
│ - Prod: 2-10       │  │                  │  │                      │
└────────────────────┘  └──────────────────┘  └──────────────────────┘
         │
┌────────┴────────┐
│     Pod         │
│                 │     ┌─────────────────────────────────────────────┐
│ ┌─────────────┐ │     │            MinIO Object Storage              │
│ │ Container   │ │────▶│                                             │
│ │ ant-server  │ │     │  Buckets:                                   │
│ │             │ │     │  - minio-dev/ant-fileserver/*               │
│ │ Resources:  │ │     │  - minio-staging/ant-fileserver/*           │
│ │ CPU: 100m   │ │     │  - minio-prod/ant-fileserver/*              │
│ │ Mem: 128Mi  │ │     │                                             │
│ └─────────────┘ │     └─────────────────────────────────────────────┘
│                 │
│ Security:       │
│ - Non-root      │
│ - Read-only FS  │
│ - No escalation │
└─────────────────┘
```

## Component Details

### 1. **Deployment**
- **Container**: Python 3.12-slim with Gunicorn
- **Port**: 8000 (HTTP)
- **Security Context**: 
  - Runs as user 1000 (non-root)
  - Read-only root filesystem
  - All capabilities dropped
  - No privilege escalation allowed
- **Health Checks**:
  - Liveness: GET /health
  - Readiness: GET /ready
- **Update Strategy**: RollingUpdate (maxSurge: 1, maxUnavailable: 0)

### 2. **Service**
- **Type**: ClusterIP (internal only)
- **Port Mapping**: 80 → 8000
- **Session Affinity**: None (stateless application)

### 3. **Configuration**
- **ConfigMap**: Non-sensitive environment variables
  - LOG_LEVEL (debug/info/warning/error)
  - FLASK_ENV (development/production)
  - STORAGE_ENDPOINT (MinIO URL)
  - STORAGE_BUCKET (bucket name)
  - STORAGE_REGION (us-east-1)
  
- **Secret**: Sensitive credentials
  - STORAGE_ACCESS_KEY_ID
  - STORAGE_SECRET_ACCESS_KEY
  - JWT_SECRET_KEY
  - API_KEY_ROLES (JSON mapping)

### 4. **Networking**
- **Cloudflare Tunnel**: 
  - External traffic entry point
  - Managed tunnel with sealed token
  - High availability with 2 replicas
  
- **Ingress Controller**: 
  - nginx with ModSecurity enabled
  - MetalLB for load balancing
  - OWASP Core Rule Set enabled
  
- **Ingress Resource**:
  - Host-based routing (api.scopecreep.productions)
  - Path: /api/v1/firmware/*
  - TLS via cert-manager with Cloudflare DNS-01 challenge
  - Rate limiting annotations
  
- **NetworkPolicy**: 
  - Ingress: Allow from ingress-nginx namespace only
  - Egress: Allow to MinIO service and DNS

### 5. **Scaling & Reliability**
- **HorizontalPodAutoscaler** (staging/prod):
  - Min replicas: 2
  - Max replicas: 10
  - Target CPU: 70%
  - Target Memory: 80%
  
- **PodDisruptionBudget** (staging/prod):
  - minAvailable: 1
  - Ensures availability during updates

### 6. **Storage**
- **Application**: Stateless (no PVC needed)
- **MinIO Backend**: 
  - All firmware binaries stored in object storage
  - Bucket per environment with ant-fileserver prefix
  - No local persistence required

## Environment Matrix

| Component | Local | Dev | Staging | Production |
|-----------|-------|-----|---------|------------|
| **Namespace** | ant-local | ant | ant-staging | ant-prod |
| **Replicas** | 1 | 1-3 | 2-5 | 2-10 |
| **Image Tag** | latest | dev | staging | v*.*.* |
| **MinIO Endpoint** | minio.minio.svc | minio-dev.example.com | minio-staging.example.com | minio.example.com |
| **MinIO Bucket** | minio-local | minio-dev | minio-staging | minio-prod |
| **Resource Limits** | None | Low | Medium | High |
| **HPA** | ❌ | ❌ | ✅ | ✅ |
| **PDB** | ❌ | ❌ | ✅ | ✅ |
| **NetworkPolicy** | ❌ | ✅ | ✅ | ✅ |
| **Ingress** | Optional | ✅ | ✅ | ✅ |
| **TLS** | ❌ | ✅ (Let's Encrypt) | ✅ (Let's Encrypt) | ✅ (Let's Encrypt) |
| **Cloudflare Tunnel** | ❌ | ✅ | ✅ | ✅ |
| **Monitoring** | ❌ | Basic | Full | Full |

## Directory Structure

```
k8s/
├── app/
│   ├── base/                    # Base manifests (common to all envs)
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   ├── serviceaccount.yaml
│   │   ├── configmap.yaml
│   │   ├── networkpolicy.yaml
│   │   └── kustomization.yaml
│   └── overlays/
│       ├── local/              # Local k3s development
│       │   ├── config.yaml
│       │   ├── secrets.yaml    # Git-ignored
│       │   └── kustomization.yaml
│       ├── dev/                # Development cluster
│       │   ├── config.yaml
│       │   ├── ingress.yaml
│       │   └── kustomization.yaml
│       ├── staging/            # Staging cluster
│       │   ├── config.yaml
│       │   ├── ingress.yaml
│       │   ├── pdb.yaml
│       │   ├── hpa.yaml
│       │   └── kustomization.yaml
│       └── prod/               # Production cluster
│           ├── config.yaml
│           ├── ingress.yaml
│           ├── pdb.yaml
│           ├── hpa.yaml
│           └── kustomization.yaml
```

## Quick Start (Local k3s)

```bash
# 1. Ensure k3s is running
kubectl cluster-info

# 2. Create namespace
kubectl create namespace ant-local

# 3. Create secrets (copy from template)
cp k8s/app/overlays/local/secrets.yaml.template k8s/app/overlays/local/secrets.yaml
# Edit secrets.yaml with your MinIO credentials
# MinIO endpoint: minio.minio.svc.cluster.local:9000

# 4. Deploy application
kubectl apply -k k8s/app/overlays/local/

# 5. Check deployment
kubectl -n ant-local get pods
kubectl -n ant-local logs -l app=ant-fileserver

# 6. Port forward for testing (no ingress in local)
kubectl -n ant-local port-forward svc/ant-fileserver 8080:80

# Test the API
curl http://localhost:8080/health
```

## Development/Staging/Production Deployment

For non-local environments, the application is exposed via:
1. **Cloudflare Tunnel** → 2. **Ingress-nginx** → 3. **Service** → 4. **Pods**

### Ingress Configuration

All ingresses follow this pattern:
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: ant-fileserver
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-cloudflare-prod
    nginx.ingress.kubernetes.io/rewrite-target: /$1
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

## GitOps Workflow

1. **Feature Development**: Create feature branch from `dev`
2. **Testing**: Deploy to local k3s using local overlay
3. **Dev Deployment**: Merge to `dev` branch → auto-deploy to dev cluster
4. **Staging**: Merge dev → staging → auto-deploy to staging cluster
5. **Production**: Merge staging → main → manual approval → deploy to prod

## Best Practices Applied

1. **Security**:
   - Pod Security Standards (Restricted profile)
   - Non-root containers
   - Read-only root filesystem
   - Network policies for isolation
   - Secrets management (SealedSecrets in prod)

2. **Reliability**:
   - Health checks (liveness & readiness)
   - Resource limits prevent noisy neighbors
   - PodDisruptionBudget for availability
   - Anti-affinity rules for spreading

3. **Observability**:
   - Structured JSON logging
   - Prometheus metrics exposed
   - Distributed tracing ready
   - Resource monitoring via metrics-server

4. **Scalability**:
   - Horizontal Pod Autoscaler
   - Stateless design
   - Efficient resource requests

5. **Maintainability**:
   - Kustomize for configuration management
   - Clear environment separation
   - Declarative GitOps approach
   - Comprehensive documentation

## Troubleshooting

### Pod not starting
```bash
# Check pod status
kubectl -n <namespace> describe pod <pod-name>

# Check logs
kubectl -n <namespace> logs <pod-name>

# Check events
kubectl -n <namespace> get events --sort-by='.lastTimestamp'
```

### MinIO connection issues
```bash
# Test MinIO connectivity
kubectl -n <namespace> exec -it <pod-name> -- curl -I http://<minio-endpoint>:9000/minio/health/live

# Check credentials
kubectl -n <namespace> get secret ant-fileserver-secrets -o yaml
```

### Resource constraints
```bash
# Check resource usage
kubectl -n <namespace> top pods

# Check HPA status
kubectl -n <namespace> get hpa
```

## Infrastructure Dependencies

This deployment relies on the following existing infrastructure components:

### 1. **Cloudflare Tunnel (cloudflared)**
- **Namespace**: `tunnels`
- **Deployment**: `cluster-cloudflared` (2 replicas)
- **Purpose**: Secure tunnel from Cloudflare edge to cluster
- **Configuration**: Managed via sealed secret `cluster-cloudflared-token`

### 2. **Ingress-nginx Controller**
- **Namespace**: `ingress-nginx`
- **LoadBalancer IP**: `192.168.1.240` (MetalLB)
- **Features**: 
  - ModSecurity enabled with OWASP Core Rule Set
  - Prometheus metrics on port 10254
  - Admission webhooks enabled

### 3. **cert-manager**
- **Namespace**: `cert-manager`
- **ClusterIssuers**:
  - `letsencrypt-cloudflare-prod`: DNS-01 challenge via Cloudflare API
  - `letsencrypt-prod`: HTTP-01 challenge (backup)
- **DNS Zone**: `scopecreep.productions`

### 4. **MinIO Object Storage**
- **Namespace**: `minio`
- **Service**: `minio.minio.svc.cluster.local:9000`
- **Existing Secrets**: `ant-fileserver-prod-creds`
- **IAM Policy**: Already configured for ant-fileserver access

### 5. **External-DNS** (Optional)
- **Namespace**: `external-dns`
- **Purpose**: Automatic DNS record creation
- **Provider**: Cloudflare

## Traffic Flow

1. **External User** → Cloudflare Edge
2. **Cloudflare Edge** → Cloudflare Tunnel (via secure tunnel)
3. **Cloudflared Pod** → Ingress-nginx Controller (HTTPS)
4. **Ingress-nginx** → ant-fileserver Service (HTTP)
5. **Service** → ant-fileserver Pods
6. **Pods** → MinIO (for object storage)

## Next Steps

See [task_plan.md](./task_plan.md) for the detailed implementation plan and checklist.