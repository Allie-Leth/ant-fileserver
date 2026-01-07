#!/usr/bin/env python3
"""Generate a secure JWT secret key."""

import base64
import secrets


def generate_jwt_secret():
    """Generate a cryptographically secure JWT secret key."""
    # JWT secrets should be at least 256 bits (32 bytes) for HS256
    # We'll use 512 bits (64 bytes) for extra security
    secret_bytes = secrets.token_bytes(64)

    # Convert to base64 for easy storage
    secret_b64 = base64.b64encode(secret_bytes).decode("utf-8")

    return secret_b64


if __name__ == "__main__":
    jwt_secret = generate_jwt_secret()
    print("Generated JWT Secret Key (base64 encoded):")
    print(jwt_secret)
    print(f"\nLength: {len(jwt_secret)} characters")
    print("Entropy: 512 bits")
