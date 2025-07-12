# Kubernetes Testing Scripts

This directory contains comprehensive testing scripts for the ant-fileserver Kubernetes deployment.

## Scripts

### 1. validate-manifests.sh

**Purpose**: Static validation of Kubernetes manifests without deploying them.

**Features**:
- Kustomize build validation
- API deprecation checks (with optional pluto support)
- Schema validation (with optional kubeconform support)
- Security compliance checks (Pod Security Standards)
- Resource configuration validation
- Best practices validation

**Usage**:
```bash
./scripts/k8s/validate-manifests.sh
```

**Optional Tools**:
- **kubeconform**: For strict schema validation
  ```bash
  go install github.com/yannh/kubeconform/cmd/kubeconform@latest
  ```
- **pluto**: For comprehensive deprecation checks
  ```bash
  go install github.com/FairwindsOps/pluto/v5@latest
  ```
- **yq**: For YAML parsing
  ```bash
  go install github.com/mikefarah/yq/v4@latest
  ```

### 2. test-base-deployment.sh

**Purpose**: Runtime testing of the actual deployment in a test namespace.

**Features**:
- Creates isolated test namespace
- Deploys manifests with test overrides
- Validates pod startup and health
- Checks security context application
- Verifies resource limits
- Tests environment variable injection
- Validates service connectivity

**Usage**:
```bash
# Run with automatic cleanup
./scripts/k8s/test-base-deployment.sh

# Keep test namespace for debugging
CLEANUP=false ./scripts/k8s/test-base-deployment.sh

# Use custom namespace
TEST_NAMESPACE=my-test ./scripts/k8s/test-base-deployment.sh
```

## Testing Strategy

### Phase 1: Static Validation
Run `validate-manifests.sh` to catch issues before deployment:
- YAML syntax errors
- Invalid resource definitions
- Deprecated APIs
- Security policy violations
- Missing required fields

### Phase 2: Deployment Testing
Run `test-base-deployment.sh` to validate runtime behavior:
- Resource creation
- Pod scheduling and startup
- Configuration injection
- Network connectivity
- Security context enforcement

### Phase 3: Application Testing (TODO)
Future scripts will test:
- Health check endpoints with actual application
- MinIO connectivity
- API functionality
- Performance characteristics

## Best Practices Validated

1. **Security**:
   - Non-root user (UID >= 1000)
   - Read-only root filesystem
   - No privilege escalation
   - All capabilities dropped
   - Seccomp RuntimeDefault profile

2. **Reliability**:
   - Resource requests and limits defined
   - Health probes configured
   - Proper labels for selection
   - Service account specified

3. **Maintainability**:
   - No use of deprecated APIs
   - Proper label taxonomy
   - Clean resource naming
   - Environment-based configuration

## CI/CD Integration

These scripts are designed to be run in CI pipelines:

```yaml
# Example GitHub Actions step
- name: Validate Kubernetes manifests
  run: |
    ./scripts/k8s/validate-manifests.sh
    
- name: Test deployment
  run: |
    ./scripts/k8s/test-base-deployment.sh
```

## Troubleshooting

### validate-manifests.sh failures

1. **"No deprecated APIs" fails**:
   - Install pluto for detailed deprecation info
   - Check Kubernetes version compatibility

2. **"Schema validation" fails**:
   - Install kubeconform for detailed errors
   - Verify API versions are correct

3. **"Security context" fails**:
   - Review Pod Security Standards
   - Ensure all required fields are set

### test-base-deployment.sh failures

1. **"Deployment failed to become ready"**:
   - Check pod logs: `kubectl logs -n ant-test -l app=ant-fileserver`
   - Describe pod: `kubectl describe pod -n ant-test -l app=ant-fileserver`
   - Common issues: image pull errors, resource constraints

2. **"Security context - non-root user" fails**:
   - Verify securityContext is properly set in deployment
   - Check for admission controller interference

3. **"Service is reachable" fails**:
   - Ensure service selectors match pod labels
   - Check network policies aren't blocking traffic

## Environment Variables

- `KUBERNETES_VERSION`: Target Kubernetes version (default: 1.29.0)
- `TEST_NAMESPACE`: Namespace for deployment tests (default: ant-test)
- `TEST_TIMEOUT`: Timeout for deployment readiness (default: 300s)
- `CLEANUP`: Whether to delete test namespace (default: true)

## Future Enhancements

1. **Integration with Real Application**:
   - Build and test actual ant-fileserver image
   - Validate real health endpoints
   - Test MinIO connectivity

2. **Performance Testing**:
   - Load testing with k6 or similar
   - Resource utilization monitoring
   - Scaling behavior validation

3. **Security Scanning**:
   - Container image scanning
   - Network policy validation
   - RBAC testing (when implemented)

4. **Multi-Environment Testing**:
   - Test overlay configurations
   - Environment-specific validation
   - Promotion testing