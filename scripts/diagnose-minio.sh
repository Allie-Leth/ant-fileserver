#!/usr/bin/env bash
set -euo pipefail

###############################################################################
# MinIO Diagnosis Script
# 
# Diagnoses MinIO connectivity and user setup issues
###############################################################################

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${BLUE}[$(date +'%H:%M:%S')]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }
success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }

# Test MinIO connectivity with root credentials
test_root_connectivity() {
    log "Testing MinIO connectivity with root credentials"
    
    # Get MinIO cluster IP
    local MINIO_IP=$(kubectl get service -n minio minio -o jsonpath='{.spec.clusterIP}')
    local ROOT_USER=$(kubectl get secret -n minio minio-root-tmp -o jsonpath='{.data.user}' | base64 -d)
    local ROOT_PASS=$(kubectl get secret -n minio minio-root-tmp -o jsonpath='{.data.password}' | base64 -d)
    
    log "MinIO Root Connection Details:"
    log "  Endpoint: http://${MINIO_IP}:9000"
    log "  User: $ROOT_USER"
    log "  Password: ${ROOT_PASS:0:8}..."
    
    # Test with Python boto3
    cat > /tmp/test_root_minio.py << EOF
import boto3
from botocore.exceptions import ClientError
import sys

def test_root_access():
    try:
        s3 = boto3.client(
            "s3",
            endpoint_url="http://${MINIO_IP}:9000",
            aws_access_key_id="$ROOT_USER",
            aws_secret_access_key="$ROOT_PASS",
            region_name="us-east-1",
        )
        
        # Test bucket listing
        print("Testing bucket listing with root credentials...")
        response = s3.list_buckets()
        buckets = [bucket['Name'] for bucket in response['Buckets']]
        print(f"Available buckets: {buckets}")
        
        # Test bucket access
        if 'minio' in buckets:
            print("Testing object listing in 'minio' bucket...")
            response = s3.list_objects_v2(Bucket='minio', MaxKeys=5)
            object_count = response.get('KeyCount', 0)
            print(f"Found {object_count} objects in 'minio' bucket")
            
            if 'Contents' in response:
                print("Sample objects:")
                for obj in response['Contents'][:3]:
                    print(f"  - {obj['Key']} ({obj['Size']} bytes)")
        
        print("Root access test successful!")
        return True
        
    except Exception as e:
        print(f"Root access test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_root_access()
    sys.exit(0 if success else 1)
EOF

    python /tmp/test_root_minio.py
}

# Check if ant-fileserver user exists and create if needed
setup_ant_fileserver_user() {
    log "Setting up ant-fileserver MinIO user"
    
    # Get credentials
    local ACCESS_KEY=$(kubectl get secret -n minio ant-fileserver-prod-creds -o jsonpath='{.data.accessKey}' | base64 -d)
    local SECRET_KEY=$(kubectl get secret -n minio ant-fileserver-prod-creds -o jsonpath='{.data.secretKey}' | base64 -d)
    
    log "Ant-fileserver credentials:"
    log "  Access Key: ${ACCESS_KEY}"
    log "  Secret Key: ${SECRET_KEY:0:8}..."
    
    # Check if user exists
    log "Checking if ant-fileserver user exists in MinIO..."
    if kubectl exec -n minio minio-0 -- mc admin user info local "$ACCESS_KEY" >/dev/null 2>&1; then
        success "Ant-fileserver user already exists"
    else
        warning "Ant-fileserver user does not exist, creating..."
        
        # Create the user
        kubectl exec -n minio minio-0 -- mc admin user add local "$ACCESS_KEY" "$SECRET_KEY"
        success "Created ant-fileserver user"
    fi
    
    # Check/create policy for ant-fileserver
    log "Checking ant-fileserver policy..."
    if kubectl exec -n minio minio-0 -- mc admin policy info local ant-fileserver-policy >/dev/null 2>&1; then
        success "Ant-fileserver policy already exists"
    else
        warning "Creating ant-fileserver policy..."
        
        # Create policy file
        kubectl exec -n minio minio-0 -- sh -c 'cat > /tmp/ant-fileserver-policy.json << '\''EOF'\''
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AntFileserverRW",
            "Effect": "Allow",
            "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
            "Resource": "arn:aws:s3:::*/ant-fileserver/*"
        },
        {
            "Sid": "AntFileserverList",
            "Effect": "Allow",
            "Action": "s3:ListBucket",
            "Resource": "arn:aws:s3:::*",
            "Condition": {
                "StringLike": { "s3:prefix": "ant-fileserver/*" }
            }
        }
    ]
}
EOF'
        
        # Add the policy (using newer command)
        kubectl exec -n minio minio-0 -- mc admin policy create local ant-fileserver-policy /tmp/ant-fileserver-policy.json
        success "Created ant-fileserver policy"
    fi
    
    # Attach policy to user
    log "Attaching policy to ant-fileserver user..."
    kubectl exec -n minio minio-0 -- mc admin policy set local ant-fileserver-policy user="$ACCESS_KEY"
    success "Attached policy to ant-fileserver user"
}

# Test ant-fileserver user access
test_ant_fileserver_access() {
    log "Testing ant-fileserver user access"
    
    local MINIO_IP=$(kubectl get service -n minio minio -o jsonpath='{.spec.clusterIP}')
    local ACCESS_KEY=$(kubectl get secret -n minio ant-fileserver-prod-creds -o jsonpath='{.data.accessKey}' | base64 -d)
    local SECRET_KEY=$(kubectl get secret -n minio ant-fileserver-prod-creds -o jsonpath='{.data.secretKey}' | base64 -d)
    
    cat > /tmp/test_ant_fileserver_access.py << EOF
import boto3
from botocore.exceptions import ClientError
import sys

def test_ant_fileserver_access():
    try:
        s3 = boto3.client(
            "s3",
            endpoint_url="http://${MINIO_IP}:9000",
            aws_access_key_id="$ACCESS_KEY",
            aws_secret_access_key="$SECRET_KEY",
            region_name="us-east-1",
        )
        
        # Test listing objects with ant-fileserver prefix
        print("Testing object listing with ant-fileserver/ prefix...")
        response = s3.list_objects_v2(
            Bucket='minio',
            Prefix='ant-fileserver/',
            MaxKeys=10
        )
        object_count = response.get('KeyCount', 0)
        print(f"Found {object_count} objects with ant-fileserver/ prefix")
        
        # Test uploading a test object
        print("Testing object upload...")
        test_key = "ant-fileserver/test/connectivity-test.txt"
        test_content = "MinIO user access test"
        
        s3.put_object(
            Bucket='minio',
            Key=test_key,
            Body=test_content.encode(),
            ContentType="text/plain"
        )
        print(f"Successfully uploaded test object: {test_key}")
        
        # Test downloading the object
        print("Testing object download...")
        response = s3.get_object(Bucket='minio', Key=test_key)
        retrieved_content = response['Body'].read().decode()
        
        if retrieved_content == test_content:
            print("Successfully retrieved test object with correct content")
        else:
            print("ERROR: Retrieved content doesn't match")
            return False
        
        # Cleanup
        s3.delete_object(Bucket='minio', Key=test_key)
        print("Successfully cleaned up test object")
        
        print("Ant-fileserver user access test successful!")
        return True
        
    except Exception as e:
        print(f"Ant-fileserver access test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_ant_fileserver_access()
    sys.exit(0 if success else 1)
EOF

    python /tmp/test_ant_fileserver_access.py
}

main() {
    log "MinIO Diagnosis and Setup"
    log "========================"
    
    cd "$(dirname "${BASH_SOURCE[0]}")/.."
    
    # Activate virtual environment
    if [ -d ".venv" ]; then
        source .venv/bin/activate
    fi
    
    echo
    log "Phase 1: Testing root connectivity"
    if ! test_root_connectivity; then
        error "Root connectivity failed - check MinIO service"
        exit 1
    fi
    
    echo
    log "Phase 2: Setting up ant-fileserver user"
    setup_ant_fileserver_user
    
    echo  
    log "Phase 3: Testing ant-fileserver user access"
    if test_ant_fileserver_access; then
        success "🎉 MinIO setup complete and working!"
        log "You can now run the production MinIO integration tests"
    else
        error "Ant-fileserver user access failed"
        exit 1
    fi
    
    # Cleanup
    rm -f /tmp/test_*.py
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi