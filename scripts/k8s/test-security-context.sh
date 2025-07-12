#!/usr/bin/env bash
set -euo pipefail

# Simple security context validation
YQ="$HOME/.local/bin/yq"

echo "Testing security contexts..."

# Generate manifests
kubectl kustomize k8s/app/base/ > /tmp/test-manifests.yaml

# Test each security setting
echo -n "Pod runAsNonRoot: "
$YQ e 'select(.kind == "Deployment") | .spec.template.spec.securityContext.runAsNonRoot' /tmp/test-manifests.yaml

echo -n "Container readOnlyRootFilesystem: "
$YQ e 'select(.kind == "Deployment") | .spec.template.spec.containers[0].securityContext.readOnlyRootFilesystem' /tmp/test-manifests.yaml

echo -n "Container allowPrivilegeEscalation: "
$YQ e 'select(.kind == "Deployment") | .spec.template.spec.containers[0].securityContext.allowPrivilegeEscalation' /tmp/test-manifests.yaml

echo -n "Capabilities dropped: "
$YQ e 'select(.kind == "Deployment") | .spec.template.spec.containers[0].securityContext.capabilities.drop[]' /tmp/test-manifests.yaml

echo -n "Seccomp profile: "
$YQ e 'select(.kind == "Deployment") | .spec.template.spec.containers[0].securityContext.seccompProfile.type' /tmp/test-manifests.yaml

echo -n "User ID: "
$YQ e 'select(.kind == "Deployment") | .spec.template.spec.securityContext.runAsUser' /tmp/test-manifests.yaml

# Cleanup
rm -f /tmp/test-manifests.yaml