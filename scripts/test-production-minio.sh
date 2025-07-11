#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# Production MinIO Integration Test
# 
# Tests the ant-fileserver against the actual production MinIO instance
# running in the k3s cluster using real credentials and bucket structure.
###############################################################################

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${BLUE}[$(date +'%H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Test counter
TESTS_RUN=0
TESTS_PASSED=0

run_test() {
    local test_name="$1"
    local test_cmd="$2"
    
    TESTS_RUN=$((TESTS_RUN + 1))
    log "Running test: $test_name"
    
    if eval "$test_cmd"; then
        success "✅ $test_name"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        error "❌ $test_name"
        return 1
    fi
}

# Function to extract credentials from Kubernetes secrets
setup_production_credentials() {
    log "Extracting production MinIO credentials from Kubernetes"
    
    # Check if kubectl is available and we can access the cluster
    if ! kubectl get pods -n minio >/dev/null 2>&1; then
        error "Cannot access Kubernetes cluster or minio namespace"
        exit 1
    fi
    
    # Extract MinIO credentials from sealed secret
    if ! kubectl get secret -n minio ant-fileserver-prod-creds >/dev/null 2>&1; then
        error "ant-fileserver-prod-creds secret not found in minio namespace"
        exit 1
    fi
    
    # Get MinIO service endpoint
    local MINIO_IP=$(kubectl get service -n minio minio -o jsonpath='{.spec.clusterIP}')
    if [[ -z "$MINIO_IP" ]]; then
        error "Could not determine MinIO cluster IP"
        exit 1
    fi
    
    # Export environment variables for production MinIO
    export STORAGE_ENDPOINT="http://${MINIO_IP}:9000"
    export STORAGE_BUCKET="minio"  # Main bucket as per IAM policy
    export STORAGE_REGION="us-east-1"
    export JWT_SECRET_KEY="production-test-secret"
    
    # Extract and decode credentials
    export STORAGE_ACCESS_KEY_ID=$(kubectl get secret -n minio ant-fileserver-prod-creds -o jsonpath='{.data.accessKey}' | base64 -d)
    export STORAGE_SECRET_ACCESS_KEY=$(kubectl get secret -n minio ant-fileserver-prod-creds -o jsonpath='{.data.secretKey}' | base64 -d)
    
    log "Production MinIO configuration:"
    log "  Endpoint: $STORAGE_ENDPOINT"
    log "  Bucket: $STORAGE_BUCKET"
    log "  Access Key: ${STORAGE_ACCESS_KEY_ID:0:8}..."
    log "  Region: $STORAGE_REGION"
}

# Function to test MinIO connectivity
test_minio_connectivity() {
    log "Testing MinIO connectivity and authentication"
    
    # Create a temporary test script
    cat > /tmp/test_minio_connectivity.py << 'EOF'
import os
import sys
import boto3
from botocore.exceptions import ClientError

def test_connectivity():
    try:
        # Create S3 client with production credentials
        s3 = boto3.client(
            "s3",
            endpoint_url=os.environ["STORAGE_ENDPOINT"],
            aws_access_key_id=os.environ["STORAGE_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["STORAGE_SECRET_ACCESS_KEY"],
            region_name=os.environ.get("STORAGE_REGION", "us-east-1"),
        )
        
        # Test 1: List buckets (should work with our credentials)
        print("Testing bucket listing...")
        response = s3.list_buckets()
        buckets = [bucket['Name'] for bucket in response['Buckets']]
        print(f"Available buckets: {buckets}")
        
        bucket_name = os.environ["STORAGE_BUCKET"]
        if bucket_name not in buckets:
            print(f"ERROR: Expected bucket '{bucket_name}' not found")
            return False
            
        # Test 2: List objects in ant-fileserver prefix
        print(f"Testing object listing in bucket '{bucket_name}' with prefix 'ant-fileserver/'...")
        try:
            response = s3.list_objects_v2(
                Bucket=bucket_name,
                Prefix="ant-fileserver/",
                MaxKeys=10
            )
            object_count = response.get('KeyCount', 0)
            print(f"Found {object_count} objects with ant-fileserver/ prefix")
        except ClientError as e:
            print(f"Error listing objects: {e}")
            return False
            
        # Test 3: Try to put a small test object
        print("Testing object upload...")
        test_key = "ant-fileserver/test/connectivity-test.txt"
        test_content = "MinIO connectivity test - this file can be deleted"
        
        try:
            s3.put_object(
                Bucket=bucket_name,
                Key=test_key,
                Body=test_content.encode(),
                ContentType="text/plain"
            )
            print(f"Successfully uploaded test object: {test_key}")
            
            # Test 4: Try to get the object back
            response = s3.get_object(Bucket=bucket_name, Key=test_key)
            retrieved_content = response['Body'].read().decode()
            
            if retrieved_content == test_content:
                print("Successfully retrieved test object with correct content")
            else:
                print("ERROR: Retrieved content doesn't match uploaded content")
                return False
                
            # Test 5: Clean up test object
            s3.delete_object(Bucket=bucket_name, Key=test_key)
            print("Successfully cleaned up test object")
            
        except ClientError as e:
            print(f"Error during upload/download test: {e}")
            return False
            
        print("All MinIO connectivity tests passed!")
        return True
        
    except Exception as e:
        print(f"MinIO connectivity test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_connectivity()
    sys.exit(0 if success else 1)
EOF

    # Run the connectivity test
    python /tmp/test_minio_connectivity.py
}

# Function to run production integration tests
test_production_integration() {
    log "Running production integration tests with real MinIO"
    
    # Set PYTHONPATH for imports
    export PYTHONPATH="$PWD"
    
    # Create a production-specific test
    cat > /tmp/test_production_integration.py << 'EOF'
import os
import sys
import base64
import pytest
from app.blueprints.firmware.service import FirmwareService

def test_firmware_service_production():
    """Test FirmwareService against production MinIO with real credentials."""
    
    # Create service instance with production settings
    service = FirmwareService(
        endpoint_url=os.environ["STORAGE_ENDPOINT"],
        bucket=os.environ["STORAGE_BUCKET"],
        access_key_id=os.environ["STORAGE_ACCESS_KEY_ID"],
        secret_access_key=os.environ["STORAGE_SECRET_ACCESS_KEY"],
        region=os.environ.get("STORAGE_REGION", "us-east-1"),
    )
    
    # Test data
    test_vendor = "test-vendor"
    test_device = "test-device"
    test_version = "0.0.1-test"
    test_firmware = b"test firmware binary content"
    
    try:
        print(f"Testing firmware upload for {test_vendor}/{test_device} v{test_version}")
        
        # Test upload
        payload = {
            "version": test_version,
            "firmware_b64": base64.b64encode(test_firmware).decode(),
        }
        
        result = service.upload_firmware(test_vendor, test_device, payload)
        print(f"Upload result: {result}")
        
        # Test list firmware
        print("Testing firmware listing...")
        firmware_list = service.list_firmware(test_vendor, test_device)
        print(f"Found {len(firmware_list)} firmware entries")
        
        # Verify our test firmware is in the list
        test_firmware_found = any(fw.version == test_version for fw in firmware_list)
        if not test_firmware_found:
            raise Exception(f"Test firmware version {test_version} not found in list")
            
        # Test get latest
        print("Testing get latest firmware...")
        latest = service.get_latest(test_vendor, test_device)
        print(f"Latest firmware: {latest.version}")
        
        # Test presigned URL generation
        print("Testing presigned URL generation...")
        latest_fw = next(fw for fw in firmware_list if fw.version == test_version)
        presigned_url = service.get_presigned_url(latest_fw.object_key)
        print(f"Generated presigned URL: {presigned_url[:50]}...")
        
        print("All production integration tests passed!")
        return True
        
    except Exception as e:
        print(f"Production integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cleanup: try to delete the test firmware
        try:
            import boto3
            s3 = boto3.client(
                "s3",
                endpoint_url=os.environ["STORAGE_ENDPOINT"],
                aws_access_key_id=os.environ["STORAGE_ACCESS_KEY_ID"],
                aws_secret_access_key=os.environ["STORAGE_SECRET_ACCESS_KEY"],
                region_name=os.environ.get("STORAGE_REGION", "us-east-1"),
            )
            
            # List and delete test objects
            response = s3.list_objects_v2(
                Bucket=os.environ["STORAGE_BUCKET"],
                Prefix=f"ant-fileserver/{test_vendor}/{test_device}/"
            )
            
            if 'Contents' in response:
                for obj in response['Contents']:
                    if test_version in obj['Key']:
                        print(f"Cleaning up test object: {obj['Key']}")
                        s3.delete_object(Bucket=os.environ["STORAGE_BUCKET"], Key=obj['Key'])
                        
        except Exception as cleanup_error:
            print(f"Warning: Cleanup failed: {cleanup_error}")

if __name__ == "__main__":
    success = test_firmware_service_production()
    sys.exit(0 if success else 1)
EOF

    # Run the production integration test
    python /tmp/test_production_integration.py
}

# Function to validate IAM permissions
test_iam_permissions() {
    log "Testing IAM permissions and bucket access patterns"
    
    cat > /tmp/test_iam_permissions.py << 'EOF'
import os
import boto3
from botocore.exceptions import ClientError

def test_iam_permissions():
    """Test that our credentials have the correct IAM permissions."""
    
    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ["STORAGE_ENDPOINT"],
        aws_access_key_id=os.environ["STORAGE_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["STORAGE_SECRET_ACCESS_KEY"],
        region_name=os.environ.get("STORAGE_REGION", "us-east-1"),
    )
    
    bucket_name = os.environ["STORAGE_BUCKET"]
    
    try:
        # Test 1: Should be able to list objects with ant-fileserver prefix
        print("Testing list permissions for ant-fileserver/ prefix...")
        s3.list_objects_v2(Bucket=bucket_name, Prefix="ant-fileserver/")
        print("✅ List permission works for ant-fileserver/ prefix")
        
        # Test 2: Should be able to put objects in ant-fileserver/ path
        print("Testing put permissions for ant-fileserver/ path...")
        test_key = "ant-fileserver/test/iam-test.txt"
        s3.put_object(Bucket=bucket_name, Key=test_key, Body=b"IAM test content")
        print("✅ Put permission works for ant-fileserver/ path")
        
        # Test 3: Should be able to get objects from ant-fileserver/ path
        print("Testing get permissions for ant-fileserver/ path...")
        s3.get_object(Bucket=bucket_name, Key=test_key)
        print("✅ Get permission works for ant-fileserver/ path")
        
        # Test 4: Should NOT be able to list objects outside ant-fileserver/ prefix
        print("Testing that access is restricted outside ant-fileserver/ prefix...")
        try:
            s3.list_objects_v2(Bucket=bucket_name, Prefix="other-app/")
            print("⚠️  Warning: Could list objects outside ant-fileserver/ prefix")
        except ClientError as e:
            if e.response['Error']['Code'] in ['AccessDenied', 'Forbidden']:
                print("✅ Access correctly denied for other prefixes")
            else:
                raise
        
        # Test 5: Should NOT be able to put objects outside ant-fileserver/ path
        print("Testing that put is restricted outside ant-fileserver/ path...")
        try:
            s3.put_object(Bucket=bucket_name, Key="other-app/test.txt", Body=b"test")
            print("⚠️  Warning: Could put objects outside ant-fileserver/ path")
            # Clean up if we accidentally succeeded
            s3.delete_object(Bucket=bucket_name, Key="other-app/test.txt")
        except ClientError as e:
            if e.response['Error']['Code'] in ['AccessDenied', 'Forbidden']:
                print("✅ Put correctly denied for other paths")
            else:
                raise
        
        # Cleanup
        s3.delete_object(Bucket=bucket_name, Key=test_key)
        print("✅ IAM permissions test completed successfully")
        return True
        
    except Exception as e:
        print(f"IAM permissions test failed: {e}")
        return False

if __name__ == "__main__":
    import sys
    success = test_iam_permissions()
    sys.exit(0 if success else 1)
EOF

    python /tmp/test_iam_permissions.py
}

# Main execution
main() {
    log "Production MinIO Integration Test Suite"
    log "======================================"
    
    # Change to project root
    cd "$(dirname "${BASH_SOURCE[0]}")/.."
    
    # Activate virtual environment
    if [ -d ".venv" ]; then
        source .venv/bin/activate
    else
        error "Virtual environment not found. Run 'python -m venv .venv' first."
        exit 1
    fi
    
    # Setup production credentials
    setup_production_credentials
    
    # Run test suite
    echo
    log "Running production MinIO integration tests..."
    
    run_test "MinIO Connectivity" "test_minio_connectivity"
    run_test "IAM Permissions" "test_iam_permissions"  
    run_test "Production Integration" "test_production_integration"
    
    # Summary
    echo
    log "Test Results Summary"
    log "==================="
    log "Tests Run: $TESTS_RUN"
    success "Tests Passed: $TESTS_PASSED"
    
    if [ $TESTS_PASSED -eq $TESTS_RUN ]; then
        success "🎉 All production MinIO integration tests passed!"
        log "The ant-fileserver is ready for deployment to production MinIO"
    else
        error "❌ Some tests failed. Production MinIO integration needs attention."
        exit 1
    fi
    
    # Cleanup temporary files
    rm -f /tmp/test_*.py
}

# Run if called directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi