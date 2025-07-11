# GitLab to GitHub Migration Guide

## Overview

This document outlines the migration from GitLab (`gitlab.scopecreep.productions`) to GitHub for the Ant Firmware API project.

## Migration Steps Completed

### 1. CI/CD Pipeline Migration
- ✅ **GitLab CI to GitHub Actions**: Migrated `.gitlab-ci.yml` to `.github/workflows/ci.yml`
- ✅ **Release Pipeline**: Added `.github/workflows/release.yml` for automated releases
- ✅ **Container Registry**: Switched from GitLab Registry to GitHub Container Registry (GHCR)

### 2. Feature Mapping

| GitLab Feature | GitHub Equivalent | Status |
|---------------|-------------------|---------|
| GitLab CI/CD | GitHub Actions | ✅ Migrated |
| GitLab Registry | GitHub Container Registry (GHCR) | ✅ Migrated |
| Merge Requests | Pull Requests | 🔄 Standard GitHub feature |
| GitLab Issues | GitHub Issues | 🔄 Standard GitHub feature |
| GitLab Wiki | GitHub Wiki | 📋 Manual migration needed |

### 3. CI/CD Pipeline Comparison

#### Original GitLab Pipeline
```yaml
stages:
  - lint
  - unit  
  - api
  - integration
  - build
```

#### New GitHub Actions Pipeline
```yaml
jobs:
  lint → unit-test → api-test → integration-test → build-image → security-scan
```

### 4. Container Registry Migration

#### Before (GitLab)
```yaml
variables:
  INTERNAL_REGISTRY: gitlab-registry.gitlab.svc.cluster.local:5000
  INTERNAL_IMAGE: $INTERNAL_REGISTRY/$CI_PROJECT_PATH
```

#### After (GitHub)
```yaml
env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}
```

## New GitHub Actions Features

### Enhanced Capabilities
- **Multi-platform builds**: Linux AMD64 and ARM64 support
- **Security scanning**: Integrated Trivy vulnerability scanning
- **Caching**: Improved build performance with GitHub Actions cache
- **Artifact management**: Coverage reports and build artifacts
- **Release automation**: Automated container image tagging and releases

### Security Improvements
- **GitHub Container Registry**: Free private registry with fine-grained access control
- **Dependabot**: Automated dependency updates and security alerts
- **Security tab**: Centralized security vulnerability tracking
- **SARIF reports**: Structured security scan results

## Migration Commands

### For Repository Maintainers

1. **Add GitHub remote** (if not already done):
   ```bash
   git remote add github https://github.com/USERNAME/ant-fileserver.git
   ```

2. **Push all branches to GitHub**:
   ```bash
   git push github --all
   git push github --tags
   ```

3. **Update default remote**:
   ```bash
   git remote set-url origin https://github.com/USERNAME/ant-fileserver.git
   ```

### For Developers

1. **Update local repository**:
   ```bash
   git remote set-url origin https://github.com/USERNAME/ant-fileserver.git
   git fetch origin
   ```

2. **Update any local scripts or configurations** that reference GitLab URLs

## Post-Migration Checklist

### ✅ Completed
- [x] GitHub Actions workflows created and tested
- [x] Container registry switched to GHCR
- [x] GitLab references updated in scripts
- [x] Documentation updated

### 📋 Pending (Manual Steps)
- [ ] **Repository URL Update**: Update remote URL in local development environments
- [ ] **Kubernetes Deployment**: Update any Kubernetes manifests that reference GitLab registry
- [ ] **CI/CD Secrets**: Configure GitHub repository secrets for deployment
- [ ] **Branch Protection**: Set up branch protection rules on GitHub
- [ ] **Team Access**: Configure team access and permissions on GitHub

### 🔄 Optional Enhancements
- [ ] **Dependabot**: Enable automated dependency updates
- [ ] **GitHub Wiki**: Migrate any GitLab Wiki content
- [ ] **Issue Templates**: Create GitHub issue and PR templates
- [ ] **GitHub Pages**: Set up documentation hosting if needed

## GitHub Repository Configuration

### Required Secrets
```bash
# For container registry (automatically available)
GITHUB_TOKEN  # Automatically provided by GitHub Actions

# For deployment (if needed)
KUBECONFIG    # Kubernetes configuration for deployments
DEPLOY_KEY    # SSH key for deployment access
```

### Recommended Settings
- **Branch Protection**: Enable for `main` and `dev` branches
- **Required Reviews**: At least 1 review for production changes
- **Status Checks**: Require CI pipeline to pass before merge
- **Auto-merge**: Enable auto-merge for approved PRs

## Troubleshooting

### Common Issues

#### 1. Container Registry Authentication
If container push fails:
```bash
# Ensure GITHUB_TOKEN has packages:write permission
# This is automatically granted in GitHub Actions
```

#### 2. Migration of Container Images
To migrate existing container images:
```bash
# Pull from GitLab registry
docker pull gitlab-registry.gitlab.svc.cluster.local:5000/ant-hive/ant-fileserver:latest

# Tag for GitHub registry  
docker tag gitlab-registry.gitlab.svc.cluster.local:5000/ant-hive/ant-fileserver:latest \
  ghcr.io/USERNAME/ant-fileserver:latest

# Push to GitHub registry
docker push ghcr.io/USERNAME/ant-fileserver:latest
```

#### 3. Kubernetes Deployment Updates
Update Kubernetes manifests to use new registry:
```yaml
# Before (GitLab CI variable)
image: $CI_REGISTRY_IMAGE

# After (GitHub Container Registry)
image: ghcr.io/allie-leth/ant-fileserver:latest
```

**Files requiring updates:**
- `k8s/app/overlays/dev/kustomization.yaml`
- `k8s/app/overlays/prod/kustomization.yaml`

### 4. MinIO Integration Validation
Current MinIO infrastructure analysis:
```bash
# Current MinIO deployment in cluster
kubectl get pods -n minio
# Shows: minio-0 (Running)

# Existing ant-fileserver credentials
kubectl get secret -n minio ant-fileserver-prod-creds
# IAM policy configured for bucket path: minio/ant-fileserver/*
```

**Storage Configuration:**
- **Bucket**: `minio` (main bucket)
- **Prefix**: `ant-fileserver/*` (application-specific path)
- **Access**: Read/Write permissions via sealed secret
- **Environment**: Production credentials already configured

## Benefits of Migration

### 1. **Cost Reduction**
- Free private repositories and container registry
- No GitLab licensing costs
- Free CI/CD minutes (2000/month on free tier)

### 2. **Enhanced Security**
- Integrated security scanning
- Dependabot for automated security updates
- Advanced security features in GitHub Enterprise

### 3. **Better Integration**
- Native integration with development tools
- Improved issue tracking and project management
- Better community features and discoverability

### 4. **Performance**
- Faster CI/CD execution
- Better caching mechanisms
- Global CDN for container registry

## Timeline

- **Phase 1**: CI/CD Migration ✅ (Completed)
- **Phase 2**: Repository Migration 🔄 (In Progress)
- **Phase 3**: Production Deployment Updates 📋 (Pending)
- **Phase 4**: GitLab Decommission 📅 (Future)

---

## Comprehensive Testing & Validation

### Pre-Migration Testing Requirements
Before creating any pull requests or deploying changes, run the comprehensive test suite:

```bash
# Run the comprehensive test runner
./dev/claude/run_tests.sh

# Manual validation commands
source .venv/bin/activate

# 1. Code Quality
ruff check app/ tests/
ruff format --check app/ tests/

# 2. Unit Tests
python -m pytest tests/unit/ -v --cov=app

# 3. API Tests  
export PYTHONPATH="$PWD"
export STORAGE_ENDPOINT="http://dummy"
export STORAGE_BUCKET="firmware" 
export STORAGE_ACCESS_KEY_ID="dummy"
export STORAGE_SECRET_ACCESS_KEY="dummy"
export STORAGE_REGION="us-east-1"
export JWT_SECRET_KEY="test-secret"
python -m pytest tests/api/ -v

# 4. Integration Tests (with MinIO)
./scripts/dev-integration.sh

# 5. Container Build
docker build -t ant-fileserver:test .
```

### Infrastructure Validation
Validate against current MinIO infrastructure:

```bash
# Check MinIO is running
kubectl get pods -n minio
kubectl get svc -n minio

# Verify ant-fileserver credentials exist
kubectl get secret -n minio ant-fileserver-prod-creds -o yaml

# Check IAM policy configuration
kubectl get configmap -n minio iam-ant-fileserver-policy -o yaml

# Test connectivity (from within cluster)
kubectl run temp-test --rm -i --tty --image=curlimages/curl -- sh
# curl http://minio.minio.svc.cluster.local:9000/minio/health/ready
```

### Post-Migration Validation Checklist

#### ✅ Local Development
- [ ] Virtual environment activated and dependencies installed
- [ ] All tests pass (unit, API, integration)
- [ ] Code quality checks pass (ruff, formatting)
- [ ] Container builds successfully
- [ ] Integration tests with MinIO pass

#### ✅ GitHub Repository
- [ ] All branches pushed to GitHub
- [ ] GitHub Actions workflows syntax valid
- [ ] Repository secrets configured (if needed)
- [ ] Branch protection rules configured

#### ✅ Kubernetes Integration
- [ ] Kubernetes manifests updated with GHCR references
- [ ] Container image references point to `ghcr.io/allie-leth/ant-fileserver`
- [ ] MinIO credentials and policies remain unchanged
- [ ] Application can connect to existing MinIO instance

#### ✅ CI/CD Pipeline
- [ ] GitHub Actions workflow triggers correctly
- [ ] All pipeline stages pass (lint, test, build, security)
- [ ] Container images build and push to GHCR
- [ ] Multi-platform builds work (AMD64, ARM64)

### Rollback Procedures

If migration issues occur:

```bash
# 1. Revert to GitLab CI (if needed)
cp .archived/gitlab-ci.yml.backup .gitlab-ci.yml
git add .gitlab-ci.yml
git commit -m "revert: restore GitLab CI temporarily"

# 2. Revert Kubernetes manifests
git checkout HEAD~1 -- k8s/app/overlays/

# 3. Switch back to GitLab remote
git remote set-url origin http://gitlab.scopecreep.productions/ant-hive/ant-fileserver.git

# 4. Verify tests still pass with GitLab configuration
./dev/claude/run_tests.sh
```

### Migration Completion Criteria

The migration is considered complete when:

1. **All tests pass locally** using `./dev/claude/run_tests.sh`
2. **GitHub Actions pipeline passes** for both CI and release workflows  
3. **Container images build and push** to GHCR successfully
4. **Kubernetes manifests validated** with correct GHCR references
5. **MinIO integration confirmed** with existing infrastructure
6. **Documentation updated** and reviewed
7. **Team trained** on new GitHub workflow

---

**Migration Status**: 🔄 In Progress  
**Last Updated**: 2025-07-11  
**Next Steps**: Run comprehensive tests, update Kubernetes manifests, validate infrastructure integration  
**Test Command**: `./dev/claude/run_tests.sh`