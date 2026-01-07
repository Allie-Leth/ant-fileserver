#!/bin/bash
# Test script to confirm CloudFlare chunked transfer solutions
# This script tests various approaches to fix the 2MB chunked transfer limit

set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}CloudFlare Chunked Transfer Solution Testing${NC}"
echo "============================================="

# Test configuration
REGISTRY_EXTERNAL="gitlab-registry.scopecreep.productions"
REGISTRY_INTERNAL="gitlab-registry.gitlab.svc.cluster.local:5000"
TEST_REPO="ant-hive/test-chunked-$(date +%s)"
TEST_IMAGE="hello-world:latest"

# Create test files of various sizes
echo "Creating test files..."
dd if=/dev/zero of=/tmp/test_1mb.bin bs=1M count=1 2>/dev/null
dd if=/dev/zero of=/tmp/test_2mb.bin bs=1M count=2 2>/dev/null
dd if=/dev/zero of=/tmp/test_3mb.bin bs=1M count=3 2>/dev/null
dd if=/dev/zero of=/tmp/test_5mb.bin bs=1M count=5 2>/dev/null

# Test 1: Confirm the problem - External registry with chunked encoding
test1_external_chunked() {
    echo -e "\n${YELLOW}Test 1: External Registry with Chunked Encoding${NC}"
    echo "Expected: Fail at ~2MB"
    
    for size in 1mb 2mb 3mb 5mb; do
        echo -n "Testing $size upload: "
        curl -X PATCH \
            "https://$REGISTRY_EXTERNAL/v2/$TEST_REPO/blobs/uploads/test-$size-$(date +%s)" \
            -H "Transfer-Encoding: chunked" \
            -H "Content-Type: application/octet-stream" \
            --data-binary @/tmp/test_${size}.bin \
            -w "HTTP %{http_code}, Uploaded: %{size_upload} bytes\n" \
            -o /dev/null -s --max-time 10 || echo "Failed/Timeout"
    done
}

# Test 2: Confirm workaround - External registry without chunked
test2_external_no_chunked() {
    echo -e "\n${YELLOW}Test 2: External Registry WITHOUT Chunked Encoding${NC}"
    echo "Expected: All sizes succeed"
    
    for size in 1mb 2mb 3mb 5mb; do
        echo -n "Testing $size upload: "
        SIZE_BYTES=$(stat -c%s /tmp/test_${size}.bin 2>/dev/null || stat -f%z /tmp/test_${size}.bin)
        curl -X PATCH \
            "https://$REGISTRY_EXTERNAL/v2/$TEST_REPO/blobs/uploads/test-$size-$(date +%s)" \
            -H "Content-Length: $SIZE_BYTES" \
            -H "Content-Type: application/octet-stream" \
            --data-binary @/tmp/test_${size}.bin \
            -w "HTTP %{http_code}, Uploaded: %{size_upload} bytes\n" \
            -o /dev/null -s --max-time 10 || echo "Failed/Timeout"
    done
}

# Test 3: Internal registry connectivity
test3_internal_registry() {
    echo -e "\n${YELLOW}Test 3: Internal Registry Direct Access${NC}"
    echo "Testing connectivity to internal registry..."
    
    # Test if we can reach internal registry
    if kubectl exec -n gitlab deployment/gitlab-gitlab-shell -- curl -s -o /dev/null -w "%{http_code}" http://$REGISTRY_INTERNAL/v2/ | grep -q "401\|200"; then
        echo -e "${GREEN}✓ Internal registry is reachable${NC}"
        
        # Test chunked upload to internal registry
        echo -n "Testing 5MB chunked upload to internal registry: "
        kubectl exec -n gitlab deployment/gitlab-gitlab-shell -- sh -c "
            dd if=/dev/zero bs=1M count=5 2>/dev/null | \
            curl -X PATCH \
                'http://$REGISTRY_INTERNAL/v2/test/blobs/uploads/internal-test-$(date +%s)' \
                -H 'Transfer-Encoding: chunked' \
                -H 'Content-Type: application/octet-stream' \
                --data-binary @- \
                -w 'HTTP %{http_code}, Uploaded: %{size_upload} bytes\n' \
                -o /dev/null -s --max-time 10
        " || echo "Failed"
    else
        echo -e "${RED}✗ Cannot reach internal registry${NC}"
    fi
}

# Test 4: HTTP/2 vs HTTP/1.1 behavior
test4_http_protocols() {
    echo -e "\n${YELLOW}Test 4: HTTP Protocol Comparison${NC}"
    
    echo "Testing HTTP/2 (should work):"
    curl -X PATCH \
        "https://$REGISTRY_EXTERNAL/v2/$TEST_REPO/blobs/uploads/http2-test-$(date +%s)" \
        --http2 \
        --data-binary @/tmp/test_5mb.bin \
        -w "Protocol: %{http_version}, HTTP %{http_code}, Uploaded: %{size_upload} bytes\n" \
        -o /dev/null -s --max-time 10 || echo "Failed"
    
    echo "Testing HTTP/1.1 with chunked (should fail at ~2MB):"
    curl -X PATCH \
        "https://$REGISTRY_EXTERNAL/v2/$TEST_REPO/blobs/uploads/http11-test-$(date +%s)" \
        --http1.1 \
        -H "Transfer-Encoding: chunked" \
        --data-binary @/tmp/test_5mb.bin \
        -w "Protocol: %{http_version}, HTTP %{http_code}, Uploaded: %{size_upload} bytes\n" \
        -o /dev/null -s --max-time 10 || echo "Failed"
}

# Test 5: Podman behavior simulation
test5_podman_simulation() {
    echo -e "\n${YELLOW}Test 5: Simulating Podman/Container Tool Behavior${NC}"
    
    # Test with container tool User-Agent
    echo "Testing with podman User-Agent and chunked encoding:"
    curl -X PATCH \
        "https://$REGISTRY_EXTERNAL/v2/$TEST_REPO/blobs/uploads/podman-test-$(date +%s)" \
        -H "User-Agent: containers/5.0.0 (github.com/containers/image)" \
        -H "Transfer-Encoding: chunked" \
        -H "Content-Type: application/octet-stream" \
        --data-binary @/tmp/test_5mb.bin \
        -w "HTTP %{http_code}, Uploaded: %{size_upload} bytes\n" \
        -o /dev/null -s --max-time 10 || echo "Failed"
}

# Test 6: CloudFlare Worker simulation
test6_worker_simulation() {
    echo -e "\n${YELLOW}Test 6: Testing Worker-like Solution${NC}"
    echo "Simulating what a CloudFlare Worker would do..."
    
    # This simulates converting chunked to Content-Length
    SIZE_BYTES=$(stat -c%s /tmp/test_5mb.bin 2>/dev/null || stat -f%z /tmp/test_5mb.bin)
    echo "Converting 5MB chunked request to Content-Length: $SIZE_BYTES"
    
    curl -X PATCH \
        "https://$REGISTRY_EXTERNAL/v2/$TEST_REPO/blobs/uploads/worker-test-$(date +%s)" \
        -H "Content-Length: $SIZE_BYTES" \
        -H "Content-Type: application/octet-stream" \
        -H "X-Converted-From-Chunked: true" \
        --data-binary @/tmp/test_5mb.bin \
        -w "HTTP %{http_code}, Uploaded: %{size_upload} bytes\n" \
        -o /dev/null -s --max-time 10 || echo "Failed"
}

# Main execution
echo -e "\n${YELLOW}Starting CloudFlare Solution Tests${NC}"
echo "=================================="

# Run tests based on user selection
if [ "$1" == "all" ] || [ -z "$1" ]; then
    test1_external_chunked
    test2_external_no_chunked
    test3_internal_registry
    test4_http_protocols
    test5_podman_simulation
    test6_worker_simulation
else
    case "$1" in
        1) test1_external_chunked ;;
        2) test2_external_no_chunked ;;
        3) test3_internal_registry ;;
        4) test4_http_protocols ;;
        5) test5_podman_simulation ;;
        6) test6_worker_simulation ;;
        *) echo "Usage: $0 [all|1|2|3|4|5|6]" ;;
    esac
fi

# Cleanup
rm -f /tmp/test_*.bin

echo -e "\n${YELLOW}Test Summary${NC}"
echo "============"
echo "If tests 1, 4, and 5 fail at ~2MB but tests 2 and 6 succeed with 5MB,"
echo "then CloudFlare chunked encoding limit is confirmed as the root cause."
echo ""
echo "Solutions that should work:"
echo "1. Configure tunnel with disableChunkedEncoding (requires dashboard access)"
echo "2. Use internal registry URL (if runners have cluster access)"
echo "3. Implement CloudFlare Worker to convert requests"
echo "4. Force HTTP/2 for all registry traffic"