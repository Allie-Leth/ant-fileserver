#!/bin/bash
# Test script for internal registry solution

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}Testing Internal Registry Solution${NC}"
echo "==================================="

INTERNAL_REGISTRY="gitlab-registry.gitlab.svc.cluster.local:5000"
EXTERNAL_REGISTRY="gitlab-registry.scopecreep.productions"

# Test 1: Verify runners can access internal registry
echo -e "\n${YELLOW}Test 1: Runner Access to Internal Registry${NC}"
for runner in $(kubectl get pods -n gitlab-runner -o name | head -3); do
    echo -n "Testing $runner: "
    if kubectl exec -n gitlab-runner $runner -- curl -s -o /dev/null -w "%{http_code}" http://$INTERNAL_REGISTRY/v2/ | grep -q "401\|200"; then
        echo -e "${GREEN}✓ Can access internal registry${NC}"
    else
        echo -e "${RED}✗ Cannot access internal registry${NC}"
    fi
done

# Test 2: Test chunked upload to internal registry
echo -e "\n${YELLOW}Test 2: Chunked Upload to Internal Registry${NC}"
kubectl exec -n gitlab-runner $(kubectl get pods -n gitlab-runner -o name | head -1) -- sh -c "
    # Create 5MB test data
    dd if=/dev/zero bs=1M count=5 2>/dev/null | \
    curl -X PATCH \
        'http://$INTERNAL_REGISTRY/v2/test/blobs/uploads/internal-chunked-test-$(date +%s)' \
        -H 'Transfer-Encoding: chunked' \
        -H 'Content-Type: application/octet-stream' \
        --data-binary @- \
        -w 'Result: %{http_code}, Uploaded: %{size_upload} bytes\n' \
        -o /dev/null -s --max-time 10
" || echo "Test failed"

# Test 3: Compare external vs internal
echo -e "\n${YELLOW}Test 3: External vs Internal Registry Comparison${NC}"
echo "External registry (through CloudFlare):"
curl -X PATCH \
    "https://$EXTERNAL_REGISTRY/v2/test/blobs/uploads/external-test-$(date +%s)" \
    -H "Transfer-Encoding: chunked" \
    --data-binary @<(dd if=/dev/zero bs=1M count=3 2>/dev/null) \
    -w "  Result: %{http_code}, Uploaded: %{size_upload} bytes\n" \
    -o /dev/null -s --max-time 5 || echo "  Failed/Timeout"

echo -e "\n${YELLOW}Solution: Update .gitlab-ci.yml${NC}"
cat << 'EOF'

To use internal registry, update build-image job:

Replace:
  - skopeo copy ... "docker://$EXTERNAL_IMAGE:$CI_COMMIT_SHA"

With:
  - skopeo copy ... "docker://$INTERNAL_IMAGE:$CI_COMMIT_SHA"

Then in deployment jobs, pull from internal registry:
  image: $INTERNAL_IMAGE:$CI_COMMIT_SHA

Benefits:
- Bypasses CloudFlare completely
- No chunked encoding issues
- Faster transfers (internal network)
- More reliable

Note: External users won't be able to pull images unless they have VPN/cluster access.
EOF