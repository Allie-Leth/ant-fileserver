# Security Documentation

## Overview

This document covers the security architecture, policies, and best practices for the ANT Fileserver deployment.

## Security Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Internet                              │
└────────────────────┬────────────────────────────────────┘
                     │ TLS 1.3
              ┌──────▼──────┐
              │  Cloudflare │ WAF, DDoS Protection
              └──────┬──────┘
                     │
              ┌──────▼──────┐
              │   Ingress   │ Rate Limiting, Security Headers
              └──────┬──────┘
                     │
         ┌───────────┼───────────┐
         │    NetworkPolicy      │
         │  ┌────────▼────────┐  │
         │  │  ANT Fileserver │  │ Pod Security Standards
         │  └────────┬────────┘  │
         │           │           │
         │  ┌────────▼────────┐  │
         │  │  MinIO Storage  │  │ Encrypted at Rest
         │  └─────────────────┘  │
         └───────────────────────┘
```

## Network Security

### NetworkPolicy Configuration

Zero-trust network model with explicit allow rules:

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
  # DNS resolution
  - to:
    - namespaceSelector: {}
    ports:
    - protocol: TCP
      port: 53
    - protocol: UDP
      port: 53
  # MinIO storage
  - to:
    - podSelector:
        matchLabels:
          app: minio
    ports:
    - protocol: TCP
      port: 9000
  # External HTTPS (for webhooks, etc)
  - to:
    - namespaceSelector: {}
    ports:
    - protocol: TCP
      port: 443
```

### Ingress Security

Security headers and policies:

```yaml
annotations:
  # Security headers
  nginx.ingress.kubernetes.io/configuration-snippet: |
    more_set_headers "X-Frame-Options: DENY";
    more_set_headers "X-Content-Type-Options: nosniff";
    more_set_headers "X-XSS-Protection: 1; mode=block";
    more_set_headers "Referrer-Policy: strict-origin-when-cross-origin";
    more_set_headers "Content-Security-Policy: default-src 'self'";
    more_set_headers "Permissions-Policy: geolocation=(), microphone=(), camera=()";
  
  # Rate limiting
  nginx.ingress.kubernetes.io/limit-rps: "10"
  nginx.ingress.kubernetes.io/limit-burst: "20"
  
  # ModSecurity WAF
  nginx.ingress.kubernetes.io/enable-modsecurity: "true"
  nginx.ingress.kubernetes.io/enable-owasp-core-rules: "true"
```

## Pod Security

### Pod Security Standards

All pods run with the Restricted security standard:

```yaml
apiVersion: v1
kind: Pod
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    runAsGroup: 1000
    fsGroup: 1000
    seccompProfile:
      type: RuntimeDefault
  containers:
  - name: ant-fileserver
    securityContext:
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      capabilities:
        drop:
        - ALL
      runAsNonRoot: true
```

### Container Security

1. **Non-root user**: UID 1000
2. **Read-only filesystem**: Prevents runtime modifications
3. **No capabilities**: All Linux capabilities dropped
4. **No privilege escalation**: Prevents sudo/setuid

## Authentication & Authorization

### API Key Authentication

```python
def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        
        # Constant-time comparison to prevent timing attacks
        if not api_key or not secrets.compare_digest(
            api_key, 
            current_app.config['API_KEYS'][0]
        ):
            return jsonify({'error': 'Invalid or missing API key'}), 401
            
        return f(*args, **kwargs)
    return decorated_function
```

### RBAC Configuration

Minimal ServiceAccount permissions:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: ant-fileserver
automountServiceAccountToken: false
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: ant-fileserver
rules: []  # No permissions needed
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: ant-fileserver
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: ant-fileserver
subjects:
- kind: ServiceAccount
  name: ant-fileserver
```

## Data Security

### Encryption at Rest

MinIO configuration for encryption:

```yaml
# MinIO server-side encryption
MINIO_KMS_KES_ENDPOINT: https://kes.example.com
MINIO_KMS_KES_KEY_FILE: /certs/key.pem
MINIO_KMS_KES_CERT_FILE: /certs/cert.pem
MINIO_KMS_KES_CA_PATH: /certs/ca.pem
MINIO_KMS_KES_KEY_NAME: my-minio-key
```

### Encryption in Transit

All communication uses TLS 1.3:

```yaml
# cert-manager configuration
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: ant-fileserver-tls
spec:
  secretName: ant-fileserver-tls
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  dnsNames:
  - api.scopecreep.productions
  - api-staging.scopecreep.productions
```

## Secret Management

### Kubernetes Secrets

Best practices for secrets:

```bash
# Create secrets securely
kubectl create secret generic ant-fileserver-secrets \
  --from-literal=api-keys="$(openssl rand -base64 32)" \
  --from-literal=storage-access-key="$(openssl rand -base64 32)" \
  --from-literal=storage-secret-key="$(openssl rand -base64 32)" \
  -n ant-prod

# Encrypt secrets at rest
kubectl patch storageclass standard -p \
  '{"parameters":{"encrypted":"true"}}'
```

### External Secret Management

Integration with HashiCorp Vault:

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: ant-fileserver-secrets
spec:
  secretStoreRef:
    name: vault-backend
    kind: SecretStore
  target:
    name: ant-fileserver-secrets
  data:
  - secretKey: api-keys
    remoteRef:
      key: secret/data/ant-fileserver
      property: api-keys
```

## Input Validation

### Request Validation

```python
from marshmallow import Schema, fields, validate, ValidationError

class FirmwareUploadSchema(Schema):
    version = fields.Str(
        required=True,
        validate=validate.Regexp(r'^\d+\.\d+\.\d+$')
    )
    device_type = fields.Str(
        required=True,
        validate=[
            validate.Length(min=1, max=50),
            validate.Regexp(r'^[a-zA-Z0-9-_]+$')
        ]
    )
    file = fields.Raw(
        required=True,
        validate=validate_file_type
    )

def validate_file_type(file):
    allowed_extensions = {'.bin', '.hex', '.img'}
    if not any(file.filename.endswith(ext) for ext in allowed_extensions):
        raise ValidationError('Invalid file type')
    
    # Check file signature
    file_header = file.read(512)
    file.seek(0)
    if not is_valid_firmware_header(file_header):
        raise ValidationError('Invalid firmware file')
```

### SQL Injection Prevention

Using parameterized queries:

```python
# Good: Parameterized query
cursor.execute(
    "SELECT * FROM firmware WHERE version = %s AND device_type = %s",
    (version, device_type)
)

# Bad: String concatenation
# cursor.execute(f"SELECT * FROM firmware WHERE version = '{version}'")
```

## Security Headers

### Application Headers

```python
@app.after_request
def set_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Content-Security-Policy'] = "default-src 'self'"
    return response
```

## Vulnerability Management

### Container Scanning

```yaml
# .github/workflows/security.yml
name: Security Scan

on:
  push:
    branches: [main]
  schedule:
    - cron: '0 0 * * *'  # Daily scan

jobs:
  trivy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: 'ghcr.io/${{ github.repository }}:latest'
          format: 'sarif'
          output: 'trivy-results.sarif'
      - name: Upload Trivy scan results
        uses: github/codeql-action/upload-sarif@v2
        with:
          sarif_file: 'trivy-results.sarif'
```

### Dependency Scanning

```bash
# Python dependency check
pip install safety
safety check

# Update dependencies
pip install --upgrade -r requirements.txt
```

## Compliance

### OWASP Top 10 Mitigation

1. **Injection**: Parameterized queries, input validation
2. **Broken Authentication**: Strong API keys, rate limiting
3. **Sensitive Data Exposure**: TLS everywhere, encryption at rest
4. **XML External Entities**: Not applicable (JSON only)
5. **Broken Access Control**: API key validation on all endpoints
6. **Security Misconfiguration**: Security headers, minimal permissions
7. **Cross-Site Scripting**: CSP headers, output encoding
8. **Insecure Deserialization**: Input validation, type checking
9. **Using Components with Known Vulnerabilities**: Regular scanning
10. **Insufficient Logging**: Comprehensive audit logging

### Audit Logging

```python
import json
from datetime import datetime

def audit_log(action, user, resource, result):
    log_entry = {
        'timestamp': datetime.utcnow().isoformat(),
        'action': action,
        'user': user,
        'resource': resource,
        'result': result,
        'ip_address': request.remote_addr,
        'user_agent': request.headers.get('User-Agent')
    }
    
    # Log to secure audit log
    audit_logger.info(json.dumps(log_entry))
```

## Incident Response

### Security Incident Procedure

1. **Detection**
   - Monitor security alerts
   - Review audit logs
   - Check vulnerability reports

2. **Containment**
   ```bash
   # Isolate affected pods
   kubectl cordon node-name
   
   # Scale down if necessary
   kubectl scale deployment ant-fileserver --replicas=0 -n ant-prod
   ```

3. **Investigation**
   ```bash
   # Collect logs
   kubectl logs -n ant-prod -l app=ant-fileserver --since=24h > incident.log
   
   # Capture pod state
   kubectl describe pods -n ant-prod > pod-state.txt
   ```

4. **Remediation**
   - Patch vulnerabilities
   - Update configurations
   - Deploy fixes

5. **Recovery**
   - Restore service
   - Verify security measures
   - Monitor closely

### Contact Information

Security issues should be reported to:
- Email: security@scopecreep.productions
- PGP Key: [Public key ID]

## Security Checklist

### Deployment Security

- [ ] All containers run as non-root
- [ ] Pod Security Standards enforced
- [ ] NetworkPolicies configured
- [ ] TLS enabled for all endpoints
- [ ] Secrets encrypted at rest
- [ ] RBAC properly configured
- [ ] Security headers set
- [ ] Rate limiting enabled
- [ ] WAF rules active
- [ ] Vulnerability scanning automated

### Application Security

- [ ] Input validation on all endpoints
- [ ] API authentication required
- [ ] Error messages sanitized
- [ ] Logging excludes sensitive data
- [ ] Dependencies up to date
- [ ] Security tests in CI/CD
- [ ] Code review for security
- [ ] Penetration testing performed

## Regular Security Tasks

### Daily
- Review security alerts
- Check failed authentication attempts
- Monitor rate limiting triggers

### Weekly
- Review vulnerability scan results
- Update security patches
- Audit access logs

### Monthly
- Rotate API keys
- Review and update security policies
- Security training for team

### Quarterly
- Penetration testing
- Security architecture review
- Incident response drill