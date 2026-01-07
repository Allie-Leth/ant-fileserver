#!/usr/bin/env python3
"""Generate secure API keys for ant-fileserver.

This script generates cryptographically secure API keys with appropriate
roles for different access levels, replacing the hardcoded "dev-key".
"""

import json
import secrets
import sys
from datetime import datetime, timedelta


def generate_api_key(prefix: str = "fwa") -> str:
    """Generate a secure API key with prefix.

    Args:
        prefix: Key prefix for identification (default: "fwa" for firmware api)

    Returns:
        Secure API key string
    """
    # 32 bytes = 256 bits of entropy
    key = secrets.token_urlsafe(32)
    return f"{prefix}_{key}"


def generate_key_set():
    """Generate a complete set of API keys for different roles.

    Returns:
        Dictionary of API keys with roles and metadata
    """
    # Generate keys for different access levels
    keys = {
        "readonly": generate_api_key(),
        "uploader": generate_api_key(),
        "admin": generate_api_key(),
        "ci_deploy": generate_api_key("fwa_ci"),  # Special key for CI/CD
    }

    # Create role mapping
    api_key_roles = {
        keys["readonly"]: ["readonly"],
        keys["uploader"]: ["uploader"],
        keys["admin"]: ["admin", "uploader"],
        keys["ci_deploy"]: ["uploader"],  # CI only needs upload, not admin
    }

    # Create metadata for tracking
    key_metadata = {}
    for purpose, key in keys.items():
        key_metadata[key] = {
            "created": datetime.utcnow().isoformat(),
            "expires": (datetime.utcnow() + timedelta(days=90)).isoformat(),
            "purpose": purpose,
            "description": get_key_description(purpose),
        }

    return {"keys": keys, "api_key_roles": api_key_roles, "key_metadata": key_metadata}


def get_key_description(purpose: str) -> str:
    """Get human-readable description for key purpose."""
    descriptions = {
        "readonly": "Read-only access for monitoring and status checks",
        "uploader": "Upload access for firmware deployment tools",
        "admin": "Full administrative access for management operations",
        "ci_deploy": "CI/CD pipeline deployment access",
    }
    return descriptions.get(purpose, "Unknown purpose")


def generate_kubernetes_secret(key_data: dict) -> str:
    """Generate Kubernetes Secret YAML for the API keys.

    Args:
        key_data: Dictionary containing keys, roles, and metadata

    Returns:
        YAML string for Kubernetes Secret
    """
    yaml_template = f"""apiVersion: v1
kind: Secret
metadata:
  name: ant-fileserver-api-keys-secure
  namespace: ant-fileserver
  annotations:
    generated-by: generate_secure_keys.py
    generated-at: "{datetime.utcnow().isoformat()}"
type: Opaque
stringData:
  API_KEY_ROLES: |
{json.dumps(key_data["api_key_roles"], indent=4, sort_keys=True).replace("\n", "\n    ")}
  KEY_METADATA: |
{json.dumps(key_data["key_metadata"], indent=4, sort_keys=True, default=str).replace("\n", "\n    ")}
"""
    return yaml_template


def generate_env_file(keys: dict) -> str:
    """Generate .env file content for local development.

    Args:
        keys: Dictionary of key purposes to key values

    Returns:
        Environment file content
    """
    env_content = f"""# Generated API Keys for Local Development
# Generated at: {datetime.utcnow().isoformat()}
# WARNING: Do not commit this file to version control!

# Read-only access (monitoring, status checks)
API_KEY_READONLY={keys["readonly"]}

# Uploader access (firmware uploads)
API_KEY_UPLOADER={keys["uploader"]}

# Admin access (full management)
API_KEY_ADMIN={keys["admin"]}

# CI/CD deployment access
API_KEY_CI_DEPLOY={keys["ci_deploy"]}
"""
    return env_content


def main():
    """Generate secure API keys and output in various formats."""
    print("Generating secure API keys for ant-fileserver...")

    # Generate the key set
    key_data = generate_key_set()

    # Output formats
    print("\n1. Individual Keys:")
    print("-" * 60)
    for purpose, key in key_data["keys"].items():
        print(f"{purpose:12} : {key}")

    print("\n2. Kubernetes Secret (to be sealed with kubeseal):")
    print("-" * 60)
    secret_yaml = generate_kubernetes_secret(key_data)

    # Save to file for sealing
    secret_file = "/home/leth/ant-firmware/ant-fileserver/k8s/manifests/overlays/dev/api-keys-secret.yaml"
    with open(secret_file, "w") as f:
        f.write(secret_yaml)
    print(f"Saved to: {secret_file}")

    print("\n3. Environment File (for local development):")
    print("-" * 60)
    env_content = generate_env_file(key_data["keys"])

    # Save env file
    env_file = "/home/leth/ant-firmware/ant-fileserver/.env.secure"
    with open(env_file, "w") as f:
        f.write(env_content)
    print(f"Saved to: {env_file}")

    print("\n4. Next Steps:")
    print("-" * 60)
    print(
        "1. Seal the secret: kubeseal < api-keys-secret.yaml > api-keys-sealedsecret.yaml"
    )
    print("2. Update kustomization.yaml to use the new sealed secret")
    print("3. Remove the plain secret file after sealing")
    print("4. Update deployment to reference the new secret name")
    print("5. Test with new keys using the secure testing script")

    print("\n5. Security Notes:")
    print("-" * 60)
    print("- Keys have 256 bits of entropy (cryptographically secure)")
    print("- Each key has a specific role (principle of least privilege)")
    print("- Keys include metadata for tracking and rotation")
    print("- CI/CD key has limited permissions (no admin access)")
    print("- Keys expire after 90 days (implement rotation)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
