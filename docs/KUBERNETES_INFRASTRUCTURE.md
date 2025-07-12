# Kubernetes Infrastructure

## Overview

The ANT Fileserver uses a modern Kubernetes deployment architecture with Kustomize for configuration management. The infrastructure is designed for high availability, security, and scalability across multiple environments.

## Architecture Overview

```
k8s/app/
├── base/                         # Base configuration
│   ├── deployment.yaml          # Core deployment
│   ├── service.yaml            # Service definition
│   ├── serviceaccount.yaml     # RBAC
│   ├── configmap.yaml          # Configuration
│   ├── networkpolicy.yaml      # Network security
│   └── kustomization.yaml      # Base kustomization
└── overlays/                    # Environment-specific
    ├── local/                   # Local development
    ├── dev/                     # Development cluster
    ├── staging/                 # Staging environment
    └── prod/                    # Production environment
```

## Base Configuration

### Deployment (`base/deployment.yaml`)

Core deployment with security defaults:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ant-fileserver
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ant-fileserver
  template:
    spec:
      serviceAccountName: ant-fileserver
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
      containers:
      - name: ant-fileserver
        image: ant-fileserver:latest
        ports:
        - containerPort: 8000
          name: http
        securityContext:
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          capabilities:
            drop: ["ALL"]
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 500m
            memory: 512Mi
```

### Service (`base/service.yaml`)

ClusterIP service for internal access:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: ant-fileserver
spec:
  type: ClusterIP
  selector:
    app: ant-fileserver
  ports:
  - port: 80
    targetPort: http
    protocol: TCP
```

### NetworkPolicy (`base/networkpolicy.yaml`)

Zero-trust network security:

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
    ports:
    - protocol: TCP
      port: 8000
  egress:
  - to:
    - namespaceSelector: {}
    ports:
    - protocol: TCP
      port: 53  # DNS
  - to:
    - namespaceSelector: {}
    ports:
    - protocol: TCP
      port: 9000  # MinIO
```

## Environment Overlays

### Local Development (`overlays/local/`)

Simplified configuration for local testing:
- NetworkPolicy removed
- NodePort service for easy access
- Debug logging enabled
- Single replica

### Development (`overlays/dev/`)

Development cluster configuration:
- 2 replicas
- Basic resource limits
- Development ingress host
- Relaxed security policies

### Staging (`overlays/staging/`)

Pre-production environment:
- **HorizontalPodAutoscaler**: 2-5 replicas
- **PodDisruptionBudget**: minAvailable: 1
- **Anti-affinity**: Preferred pod spreading
- **ServiceMonitor**: Prometheus integration
- **Resources**: Higher limits than dev
- **Ingress**: Staging domain with IP whitelist

Key components:

```yaml
# HPA Configuration
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: ant-fileserver
spec:
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
```

### Production (`overlays/prod/`)

Production configuration with maximum reliability:
- **HorizontalPodAutoscaler**: 2-10 replicas
- **PodDisruptionBudget**: minAvailable: 2
- **Anti-affinity**: Required pod spreading
- **Resources**: Production-grade limits
- **Security**: Enhanced headers and policies
- **Monitoring**: Full observability

## Security Features

### 1. Pod Security Standards

All pods run with the Restricted security standard:
- Non-root user (UID 1000)
- Read-only root filesystem
- No privilege escalation
- All capabilities dropped
- Seccomp and AppArmor profiles

### 2. Network Policies

- **Ingress**: Only from ingress-nginx namespace
- **Egress**: Limited to DNS, MinIO, and HTTPS
- **Default deny**: All other traffic blocked

### 3. RBAC

Minimal ServiceAccount permissions:
```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: ant-fileserver
automountServiceAccountToken: false
```

### 4. Secret Management

- Secrets mounted as volumes
- Environment variables for non-sensitive config
- Integration with external secret managers supported

## High Availability Features

### 1. Multi-Replica Deployments

- Minimum 2 replicas in staging/production
- Automatic scaling based on load
- Rolling updates with surge capacity

### 2. Pod Disruption Budgets

Ensures availability during maintenance:
```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: ant-fileserver
spec:
  minAvailable: 1  # Staging
  # minAvailable: 2  # Production
  selector:
    matchLabels:
      app: ant-fileserver
```

### 3. Anti-Affinity Rules

Spreads pods across nodes:
```yaml
affinity:
  podAntiAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
    - weight: 100
      podAffinityTerm:
        topologyKey: kubernetes.io/hostname
```

## Auto-Scaling Configuration

### Horizontal Pod Autoscaler

Scales based on multiple metrics:
- **CPU**: 70% threshold
- **Memory**: 80% threshold
- **Scale-up**: Fast response (30s)
- **Scale-down**: Conservative (5-10 min)

### Scaling Behavior

```yaml
behavior:
  scaleUp:
    stabilizationWindowSeconds: 30
    policies:
    - type: Percent
      value: 100
      periodSeconds: 60
  scaleDown:
    stabilizationWindowSeconds: 300  # 5 min staging
    # stabilizationWindowSeconds: 600  # 10 min production
```

## Ingress Configuration

### TLS Termination

Using cert-manager with Let's Encrypt:
```yaml
annotations:
  cert-manager.io/cluster-issuer: letsencrypt-cloudflare-prod
tls:
- hosts:
  - api.scopecreep.productions
  secretName: ant-fileserver-tls
```

### Security Headers

Production ingress adds security headers:
- X-Frame-Options: DENY
- X-Content-Type-Options: nosniff
- X-XSS-Protection: 1; mode=block
- Referrer-Policy: strict-origin-when-cross-origin

### Rate Limiting

Protection against abuse:
- Staging: 200 requests/min
- Production: 500 requests/min

## Monitoring Integration

### ServiceMonitor

Prometheus operator integration:
```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: ant-fileserver
spec:
  selector:
    matchLabels:
      app: ant-fileserver
  endpoints:
  - port: http
    path: /metrics
    interval: 30s
```

### Metrics Exposed

- Request rate and latency
- Error rates by endpoint
- Storage operation metrics
- Resource utilization

## Resource Management

### Resource Requests/Limits

Environment-specific sizing:

| Environment | CPU Request | CPU Limit | Memory Request | Memory Limit |
|------------|-------------|-----------|----------------|--------------|
| Local      | 50m         | 200m      | 64Mi           | 256Mi        |
| Dev        | 100m        | 500m      | 128Mi          | 512Mi        |
| Staging    | 200m        | 1000m     | 256Mi          | 1Gi          |
| Production | 500m        | 2000m     | 512Mi          | 2Gi          |

## Deployment Strategies

### Rolling Updates

Zero-downtime deployments:
```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 1
    maxUnavailable: 0
```

### Health Checks

Ensures only healthy pods receive traffic:
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: http
  initialDelaySeconds: 30
  periodSeconds: 30

readinessProbe:
  httpGet:
    path: /ready
    port: http
  initialDelaySeconds: 10
  periodSeconds: 10
```

## GitOps Integration

### Kustomize Benefits

- Environment-specific patches
- ConfigMap generation
- Secret management
- Image tag updates
- Resource transformation

### CI/CD Pipeline

Automated deployment flow:
1. Build and test application
2. Build and push container image
3. Update image tag in kustomization
4. Apply manifests to cluster
5. Verify deployment health

## Best Practices

1. **Security First**: All security features enabled by default
2. **Observability**: Comprehensive monitoring and logging
3. **Reliability**: HA configuration for production
4. **Efficiency**: Right-sized resources per environment
5. **Maintainability**: Clear separation of concerns