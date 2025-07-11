# MinIO GitOps Setup Guide

## Overview

This document describes how to properly configure MinIO for ant-fileserver using GitOps principles, avoiding direct container modifications.

## Current Issue

The ant-fileserver needs specific MinIO configuration:
- User credentials (already exist via sealed secret)
- IAM policy for bucket access 
- Bucket creation and permissions

## GitOps Solution

### 1. Apply Configuration via GitOps Repository

The proper fix should be applied to the GitOps repository at `/home/leth/gitops/infra/minio/overlay/prod/`:

```bash
# Copy the fixes to GitOps repository
cp minio-config-fixes.yaml /home/leth/gitops/infra/minio/overlay/prod/

# Update the existing IAM policy
cp minio-config-fixes.yaml /tmp/
yq '.data."ant-fileserver.json"' /tmp/minio-config-fixes.yaml > /tmp/policy.json

# Edit the existing policy file
# /home/leth/gitops/infra/minio/overlay/prod/iam-ant-fileserver-policy.yaml

# Add the jobs to kustomization.yaml
# /home/leth/gitops/infra/minio/overlay/prod/kustomization.yaml
```

### 2. Required Changes

#### A. Update IAM Policy
File: `/home/leth/gitops/infra/minio/overlay/prod/iam-ant-fileserver-policy.yaml`

Add support for multiple buckets:
- `arn:aws:s3:::minio/ant-fileserver/*`
- `arn:aws:s3:::minio-dev/ant-fileserver/*` 
- `arn:aws:s3:::minio-staging/ant-fileserver/*`

#### B. Add Setup Jobs
Add Jobs to create bucket and user setup (see `minio-config-fixes.yaml`)

#### C. Update Kustomization
Add the new resources to the kustomization.yaml

### 3. Deployment

```bash
# In GitOps repository
cd /home/leth/gitops/infra/minio/overlay/prod
git add .
git commit -m "feat: update MinIO config for ant-fileserver integration"
git push

# Changes will be applied by Flux automatically
# Monitor with:
kubectl get jobs -n minio
kubectl logs job/setup-ant-fileserver-user -n minio
```

### 4. Validation

After GitOps deployment:

```bash
# Run the production test (should now pass)
./scripts/test-production-minio.sh

# Check user exists
kubectl exec -n minio minio-0 -- mc admin user list local

# Check policy
kubectl exec -n minio minio-0 -- mc admin policy info local ant-fileserver-policy
```

## Anti-Patterns Avoided

❌ **Direct container exec**: `kubectl exec -n minio minio-0 -- mc admin user add`
❌ **Manual API calls**: Direct MinIO admin API usage
❌ **Imperative commands**: Any kubectl create/apply without Git

✅ **GitOps workflow**: All changes via Git commits
✅ **Declarative config**: YAML manifests for all resources
✅ **Reproducible**: Can recreate entire setup from Git

## Testing Approach

Use the existing test scripts which validate the configuration but don't modify it:

```bash
# This is correct - tests configuration without modifying
./scripts/test-production-minio.sh

# This would be wrong - modifies live system
# kubectl exec ... mc admin user add
```

## Rollback

If issues occur, rollback via Git:

```bash
git revert <commit>
git push
# Flux will automatically revert changes
```