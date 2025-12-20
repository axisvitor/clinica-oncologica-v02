#!/usr/bin/env python3
"""
Test Redis SSL connection with detailed debugging.
"""

import ssl
import socket
import sys
from pathlib import Path

# Redis Cloud connection info
REDIS_HOST = "redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com"
REDIS_PORT = 14149
REDIS_PASSWORD = "6V7Bg9HKlUuxhXtbpnS4ygeiPKB3WQsR"

# Certificate path
CERT_PATH = Path(__file__).parent.parent / "certs" / "redis_ca.pem"

def test_ssl_socket():
    """Test raw SSL socket connection."""
    print(f"\n{'='*60}")
    print("TEST 1: Raw SSL Socket Connection")
    print(f"{'='*60}")
    print(f"Host: {REDIS_HOST}")
    print(f"Port: {REDIS_PORT}")
    print(f"Cert path: {CERT_PATH}")
    print(f"Cert exists: {CERT_PATH.exists()}")

    try:
        # Create SSL context with certificate verification
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.minimum_version = ssl.TLSVersion.TLSv1_2

        if CERT_PATH.exists():
            context.load_verify_locations(cafile=str(CERT_PATH))
            print("✓ Loaded CA certificate")
        else:
            context.load_default_certs()
            print("⚠ Using system default certs")

        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED

        # Create socket and wrap with SSL
        sock = socket.create_connection((REDIS_HOST, REDIS_PORT), timeout=10)
        ssl_sock = context.wrap_socket(sock, server_hostname=REDIS_HOST)

        print(f"✓ SSL connection established")
        print(f"  Cipher: {ssl_sock.cipher()}")
        print(f"  Version: {ssl_sock.version()}")

        # Get peer certificate
        cert = ssl_sock.getpeercert()
        print(f"  Subject: {cert.get('subject', 'N/A')}")
        print(f"  Issuer: {cert.get('issuer', 'N/A')}")

        ssl_sock.close()
        return True

    except ssl.SSLCertVerificationError as e:
        print(f"✗ SSL Certificate Verification Error: {e}")
        return False
    except ssl.SSLError as e:
        print(f"✗ SSL Error: {e}")
        return False
    except Exception as e:
        print(f"✗ Error: {type(e).__name__}: {e}")
        return False


def test_ssl_socket_no_verify():
    """Test SSL socket without certificate verification."""
    print(f"\n{'='*60}")
    print("TEST 2: SSL Socket (No Certificate Verification)")
    print(f"{'='*60}")

    try:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        sock = socket.create_connection((REDIS_HOST, REDIS_PORT), timeout=10)
        ssl_sock = context.wrap_socket(sock, server_hostname=REDIS_HOST)

        print(f"✓ SSL connection established (no verification)")
        print(f"  Cipher: {ssl_sock.cipher()}")
        print(f"  Version: {ssl_sock.version()}")

        ssl_sock.close()
        return True

    except Exception as e:
        print(f"✗ Error: {type(e).__name__}: {e}")
        return False


def test_redis_connection_ssl_cert_reqs():
    """Test redis-py with ssl_cert_reqs parameter."""
    print(f"\n{'='*60}")
    print("TEST 3: redis-py with ssl_cert_reqs='none'")
    print(f"{'='*60}")

    try:
        import redis
        print(f"redis-py version: {redis.__version__}")

        url = f"rediss://default:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}"

        client = redis.from_url(
            url,
            ssl_cert_reqs="none",
            socket_timeout=10,
            socket_connect_timeout=10,
        )

        result = client.ping()
        print(f"✓ PING response: {result}")

        client.close()
        return True

    except Exception as e:
        print(f"✗ Error: {type(e).__name__}: {e}")
        return False


def test_redis_connection_ssl_context():
    """Test redis-py with ssl_context parameter (for 6.x)."""
    print(f"\n{'='*60}")
    print("TEST 4: redis-py with ssl_context (CERT_NONE)")
    print(f"{'='*60}")

    try:
        import redis
        print(f"redis-py version: {redis.__version__}")

        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        url = f"rediss://default:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}"

        client = redis.from_url(
            url,
            ssl_context=context,
            socket_timeout=10,
            socket_connect_timeout=10,
        )

        result = client.ping()
        print(f"✓ PING response: {result}")

        client.close()
        return True

    except Exception as e:
        print(f"✗ Error: {type(e).__name__}: {e}")
        return False


def test_redis_connection_with_ca_cert():
    """Test redis-py with CA certificate."""
    print(f"\n{'='*60}")
    print("TEST 5: redis-py with CA Certificate")
    print(f"{'='*60}")

    try:
        import redis
        print(f"redis-py version: {redis.__version__}")

        url = f"rediss://default:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}"

        if CERT_PATH.exists():
            print(f"Using CA cert: {CERT_PATH}")
            client = redis.from_url(
                url,
                ssl_cert_reqs="required",
                ssl_ca_certs=str(CERT_PATH),
                socket_timeout=10,
                socket_connect_timeout=10,
            )
        else:
            print("CA cert not found, using ssl_cert_reqs='required' only")
            client = redis.from_url(
                url,
                ssl_cert_reqs="required",
                socket_timeout=10,
                socket_connect_timeout=10,
            )

        result = client.ping()
        print(f"✓ PING response: {result}")

        client.close()
        return True

    except Exception as e:
        print(f"✗ Error: {type(e).__name__}: {e}")
        return False


def test_get_server_certificate():
    """Get the actual certificate from the server."""
    print(f"\n{'='*60}")
    print("TEST 6: Fetch Server Certificate")
    print(f"{'='*60}")

    try:
        import ssl
        import socket

        # Connect without verification to get the cert
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        with socket.create_connection((REDIS_HOST, REDIS_PORT), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=REDIS_HOST) as ssl_sock:
                cert_der = ssl_sock.getpeercert(binary_form=True)
                cert = ssl_sock.getpeercert()

                print("Server Certificate Info:")
                print(f"  Subject: {cert.get('subject', 'N/A')}")
                print(f"  Issuer: {cert.get('issuer', 'N/A')}")
                print(f"  Serial: {cert.get('serialNumber', 'N/A')}")
                print(f"  Not Before: {cert.get('notBefore', 'N/A')}")
                print(f"  Not After: {cert.get('notAfter', 'N/A')}")

                # Save the cert for comparison
                import base64
                pem = ssl.DER_cert_to_PEM_cert(cert_der)
                print(f"\n  Server's certificate (PEM):")
                print(pem[:200] + "...")

                return True

    except Exception as e:
        print(f"✗ Error: {type(e).__name__}: {e}")
        return False


def main():
    print("Redis SSL Connection Debugger")
    print("=" * 60)

    results = []

    # Test 1: Raw SSL with CA cert
    results.append(("SSL Socket (with CA)", test_ssl_socket()))

    # Test 2: Raw SSL without verification
    results.append(("SSL Socket (no verify)", test_ssl_socket_no_verify()))

    # Test 3: redis-py with ssl_cert_reqs
    results.append(("redis-py ssl_cert_reqs", test_redis_connection_ssl_cert_reqs()))

    # Test 4: redis-py with ssl_context
    results.append(("redis-py ssl_context", test_redis_connection_ssl_context()))

    # Test 5: redis-py with CA cert
    results.append(("redis-py with CA cert", test_redis_connection_with_ca_cert()))

    # Test 6: Get server certificate
    results.append(("Get server cert", test_get_server_certificate()))

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for name, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"  {status}: {name}")

    print("\n" + "="*60)
    if all(r[1] for r in results):
        print("All tests passed!")
        return 0
    else:
        print("Some tests failed. Check output above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
