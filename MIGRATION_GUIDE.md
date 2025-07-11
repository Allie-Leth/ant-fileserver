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
# Before
image: gitlab-registry.gitlab.svc.cluster.local:5000/ant-hive/ant-fileserver:latest

# After  
image: ghcr.io/USERNAME/ant-fileserver:latest
```

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

**Migration Status**: 🔄 In Progress  
**Last Updated**: 2025-07-11  
**Next Steps**: Repository URL updates and production deployment configuration