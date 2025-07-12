#!/usr/bin/env bash
set -euo pipefail

# Script to install Kubernetes validation tools
# Run with: ./scripts/k8s/install-validation-tools.sh

BLUE='\033[0;34m'
GREEN='\033[0;32m'
NC='\033[0m'

log() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Detect OS and architecture
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)

case $ARCH in
    x86_64)
        ARCH="amd64"
        ;;
    aarch64|arm64)
        ARCH="arm64"
        ;;
    *)
        echo "Unsupported architecture: $ARCH"
        exit 1
        ;;
esac

log "Detected OS: $OS, Architecture: $ARCH"

# Create local bin directory if it doesn't exist
LOCAL_BIN="$HOME/.local/bin"
mkdir -p "$LOCAL_BIN"

# Add to PATH if not already there
if [[ ":$PATH:" != *":$LOCAL_BIN:"* ]]; then
    log "Adding $LOCAL_BIN to PATH"
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
    export PATH="$LOCAL_BIN:$PATH"
fi

# Install yq (v4)
log "Installing yq v4..."
YQ_VERSION="v4.35.2"
YQ_URL="https://github.com/mikefarah/yq/releases/download/${YQ_VERSION}/yq_${OS}_${ARCH}"
curl -sL "$YQ_URL" -o "$LOCAL_BIN/yq"
chmod +x "$LOCAL_BIN/yq"
success "yq installed: $(yq --version)"

# Install kubeconform
log "Installing kubeconform..."
KUBECONFORM_VERSION="0.6.4"
KUBECONFORM_URL="https://github.com/yannh/kubeconform/releases/download/v${KUBECONFORM_VERSION}/kubeconform-${OS}-${ARCH}.tar.gz"
curl -sL "$KUBECONFORM_URL" | tar xz -C "$LOCAL_BIN" kubeconform
chmod +x "$LOCAL_BIN/kubeconform"
success "kubeconform installed: $(kubeconform -v)"

# Install pluto
log "Installing pluto..."
PLUTO_VERSION="5.19.0"
PLUTO_URL="https://github.com/FairwindsOps/pluto/releases/download/v${PLUTO_VERSION}/pluto_${PLUTO_VERSION}_${OS}_${ARCH}.tar.gz"
curl -sL "$PLUTO_URL" | tar xz -C "$LOCAL_BIN" pluto
chmod +x "$LOCAL_BIN/pluto"
success "pluto installed: $(pluto version)"

echo
log "All tools installed successfully!"
log "Location: $LOCAL_BIN"
log "Make sure $LOCAL_BIN is in your PATH"
echo
log "You can now run the validation script with full features:"
log "  ./scripts/k8s/validate-manifests.sh"