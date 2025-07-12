#!/usr/bin/env bash
set -euo pipefail

# Install Kubernetes validation tools using Go

echo "Installing Kubernetes validation tools..."

# Set GOPATH if not set
export GOPATH="${GOPATH:-$HOME/go}"
export PATH="$GOPATH/bin:$PATH"

echo "Installing yq v4..."
go install github.com/mikefarah/yq/v4@latest

echo "Installing kubeconform..."
go install github.com/yannh/kubeconform/cmd/kubeconform@latest

echo "Installing pluto..."
go install github.com/FairwindsOps/pluto/v5@latest

echo
echo "Tools installed to: $GOPATH/bin"
echo "Make sure $GOPATH/bin is in your PATH:"
echo "  export PATH=\$PATH:$GOPATH/bin"
echo
echo "Verify installation:"
yq --version
kubeconform -v
pluto version