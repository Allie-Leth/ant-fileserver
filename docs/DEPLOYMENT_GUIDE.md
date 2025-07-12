# Deployment Guide

## Overview

This guide covers deployment procedures for the ANT Fileserver across different environments using Kubernetes and GitOps practices.

## Prerequisites

### Required Tools

1. **kubectl** (v1.28+)
   ```bash
   curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
   chmod +x kubectl
   sudo mv kubectl /usr/local/bin/
   ```

2. **kustomize** (v5.0+)
   ```bash
   curl -s "https://raw.githubusercontent.com/kubernetes-sigs/kustomize/master/hack/install_kustomize.sh" | bash
   sudo mv kustomize /usr/local/bin/
   ```

3. **Docker** (for building images)
   ```bash
   # Follow Docker installation guide for your OS
   ```

### Cluster Requirements

- Kubernetes 1.28+
- NGINX Ingress Controller
- cert-manager (for TLS)
- metrics-server (for HPA)
- Prometheus Operator (optional, for monitoring)

## Environment Overview

| Environment | Purpose | Namespace | Domain | Features |
|------------|---------|-----------|--------|----------|
| Local | Development | ant-local | localhost:30080 | Minimal security |
| Dev | Integration | ant-dev | api-dev.example.com | Basic features |
| Staging | Pre-production | ant-staging | api-staging.scopecreep.productions | Full features |
| Production | Live service | ant-prod | api.scopecreep.productions | HA, monitoring |

## Deployment Process

### 1. Local Development

For local development and testing:

```bash
# Create namespace
kubectl create namespace ant-local

# Deploy using local overlay
kubectl apply -k k8s/app/overlays/local/

# Check deployment
kubectl get all -n ant-local

# Access service (NodePort)
curl http://localhost:30080/health
```

### 2. Development Environment

Deploy to development cluster:

```bash
# Create namespace
kubectl create namespace ant-dev

# Deploy using dev overlay
kubectl apply -k k8s/app/overlays/dev/

# Verify deployment
kubectl rollout status deployment/ant-fileserver -n ant-dev

# Check pods
kubectl get pods -n ant-dev
```

### 3. Staging Environment

Deploy to staging with full features:

```bash
# Create namespace with labels
kubectl create namespace ant-staging
kubectl label namespace ant-staging name=ant-staging

# Deploy using staging overlay
kubectl apply -k k8s/app/overlays/staging/

# Wait for deployment
kubectl wait --for=condition=available --timeout=300s \
  deployment/ant-fileserver -n ant-staging

# Verify HPA
kubectl get hpa -n ant-staging

# Check ingress
kubectl get ingress -n ant-staging
```

### 4. Production Environment

Production deployment with approvals:

```bash
# Create namespace with labels
kubectl create namespace ant-prod
kubectl label namespace ant-prod name=ant-prod

# Dry-run first
kubectl apply -k k8s/app/overlays/prod/ --dry-run=server

# Deploy if dry-run succeeds
kubectl apply -k k8s/app/overlays/prod/

# Monitor rollout
kubectl rollout status deployment/ant-fileserver -n ant-prod

# Verify all components
kubectl get all,hpa,pdb,ingress,networkpolicy -n ant-prod
```

## CI/CD Pipeline

### GitHub Actions Workflow

```yaml
name: Deploy to Kubernetes

on:
  push:
    branches: [main]
    tags: ['v*']

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Build and push image
      run: |
        docker build -t ghcr.io/${{ github.repository }}:${{ github.sha }} .
        docker push ghcr.io/${{ github.repository }}:${{ github.sha }}
    
    - name: Deploy to staging
      if: github.ref == 'refs/heads/main'
      run: |
        cd k8s/app/overlays/staging
        kustomize edit set image ant-fileserver=ghcr.io/${{ github.repository }}:${{ github.sha }}
        kubectl apply -k .
    
    - name: Deploy to production
      if: startsWith(github.ref, 'refs/tags/v')
      run: |
        cd k8s/app/overlays/prod
        kustomize edit set image ant-fileserver=ghcr.io/${{ github.repository }}:${{ github.ref_name }}
        kubectl apply -k .
```

## Configuration Management

### Environment Variables

Set via ConfigMap in each overlay:

```yaml
# k8s/app/overlays/staging/kustomization.yaml
configMapGenerator:
  - name: ant-fileserver-config
    behavior: merge
    literals:
      - LOG_LEVEL=info
      - FLASK_ENV=production
      - STORAGE_ENDPOINT=https://minio-staging.example.com
      - STORAGE_BUCKET=ant-fileserver-staging
```

### Secrets Management

Create secrets for each environment:

```bash
# Create secret for API keys and storage credentials
kubectl create secret generic ant-fileserver-secrets \
  --from-literal=api-keys="key1,key2,key3" \
  --from-literal=storage-access-key="minio-access-key" \
  --from-literal=storage-secret-key="minio-secret-key" \
  -n ant-staging
```

### Image Management

Update image tags using kustomize:

```bash
# Update staging image
cd k8s/app/overlays/staging
kustomize edit set image ant-fileserver=ghcr.io/yourorg/ant-fileserver:v1.2.3

# Update production image
cd k8s/app/overlays/prod
kustomize edit set image ant-fileserver=ghcr.io/yourorg/ant-fileserver:v1.2.3
```

## Rollout Strategies

### Blue-Green Deployment

For zero-downtime deployments:

1. Deploy new version to separate deployment
2. Test new version thoroughly
3. Switch service selector
4. Remove old deployment

### Canary Deployment

Gradual rollout:

```yaml
# Deploy canary version
kubectl set image deployment/ant-fileserver \
  ant-fileserver=ghcr.io/yourorg/ant-fileserver:v2.0.0 \
  -n ant-prod --record

# Monitor metrics
kubectl get pods -n ant-prod -w

# Complete rollout if successful
kubectl rollout resume deployment/ant-fileserver -n ant-prod
```

### Rollback Procedures

Quick rollback if issues detected:

```bash
# Check rollout history
kubectl rollout history deployment/ant-fileserver -n ant-prod

# Rollback to previous version
kubectl rollout undo deployment/ant-fileserver -n ant-prod

# Rollback to specific revision
kubectl rollout undo deployment/ant-fileserver -n ant-prod --to-revision=3
```

## Health Checks

### Pre-deployment Checks

Run validation before deployment:

```bash
# Run Phase 1 tests
./scripts/k8s/test-phase1-application.sh

# Run Phase 2 tests
./scripts/k8s/test-phase2-security.sh

# Run Phase 3 tests
./scripts/k8s/test-phase3-production.sh

# Run all tests
./scripts/k8s/validate-all.sh
```

### Post-deployment Verification

Verify deployment health:

```bash
# Check pod status
kubectl get pods -n ant-staging -o wide

# Check logs
kubectl logs -n ant-staging -l app=ant-fileserver --tail=50

# Test endpoints
curl -H "X-API-Key: test-key" https://api-staging.scopecreep.productions/health

# Check metrics
kubectl top pods -n ant-staging
```

## Monitoring Deployment

### Watch Resources

Monitor during deployment:

```bash
# Watch all resources
watch kubectl get all,hpa,pdb -n ant-staging

# Watch HPA scaling
kubectl get hpa -n ant-staging -w

# Monitor events
kubectl events -n ant-staging -w
```

### Load Testing

Test auto-scaling:

```bash
# Run load test
./scripts/k8s/load-test-hpa.sh ant-staging 300

# Monitor scaling behavior
kubectl get hpa,pods -n ant-staging -w
```

## Troubleshooting

### Common Issues

1. **ImagePullBackOff**
   ```bash
   # Check image name and credentials
   kubectl describe pod <pod-name> -n ant-staging
   kubectl get events -n ant-staging
   ```

2. **CrashLoopBackOff**
   ```bash
   # Check logs
   kubectl logs <pod-name> -n ant-staging --previous
   ```

3. **HPA Not Scaling**
   ```bash
   # Check metrics
   kubectl top nodes
   kubectl top pods -n ant-staging
   kubectl describe hpa -n ant-staging
   ```

4. **Ingress Not Working**
   ```bash
   # Check ingress controller
   kubectl get pods -n ingress-nginx
   kubectl describe ingress -n ant-staging
   ```

### Debug Commands

```bash
# Get detailed pod info
kubectl describe pod <pod-name> -n ant-staging

# Execute commands in pod
kubectl exec -it <pod-name> -n ant-staging -- /bin/sh

# Check resource usage
kubectl top pod <pod-name> -n ant-staging

# View recent events
kubectl get events -n ant-staging --sort-by='.lastTimestamp'
```

## Security Considerations

### Pre-deployment Security Checks

1. Scan container images
2. Verify RBAC permissions
3. Check NetworkPolicy rules
4. Validate Pod Security Standards

### Secret Rotation

Regular rotation procedure:

```bash
# Generate new API keys
NEW_KEYS=$(openssl rand -base64 32)

# Update secret
kubectl create secret generic ant-fileserver-secrets \
  --from-literal=api-keys="$NEW_KEYS" \
  --dry-run=client -o yaml | \
  kubectl apply -f - -n ant-prod

# Restart pods to pick up new secrets
kubectl rollout restart deployment/ant-fileserver -n ant-prod
```

## Maintenance

### Scaling Operations

```bash
# Manual scaling
kubectl scale deployment ant-fileserver --replicas=5 -n ant-staging

# Update HPA limits
kubectl patch hpa ant-fileserver -n ant-staging \
  --patch '{"spec":{"maxReplicas":10}}'
```

### Resource Updates

```bash
# Update resource limits
kubectl set resources deployment ant-fileserver \
  -c ant-fileserver \
  --requests=cpu=200m,memory=256Mi \
  --limits=cpu=1000m,memory=1Gi \
  -n ant-staging
```

## Best Practices

1. **Always test in staging first**
2. **Use GitOps for production changes**
3. **Monitor deployments actively**
4. **Keep rollback procedures ready**
5. **Document all changes**
6. **Use semantic versioning for images**
7. **Implement proper health checks**
8. **Set resource limits appropriately**