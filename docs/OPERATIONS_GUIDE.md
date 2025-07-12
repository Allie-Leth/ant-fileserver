# Operations Guide

## Overview

This guide covers monitoring, maintenance, troubleshooting, and operational procedures for the ANT Fileserver in production environments.

## Monitoring Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Application   │────▶│   Prometheus     │────▶│    Grafana      │
│    Metrics      │     │                  │     │                 │
└─────────────────┘     └──────────────────┘     └─────────────────┘
         │                       │                         │
         │                       ▼                         │
         │              ┌──────────────────┐              │
         └──────────────│   AlertManager   │──────────────┘
                        └──────────────────┘
```

## Metrics and Monitoring

### Application Metrics

The application exposes metrics at `/metrics`:

```python
# Key metrics exposed
ant_fileserver_requests_total{method,endpoint,status}
ant_fileserver_request_duration_seconds{method,endpoint}
ant_fileserver_storage_operations_total{operation,status}
ant_fileserver_storage_duration_seconds{operation}
ant_fileserver_active_connections
ant_fileserver_firmware_uploads_total
ant_fileserver_firmware_downloads_total
```

### Prometheus Configuration

ServiceMonitor for automatic discovery:

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

### Grafana Dashboards

Import dashboard JSON:

```json
{
  "dashboard": {
    "title": "ANT Fileserver",
    "panels": [
      {
        "title": "Request Rate",
        "targets": [{
          "expr": "rate(ant_fileserver_requests_total[5m])"
        }]
      },
      {
        "title": "Error Rate",
        "targets": [{
          "expr": "rate(ant_fileserver_requests_total{status=~'5..'}[5m])"
        }]
      },
      {
        "title": "Response Time",
        "targets": [{
          "expr": "histogram_quantile(0.95, ant_fileserver_request_duration_seconds)"
        }]
      }
    ]
  }
}
```

## Alerting Rules

### Prometheus Alert Configuration

```yaml
groups:
  - name: ant-fileserver
    rules:
    - alert: HighErrorRate
      expr: rate(ant_fileserver_requests_total{status=~"5.."}[5m]) > 0.05
      for: 5m
      labels:
        severity: warning
      annotations:
        summary: "High error rate detected"
        description: "Error rate is {{ $value }} errors per second"
    
    - alert: HighResponseTime
      expr: histogram_quantile(0.95, ant_fileserver_request_duration_seconds) > 1
      for: 5m
      labels:
        severity: warning
      annotations:
        summary: "High response time"
        description: "95th percentile response time is {{ $value }} seconds"
    
    - alert: PodCrashLooping
      expr: rate(kube_pod_container_status_restarts_total{namespace="ant-prod"}[15m]) > 0
      for: 5m
      labels:
        severity: critical
      annotations:
        summary: "Pod is crash looping"
        description: "Pod {{ $labels.pod }} has restarted {{ $value }} times"
    
    - alert: StorageErrors
      expr: rate(ant_fileserver_storage_operations_total{status="error"}[5m]) > 0.01
      for: 5m
      labels:
        severity: warning
      annotations:
        summary: "Storage operation errors"
        description: "Storage error rate is {{ $value }} per second"
```

## Logging

### Log Aggregation

Structured JSON logs for easy parsing:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "service": "ant-fileserver",
  "request_id": "abc123",
  "method": "POST",
  "path": "/api/v1/firmware",
  "status": 201,
  "duration_ms": 125,
  "client_ip": "10.0.0.1",
  "message": "Firmware uploaded successfully"
}
```

### Log Queries

Common Elasticsearch/Kibana queries:

```json
// Find all errors
{
  "query": {
    "match": {
      "level": "ERROR"
    }
  }
}

// Find slow requests
{
  "query": {
    "range": {
      "duration_ms": {
        "gte": 1000
      }
    }
  }
}

// Find specific endpoint errors
{
  "query": {
    "bool": {
      "must": [
        { "match": { "path": "/api/v1/firmware" } },
        { "match": { "status": 500 } }
      ]
    }
  }
}
```

## Health Checks and SLOs

### Service Level Objectives

| Metric | SLO Target | Measurement Window |
|--------|------------|-------------------|
| Availability | 99.9% | 30 days |
| Response Time (p95) | < 200ms | 5 minutes |
| Error Rate | < 0.1% | 5 minutes |
| Storage Success Rate | > 99.5% | 1 hour |

### Health Check Procedures

```bash
# Quick health check
curl https://api.scopecreep.productions/health

# Detailed readiness check
curl https://api.scopecreep.productions/ready

# Check specific pod health
kubectl exec -n ant-prod deployment/ant-fileserver -- curl localhost:8000/health
```

## Scaling Operations

### Manual Scaling

```bash
# Scale up for high load
kubectl scale deployment ant-fileserver --replicas=10 -n ant-prod

# Scale down after load decreases
kubectl scale deployment ant-fileserver --replicas=3 -n ant-prod
```

### HPA Tuning

```bash
# Check current HPA status
kubectl get hpa ant-fileserver -n ant-prod

# Update HPA thresholds
kubectl patch hpa ant-fileserver -n ant-prod --patch '
spec:
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 60
'
```

### Capacity Planning

Monitor these metrics for capacity planning:
- Average CPU usage per pod
- Average memory usage per pod
- Request rate trends
- Storage growth rate
- Network bandwidth usage

## Backup and Recovery

### Configuration Backup

```bash
# Backup all configurations
kubectl get all,cm,secret,ing,netpol -n ant-prod -o yaml > backup-$(date +%Y%m%d).yaml

# Backup kustomization files
tar -czf k8s-config-$(date +%Y%m%d).tar.gz k8s/
```

### Storage Backup

MinIO backup procedures:
```bash
# Sync bucket to backup location
mc mirror source/ant-fileserver backup/ant-fileserver-$(date +%Y%m%d)

# Verify backup
mc ls backup/ant-fileserver-$(date +%Y%m%d)
```

### Disaster Recovery

Recovery procedure:
1. Restore Kubernetes configurations
2. Restore MinIO data
3. Update DNS if needed
4. Verify service health

## Maintenance Procedures

### Rolling Updates

```bash
# Update image
kubectl set image deployment/ant-fileserver \
  ant-fileserver=ghcr.io/yourorg/ant-fileserver:v2.0.0 \
  -n ant-prod --record

# Monitor rollout
kubectl rollout status deployment/ant-fileserver -n ant-prod

# Verify new version
kubectl get pods -n ant-prod -o jsonpath='{.items[*].spec.containers[0].image}'
```

### Certificate Renewal

cert-manager handles automatic renewal, but verify:

```bash
# Check certificate status
kubectl get certificates -n ant-prod

# Check certificate expiry
kubectl describe certificate ant-fileserver-tls -n ant-prod

# Force renewal if needed
kubectl delete certificate ant-fileserver-tls -n ant-prod
```

### Database Maintenance

If using external database:
```bash
# Backup database
pg_dump -h db.example.com -U ant_user ant_fileserver > backup.sql

# Vacuum and analyze
psql -h db.example.com -U ant_user -d ant_fileserver -c "VACUUM ANALYZE;"
```

## Troubleshooting Guide

### Common Issues

#### 1. High Memory Usage

**Symptoms**: Pods being OOMKilled

**Investigation**:
```bash
# Check memory usage
kubectl top pods -n ant-prod

# Check OOMKill events
kubectl get events -n ant-prod | grep OOMKill

# Review memory limits
kubectl describe deployment ant-fileserver -n ant-prod | grep -A5 "resources:"
```

**Resolution**:
- Increase memory limits
- Investigate memory leaks
- Review application logs

#### 2. Storage Connection Issues

**Symptoms**: 500 errors, storage timeouts

**Investigation**:
```bash
# Test MinIO connectivity
kubectl exec -n ant-prod deployment/ant-fileserver -- \
  curl -I http://minio-service:9000/minio/health/live

# Check network policies
kubectl get networkpolicy -n ant-prod

# Review storage logs
kubectl logs -n ant-prod -l app=ant-fileserver | grep storage
```

**Resolution**:
- Verify MinIO credentials
- Check network policies
- Review firewall rules

#### 3. Slow Response Times

**Symptoms**: High latency, timeouts

**Investigation**:
```bash
# Check pod resources
kubectl top pods -n ant-prod

# Review HPA scaling
kubectl describe hpa ant-fileserver -n ant-prod

# Check ingress controller
kubectl logs -n ingress-nginx deployment/ingress-nginx-controller
```

**Resolution**:
- Scale up pods
- Optimize database queries
- Review caching strategy

### Debug Mode

Enable debug logging:

```bash
# Update ConfigMap
kubectl edit configmap ant-fileserver-config -n ant-prod
# Set LOG_LEVEL=DEBUG

# Restart pods
kubectl rollout restart deployment/ant-fileserver -n ant-prod

# Watch debug logs
kubectl logs -n ant-prod -l app=ant-fileserver -f | grep DEBUG
```

## Performance Tuning

### Application Tuning

```python
# Gunicorn worker tuning
workers = multiprocessing.cpu_count() * 2 + 1
worker_connections = 1000
keepalive = 5

# Connection pooling
STORAGE_POOL_SIZE = 10
STORAGE_POOL_TIMEOUT = 30
```

### Kubernetes Tuning

```yaml
# Resource optimization
resources:
  requests:
    cpu: 500m    # Baseline CPU
    memory: 512Mi # Baseline memory
  limits:
    cpu: 2000m   # Allow bursting
    memory: 2Gi  # Prevent OOM

# Connection tuning
readinessProbe:
  successThreshold: 1
  failureThreshold: 3
  timeoutSeconds: 5
```

### Network Optimization

```yaml
# Ingress optimization
annotations:
  nginx.ingress.kubernetes.io/proxy-body-size: "100m"
  nginx.ingress.kubernetes.io/proxy-connect-timeout: "30"
  nginx.ingress.kubernetes.io/proxy-send-timeout: "300"
  nginx.ingress.kubernetes.io/proxy-read-timeout: "300"
  nginx.ingress.kubernetes.io/client-body-buffer-size: "16k"
```

## Security Operations

### Security Scanning

```bash
# Scan container images
trivy image ghcr.io/yourorg/ant-fileserver:latest

# Scan running pods
kubectl get pods -n ant-prod -o jsonpath="{.items[*].spec.containers[*].image}" | \
  tr -s '[[:space:]]' '\n' | sort | uniq | xargs -I {} trivy image {}

# Check security policies
kubectl get psp
kubectl get networkpolicies -n ant-prod
```

### Incident Response

1. **Detection**: Alert triggered
2. **Triage**: Assess severity and impact
3. **Containment**: Isolate affected components
4. **Investigation**: Root cause analysis
5. **Resolution**: Fix and deploy
6. **Documentation**: Post-mortem

### Audit Logging

```bash
# Review API access
kubectl logs -n ant-prod -l app=ant-fileserver | grep "X-API-Key"

# Check authentication failures
kubectl logs -n ant-prod -l app=ant-fileserver | grep "401"

# Export audit logs
kubectl logs -n ant-prod -l app=ant-fileserver \
  --since=24h > audit-$(date +%Y%m%d).log
```

## Regular Maintenance Tasks

### Daily
- Check dashboard for anomalies
- Review error logs
- Verify backup completion

### Weekly
- Review performance metrics
- Check certificate expiry
- Update dependencies

### Monthly
- Capacity planning review
- Security scan results
- Cost optimization review

### Quarterly
- Disaster recovery drill
- Load testing
- Architecture review