#!/usr/bin/env bash
set -euo pipefail

# Simple security context validation
# Use yq from PATH, with fallback locations
if command -v yq &> /dev/null; then
    YQ="yq"
elif [ -f "$HOME/.local/bin/yq" ]; then
    YQ="$HOME/.local/bin/yq"
elif [ -f "/usr/local/bin/yq" ]; then
    YQ="/usr/local/bin/yq"
else
    echo "Error: yq not found in PATH or standard locations"
    echo "Install yq: https://github.com/mikefarah/yq#install"
    exit 1
fi

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