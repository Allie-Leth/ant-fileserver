#!/bin/bash
# Test script to verify CloudFlare tunnel configuration changes
# For remotely-managed tunnels (using TUNNEL_TOKEN)

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${YELLOW}CloudFlare Remotely-Managed Tunnel Configuration Test${NC}"
echo "===================================================="

# Check current tunnel status
check_tunnel_status() {
    echo -e "\n${BLUE}Current Tunnel Configuration:${NC}"
    
    # Get tunnel pods
    TUNNEL_PODS=$(kubectl get pods -n tunnels -l app=cloudflared -o name)
    
    for pod in $TUNNEL_PODS; do
        echo -e "\n${YELLOW}Checking $pod${NC}"
        
        # Check if tunnel has config file
        echo "Checking for config file:"
        kubectl exec -n tunnels $pod -- ls -la /etc/cloudflared/ 2>/dev/null || echo "No /etc/cloudflared directory"
        
        # Check environment variables
        echo -e "\nEnvironment variables:"
        kubectl exec -n tunnels $pod -- env | grep -E "(TUNNEL|CLOUDFLARE)" || echo "No tunnel env vars"
        
        # Check tunnel info
        echo -e "\nTunnel info (if available):"
        kubectl exec -n tunnels $pod -- cloudflared tunnel info 2>&1 | head -10 || true
    done
}

# Test current behavior
test_current_behavior() {
    echo -e "\n${BLUE}Testing Current Chunked Transfer Behavior:${NC}"
    
    # Create 3MB test file
    dd if=/dev/zero of=/tmp/test_3mb.bin bs=1M count=3 2>/dev/null
    
    echo "Testing 3MB chunked upload (current config):"
    START_TIME=$(date +%s)
    
    RESULT=$(curl -X PATCH \
        "https://gitlab-registry.scopecreep.productions/v2/test/blobs/uploads/config-test-$(date +%s)" \
        -H "Transfer-Encoding: chunked" \
        -H "Content-Type: application/octet-stream" \
        --data-binary @/tmp/test_3mb.bin \
        -w "HTTP_CODE:%{http_code},SIZE_UPLOAD:%{size_upload},TIME:%{time_total}" \
        -o /dev/null -s --max-time 10 2>&1) || RESULT="FAILED"
    
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    
    if [[ "$RESULT" == *"HTTP_CODE:502"* ]] || [[ "$RESULT" == *"SIZE_UPLOAD:2"* ]]; then
        echo -e "${RED}✗ Chunked transfer limited (as expected with current config)${NC}"
        echo "  Result: $RESULT"
        echo "  Duration: ${DURATION}s"
    elif [[ "$RESULT" == *"HTTP_CODE:401"* ]] && [[ "$RESULT" == *"SIZE_UPLOAD:3145728"* ]]; then
        echo -e "${GREEN}✓ Chunked transfer succeeded! Config may be fixed${NC}"
        echo "  Result: $RESULT"
    else
        echo -e "${YELLOW}⚠ Unexpected result${NC}"
        echo "  Result: $RESULT"
    fi
    
    rm -f /tmp/test_3mb.bin
}

# Generate config suggestions
suggest_dashboard_config() {
    echo -e "\n${BLUE}CloudFlare Dashboard Configuration Steps:${NC}"
    echo "Since you're using a remotely-managed tunnel (TUNNEL_TOKEN),"
    echo "configuration must be done through the CloudFlare dashboard:"
    echo ""
    echo "1. Log into CloudFlare Zero Trust Dashboard"
    echo "2. Navigate to: Access → Tunnels"
    echo "3. Find your tunnel (check ID below)"
    echo "4. Click 'Configure' → 'Public Hostname' tab"
    echo "5. Add or edit the hostname: gitlab-registry.scopecreep.productions"
    echo "6. Under 'Additional application settings', add:"
    echo "   - Origin Request → Disable chunked encoding: ✓ (checked)"
    echo "   - Origin Request → HTTP2 Origin: ✓ (checked)"
    echo ""
    
    # Try to extract tunnel ID from logs
    echo -e "${YELLOW}Attempting to find Tunnel ID:${NC}"
    kubectl logs deployment/cluster-cloudflared -n tunnels --tail=200 | \
        grep -E "(tunnel|Tunnel).*[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}" | \
        head -5 || echo "Could not find tunnel ID in logs"
}

# Test alternative: Local tunnel config
test_local_config_option() {
    echo -e "\n${BLUE}Alternative: Convert to Locally-Managed Tunnel${NC}"
    echo "If dashboard changes aren't possible, you can convert to local config:"
    
    cat << 'EOF'

1. Create config.yaml:
---
tunnel: <YOUR-TUNNEL-ID>
credentials-file: /etc/cloudflared/creds.json

# Default origin settings
originRequest:
  disableChunkedEncoding: true
  http2Origin: true
  connectTimeout: 30s

ingress:
  # GitLab Registry with special handling
  - hostname: gitlab-registry.scopecreep.productions
    service: https://gitlab-registry.gitlab.svc.cluster.local:5000
    originRequest:
      disableChunkedEncoding: true
      http2Origin: true
      noTLSVerify: true  # If using self-signed certs
      
  # Other services route to nginx
  - hostname: "*.scopecreep.productions"
    service: https://ingress-nginx-controller.ingress-nginx.svc.cluster.local:443
    originRequest:
      http2Origin: true
      
  # Catch-all
  - service: http_status:404

2. Create ConfigMap:
kubectl create configmap tunnel-config -n tunnels --from-file=config.yaml

3. Update deployment to use config file instead of token

EOF
}

# Create test container for podman push
create_test_container() {
    echo -e "\n${BLUE}Creating Test Container for Podman Push:${NC}"
    
    cat > /tmp/test-push-dockerfile << 'EOF'
FROM alpine:latest
RUN apk add --no-cache curl podman skopeo
WORKDIR /test

# Test script
RUN echo '#!/bin/sh' > /test/test-push.sh && \
    echo 'echo "Testing podman push through CloudFlare..."' >> /test/test-push.sh && \
    echo 'podman pull docker.io/hello-world:latest' >> /test/test-push.sh && \
    echo 'podman tag hello-world:latest $1/test-push:latest' >> /test/test-push.sh && \
    echo 'podman push $1/test-push:latest 2>&1 | grep -E "(Copying|Error|digest)"' >> /test/test-push.sh && \
    chmod +x /test/test-push.sh

CMD ["/bin/sh"]
EOF

    echo "Dockerfile created at /tmp/test-push-dockerfile"
    echo "Build with: docker build -f /tmp/test-push-dockerfile -t test-push:latest ."
    echo "Run with: docker run -it test-push:latest ./test-push.sh gitlab-registry.scopecreep.productions"
}

# Main execution
echo -e "\n${YELLOW}Running Tunnel Configuration Tests${NC}"
echo "=================================="

check_tunnel_status
test_current_behavior
suggest_dashboard_config
test_local_config_option
create_test_container

echo -e "\n${BLUE}Next Steps:${NC}"
echo "1. Run the test script to confirm current behavior"
echo "2. Apply configuration changes via CloudFlare dashboard"
echo "3. Wait 1-2 minutes for changes to propagate"
echo "4. Re-run this script to verify the fix worked"
echo "5. Test actual podman push once confirmed"

echo -e "\n${YELLOW}Quick Test Command:${NC}"
echo "curl -X PATCH https://gitlab-registry.scopecreep.productions/v2/test/blobs/uploads/test-\$(date +%s) \\"
echo "  -H 'Transfer-Encoding: chunked' --data-binary @<(dd if=/dev/zero bs=1M count=3 2>/dev/null) \\"
echo "  -w 'Result: %{http_code}, Uploaded: %{size_upload} bytes\n' -o /dev/null -s"