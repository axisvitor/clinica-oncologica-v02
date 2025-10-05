# Redis SSL/TLS Configuration Architecture Plan

**Document Version:** 1.0.0
**Date:** 2025-10-05
**Architect:** System Architecture Designer
**Status:** Design Phase

---

## Executive Summary

This document provides a comprehensive architectural solution for Redis SSL/TLS configuration issues in the Hormonia Backend System. The solution addresses missing configuration fields, implements secure certificate validation with fallback mechanisms, fixes brittle URL parsing, and establishes diagnostic logging without exposing sensitive credentials.

### Key Issues Identified

1. **Configuration Gaps**: Settings class missing `REDIS_SSL_MIN_VERSION`, `REDIS_SSL_CA_CERTS`, `BASE_DIR` fields
2. **No Certifi Fallback**: Missing automatic fallback to system CA certificates when custom CA not specified
3. **Brittle URL Rewriting**: monitoring/config.py uses fragile string replacement (`replace('/0', '/1')`)
4. **Diagnostic Logging**: Need secure logging that shows connection details without exposing passwords

### Solution Impact

- ✅ **Security**: Proper SSL/TLS certificate validation with flexible configuration
- ✅ **Reliability**: Robust URL parsing using urllib.parse instead of string replacement
- ✅ **Observability**: Diagnostic logging for troubleshooting without credential leakage
- ✅ **Maintainability**: Clean architecture with clear separation of concerns

---

## 1. Architecture Decision Records (ADRs)

### ADR-001: Certifi as Default CA Certificate Bundle

**Context**: Redis Cloud requires proper CA certificate validation for SSL/TLS connections. Hardcoding CA paths is not portable across environments.

**Decision**: Implement automatic fallback to `certifi` package for CA certificates when `REDIS_SSL_CERT_REQS='required'` and no custom `REDIS_SSL_CA_CERTS` specified.

**Consequences**:
- ✅ Works out-of-the-box across all platforms (Windows, Linux, macOS)
- ✅ Automatically updated CA certificates via certifi package
- ✅ Explicit override available via `REDIS_SSL_CA_CERTS` for corporate environments
- ⚠️ Requires certifi dependency (already in requirements.txt)

**Alternatives Considered**:
- System CA store: Platform-specific, not portable
- Bundled CA file: Requires manual updates, security risk

---

### ADR-002: urllib.parse for URL Manipulation

**Context**: Current monitoring/config.py uses `replace('/0', '/1')` which breaks on URLs without database numbers or non-standard formats.

**Decision**: Use `urllib.parse` for robust URL parsing and reconstruction.

**Consequences**:
- ✅ Handles all URL formats correctly (with/without DB, auth, query params)
- ✅ Validates URL structure before modification
- ✅ Preserves scheme, host, port, credentials
- ✅ Standard library solution, no new dependencies

**Implementation**:
```python
from urllib.parse import urlparse, urlunparse

parsed = urlparse(redis_url)
# Extract and modify path safely
path_parts = parsed.path.split('/') if parsed.path else []
# Replace last segment if digit, otherwise append
if path_parts and path_parts[-1].isdigit():
    path_parts[-1] = str(new_db_number)
else:
    path_parts.append(str(new_db_number))
new_path = '/'.join(path_parts)
# Reconstruct URL
new_parsed = parsed._replace(path=new_path)
redis_url = urlunparse(new_parsed)
```

---

### ADR-003: Structured Diagnostic Logging

**Context**: Need to debug Redis connections without exposing passwords or sensitive credentials in logs.

**Decision**: Implement secure logging that:
1. Extracts and logs: scheme, host, port, DB number, TLS version
2. **Never logs**: passwords, auth tokens, full connection strings
3. Uses structured logging (logger.info with key=value pairs)

**Consequences**:
- ✅ Security: No credential leakage in logs
- ✅ Observability: Enough information to diagnose connection issues
- ✅ Compliance: Meets security audit requirements
- ✅ Performance: Minimal overhead

**Logging Format**:
```python
logger.info(
    f"Redis connection: scheme={scheme}, host={host}, port={port}, "
    f"db={db}, ssl={ssl_enabled}, tls_version={tls_version}, "
    f"cert_validation={cert_reqs}"
)
# NEVER: logger.info(f"Redis URL: {redis_url}")  # ❌ Exposes password
```

---

### ADR-004: BASE_DIR as Computed Default

**Context**: Need to resolve relative paths for CA certificates (e.g., `certs/ca-bundle.crt`) to absolute paths.

**Decision**: Add `BASE_DIR` to Settings class with computed default using `os.path.dirname()`.

**Consequences**:
- ✅ Relative paths work correctly in all environments
- ✅ No breaking changes (default computed automatically)
- ✅ Explicit override available via environment variable
- ✅ Consistent with Django/Flask patterns

**Implementation**:
```python
BASE_DIR: str = Field(
    default_factory=lambda: os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    description="Base directory of the application (backend-hormonia/app parent)"
)
```

---

## 2. Detailed Component Changes

### 2.1 Settings Class (app/config.py)

**File**: `backend-hormonia/app/config.py`
**Class**: `Settings(BaseSettings)`
**Lines**: 12-497

#### Changes Required

**A. Add Missing SSL Configuration Fields**

**Location**: After line 184 (after existing `REDIS_SSL_CA_CERTS`)

```python
# Lines 177-190 (UPDATE existing fields + add new ones)
# SSL/TLS Configuration
REDIS_SSL: bool = Field(default=False, description="Enable SSL/TLS for Redis connection (use rediss:// URL or set to True)")
REDIS_SSL_CERT_REQS: str = Field(
    default="required",
    description="Redis SSL certificate requirements: none, optional, required (SECURITY: Use 'required' for production)"
)

# NEW FIELD 1: Minimum TLS Version
REDIS_SSL_MIN_VERSION: Optional[str] = Field(
    default=None,
    description="Minimum TLS version: 'TLSV1_2' or 'TLSV1_3'. Leave empty for auto-negotiation."
)

# NEW FIELD 2: CA Certificate Path (with certifi fallback)
REDIS_SSL_CA_CERTS: Optional[str] = Field(
    default=None,
    description="Path to CA certificate bundle (absolute or relative to BASE_DIR). If not specified with CERT_REQUIRED, will use certifi."
)

# NEW FIELD 3: Base Directory
BASE_DIR: str = Field(
    default_factory=lambda: os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    description="Base directory of the application (backend-hormonia/app parent)"
)
```

**Rationale**:
- `REDIS_SSL_MIN_VERSION`: Allows explicit TLS version control for Redis Cloud compatibility
- `REDIS_SSL_CA_CERTS`: Explicitly documents certifi fallback behavior
- `BASE_DIR`: Enables relative path resolution for certificates

**B. Add SSL Configuration Validator**

**Location**: After line 493 (inside `_validate_production_config` method)

```python
# Lines 464-494 (ADD new validation inside _validate_production_config)
def _validate_production_config(self):
    """Validate production environment has secure configurations."""
    if self.ENVIRONMENT.lower() == 'production':
        errors = []

        # ... existing validations ...

        # NEW: Validate SSL certificate configuration
        if self.REDIS_SSL and self.REDIS_SSL_CERT_REQS == 'required':
            # Check if custom CA specified and exists
            if self.REDIS_SSL_CA_CERTS:
                ca_path = self.REDIS_SSL_CA_CERTS
                if not os.path.isabs(ca_path):
                    ca_path = os.path.join(self.BASE_DIR, ca_path)

                if not os.path.exists(ca_path):
                    errors.append(f"REDIS_SSL_CA_CERTS specified but file not found: {ca_path}")
            else:
                # Verify certifi is available for fallback
                try:
                    import certifi
                    logger.info(f"✅ Redis SSL: Will use certifi CA bundle ({certifi.where()})")
                except ImportError:
                    errors.append(
                        "REDIS_SSL_CERT_REQS='required' but no REDIS_SSL_CA_CERTS specified "
                        "and certifi not installed. Install certifi or provide CA certificate path."
                    )

        # NEW: Validate TLS version format
        if self.REDIS_SSL_MIN_VERSION:
            valid_versions = ['TLSV1_2', 'TLSV1_3']
            if self.REDIS_SSL_MIN_VERSION.upper() not in valid_versions:
                errors.append(
                    f"Invalid REDIS_SSL_MIN_VERSION: {self.REDIS_SSL_MIN_VERSION}. "
                    f"Must be one of: {', '.join(valid_versions)}"
                )

        if errors:
            raise ValueError(
                f"Production environment security validation failed:\n" +
                "\n".join(f"  - {error}" for error in errors)
            )
```

**Impact**: Catches configuration errors at startup, not at first Redis connection.

---

### 2.2 Redis Manager (app/core/redis_manager.py)

**File**: `backend-hormonia/app/core/redis_manager.py`
**Class**: `RedisManager`
**Lines**: 24-628

#### Changes Required

**A. Implement Certifi Fallback in Async Client**

**Location**: Lines 90-200 (`_create_async_client` method)

**Current Code** (Lines 129-158):
```python
else:  # 'required'
    connection_kwargs['ssl_cert_reqs'] = ssl.CERT_REQUIRED

    # Use CA certificate for validation if provided
    ssl_ca_certs = getattr(settings, 'REDIS_SSL_CA_CERTS', None)
    if ssl_ca_certs:
        # ... existing code ...
    else:
        # MISSING FALLBACK - THIS IS THE BUG
        logger.info("Redis async SSL: Certificate verification REQUIRED")
```

**Fixed Code**:
```python
else:  # 'required'
    connection_kwargs['ssl_cert_reqs'] = ssl.CERT_REQUIRED

    # Use CA certificate for validation if provided
    ssl_ca_certs = getattr(settings, 'REDIS_SSL_CA_CERTS', None)
    if ssl_ca_certs:
        import os
        # Support both absolute and relative paths
        if os.path.isabs(ssl_ca_certs):
            ca_path = ssl_ca_certs
        else:
            ca_path = os.path.join(settings.BASE_DIR, ssl_ca_certs)

        if os.path.exists(ca_path):
            connection_kwargs['ssl_ca_certs'] = ca_path
            logger.info(f"Redis async SSL: Using CA certificate from {ssl_ca_certs}")
        else:
            logger.error(f"Redis CA certificate not found at {ca_path}. Falling back to certifi.")
            ssl_ca_certs = None  # Trigger fallback below

    # NEW: Fallback to certifi if no custom CA specified
    if not ssl_ca_certs:
        try:
            import certifi
            connection_kwargs['ssl_ca_certs'] = certifi.where()
            logger.info(f"Redis async SSL: Using certifi CA bundle: {certifi.where()}")
        except ImportError:
            logger.warning("Redis async SSL: certifi not available, using system CA store")

    logger.info("Redis async SSL: Certificate verification REQUIRED")
```

**B. Add Secure Diagnostic Logging**

**Location**: Lines 175-183 (replace existing URL validation logging)

**Current Code**:
```python
# Validate URL scheme matches SSL config
if not redis_url.startswith('rediss://'):
    logger.error(f"REDIS_SSL=true but URL uses {redis_url.split('://')[0]}:// scheme. Fix .env to use rediss://")
```

**Fixed Code**:
```python
# NEW: Secure diagnostic logging (parse URL without exposing password)
from urllib.parse import urlparse
parsed_url = urlparse(redis_url)
scheme = parsed_url.scheme
hostname = parsed_url.hostname or 'unknown'
port = parsed_url.port or (6380 if scheme == 'rediss' else 6379)
db_num = self.db_number if self.db_number is not None else 'default'

# Get TLS version for logging
tls_version = ssl_min_version if ssl_min_version else 'auto-negotiated'
cert_reqs = ssl_cert_reqs if ssl_cert_reqs else 'none'

# Log connection details (NO PASSWORD)
logger.info(
    f"Redis async connection: scheme={scheme}, host={hostname}, port={port}, "
    f"db={db_num}, ssl={settings.REDIS_SSL}, tls_version={tls_version}, "
    f"cert_validation={cert_reqs}"
)

# Validate URL scheme matches SSL config
if not redis_url.startswith('rediss://'):
    logger.error(
        f"REDIS_SSL=true but URL uses {scheme}:// scheme. "
        f"Fix .env to use rediss:// for host {hostname}:{port}"
    )
```

**C. Apply Same Changes to Sync Client**

**Location**: Lines 202-253 (`_create_sync_client` method)

Apply identical certifi fallback and diagnostic logging changes as async client.

**Note**: Sync client currently does NOT configure SSL parameters (lines 237-242). This needs enhancement:

```python
# Lines 225-242 (REPLACE)
# Configure SSL if enabled
redis_url = self.redis_url
if settings.REDIS_SSL:
    import ssl

    # Base SSL configuration
    ssl_cert_reqs = getattr(settings, 'REDIS_SSL_CERT_REQS', 'required').lower()

    if ssl_cert_reqs == 'none':
        connection_kwargs['ssl_cert_reqs'] = ssl.CERT_NONE
        connection_kwargs['ssl_check_hostname'] = False
    elif ssl_cert_reqs == 'optional':
        connection_kwargs['ssl_cert_reqs'] = ssl.CERT_OPTIONAL
    else:  # 'required'
        connection_kwargs['ssl_cert_reqs'] = ssl.CERT_REQUIRED

        # Apply same certifi fallback as async client
        ssl_ca_certs = getattr(settings, 'REDIS_SSL_CA_CERTS', None)
        if ssl_ca_certs:
            # ... same path resolution logic ...
        else:
            try:
                import certifi
                connection_kwargs['ssl_ca_certs'] = certifi.where()
                logger.info(f"Redis sync SSL: Using certifi CA bundle")
            except ImportError:
                logger.warning("Redis sync SSL: certifi not available")

    # Apply TLS version if specified
    ssl_min_version = getattr(settings, 'REDIS_SSL_MIN_VERSION', None)
    if ssl_min_version:
        # ... same TLS version logic as async ...

    # Secure diagnostic logging
    # ... same logging as async client ...
```

---

### 2.3 Monitoring Config (app/monitoring/config.py)

**File**: `backend-hormonia/app/monitoring/config.py`
**Class**: `MonitoringConfig`
**Lines**: 169-308

#### Changes Required

**A. Fix URL Parsing in get_redis_url() Method**

**Location**: Lines 238-264 (replace entire method)

**Current Code** (Lines 238-264):
```python
def get_redis_url(self) -> str:
    """Get Redis connection URL with proper environment variable handling."""
    from urllib.parse import urlparse, urlunparse
    from app.config import settings

    # First priority: Use REDIS_URL environment variable if available (from settings)
    redis_url = settings.REDIS_URL
    if redis_url and not redis_url.startswith('redis://localhost'):
        # Parse URL to safely replace database number
        parsed = urlparse(redis_url)

        # Extract path and replace/add database number
        path = parsed.path or ''
        # Remove existing /N suffix if present
        if '/' in path and path.split('/')[-1].isdigit():
            path = '/'.join(path.split('/')[:-1])

        # Add monitoring DB (1)
        new_path = f"{path}/{self.redis.db}" if path else f"/{self.redis.db}"

        # Reconstruct URL with new path
        new_parsed = parsed._replace(path=new_path)
        return urlunparse(new_parsed)

    # Fallback: Construct URL from individual components for local development
    auth = f":{self.redis.password}@" if self.redis.password else ""
    return f"redis://{auth}{self.redis.host}:{self.redis.port}/{self.redis.db}"
```

**Issues**:
- Line 252: `path.split('/')` creates empty strings: `''.split('/') → ['']`
- Line 253: Logic fails when path is `/` or empty
- Line 257: Double slash when path is empty: `f"/{1}" → "/1"` (correct) but `f"/{1}"` when path=`""` → `"/1"` not `/1`

**Fixed Code**:
```python
def get_redis_url(self) -> str:
    """
    Get Redis connection URL with proper database number substitution.

    Uses robust URL parsing with urllib.parse to safely modify database number
    while preserving scheme, credentials, host, port, and query parameters.

    Returns:
        str: Redis connection URL with monitoring database number
    """
    from urllib.parse import urlparse, urlunparse
    from app.config import settings
    import logging

    logger = logging.getLogger(__name__)

    # First priority: Use REDIS_URL from settings (Railway/production)
    redis_url = settings.REDIS_URL

    if redis_url and not redis_url.startswith('redis://localhost'):
        try:
            # Parse URL safely
            parsed = urlparse(redis_url)

            # Extract path components (e.g., "/0" → ["", "0"])
            path_parts = parsed.path.split('/') if parsed.path else []

            # Filter out empty strings
            path_parts = [p for p in path_parts if p]

            # Replace last segment if it's a digit (database number)
            if path_parts and path_parts[-1].isdigit():
                path_parts[-1] = str(self.redis.db)
            else:
                # No database number in URL, append it
                path_parts.append(str(self.redis.db))

            # Reconstruct path with leading slash
            new_path = '/' + '/'.join(path_parts)

            # Reconstruct URL with modified path
            new_parsed = parsed._replace(path=new_path)
            result_url = urlunparse(new_parsed)

            # Secure logging (NO PASSWORD)
            logger.info(
                f"Monitoring Redis: scheme={parsed.scheme}, host={parsed.hostname}, "
                f"port={parsed.port or 6379}, db={self.redis.db}"
            )

            return result_url

        except Exception as e:
            logger.error(f"Failed to parse REDIS_URL: {e}. Using fallback construction.")
            # Fall through to fallback

    # Fallback: Construct URL from individual components (local development)
    scheme = "rediss" if getattr(settings, 'REDIS_SSL', False) else "redis"
    auth = f":{self.redis.password}@" if self.redis.password else ""
    result_url = f"{scheme}://{auth}{self.redis.host}:{self.redis.port}/{self.redis.db}"

    logger.info(
        f"Monitoring Redis (fallback): scheme={scheme}, host={self.redis.host}, "
        f"port={self.redis.port}, db={self.redis.db}"
    )

    return result_url
```

**Test Cases** (to verify fix):

| Input URL | Expected Output | Notes |
|-----------|----------------|-------|
| `rediss://user:pass@host:6380/0` | `rediss://user:pass@host:6380/1` | Standard format |
| `rediss://user:pass@host:6380` | `rediss://user:pass@host:6380/1` | Missing DB |
| `rediss://host:6380/2` | `rediss://host:6380/1` | No auth |
| `redis://localhost:6379` | `redis://localhost:6379/1` | Localhost (fallback) |
| `rediss://host/` | `rediss://host/1` | Trailing slash |
| `rediss://host` | `rediss://host/1` | No path |

---

## 3. Testing Strategy

### 3.1 Unit Tests

**File**: `backend-hormonia/tests/test_redis_ssl_config.py` (NEW)

```python
import pytest
import ssl
from unittest.mock import patch, MagicMock
from app.config import Settings
from app.core.redis_manager import RedisManager


class TestRedisSSLConfiguration:
    """Test Redis SSL/TLS configuration."""

    def test_settings_has_ssl_fields(self):
        """Verify Settings class has all required SSL fields."""
        settings = Settings(
            SECRET_KEY="test-secret",
            DATABASE_URL="postgresql://test",
            SUPABASE_URL="https://test.supabase.co",
            SUPABASE_ANON_KEY="test-anon",
            SUPABASE_SERVICE_ROLE_KEY="test-service"
        )

        assert hasattr(settings, 'REDIS_SSL_MIN_VERSION')
        assert hasattr(settings, 'REDIS_SSL_CA_CERTS')
        assert hasattr(settings, 'BASE_DIR')

    def test_certifi_fallback_when_ca_not_specified(self, monkeypatch):
        """Test certifi fallback when REDIS_SSL_CA_CERTS not provided."""
        # Mock certifi
        mock_certifi = MagicMock()
        mock_certifi.where.return_value = "/path/to/certifi/cacert.pem"

        with patch.dict('sys.modules', {'certifi': mock_certifi}):
            settings = Settings(
                SECRET_KEY="test",
                REDIS_SSL=True,
                REDIS_SSL_CERT_REQS="required",
                # REDIS_SSL_CA_CERTS NOT SET
            )

            manager = RedisManager()
            # Trigger async client creation
            # ... async test logic ...

            # Verify certifi.where() was called
            mock_certifi.where.assert_called_once()

    def test_tls_version_validation(self):
        """Test TLS version field accepts valid values."""
        # Valid values
        settings = Settings(
            SECRET_KEY="test",
            REDIS_SSL_MIN_VERSION="TLSV1_2"
        )
        assert settings.REDIS_SSL_MIN_VERSION == "TLSV1_2"

        settings = Settings(
            SECRET_KEY="test",
            REDIS_SSL_MIN_VERSION="TLSV1_3"
        )
        assert settings.REDIS_SSL_MIN_VERSION == "TLSV1_3"

    def test_base_dir_computed_default(self):
        """Test BASE_DIR is computed correctly."""
        settings = Settings(SECRET_KEY="test")

        assert settings.BASE_DIR is not None
        assert isinstance(settings.BASE_DIR, str)
        # Should point to backend-hormonia directory
        assert settings.BASE_DIR.endswith('backend-hormonia')


class TestMonitoringRedisURL:
    """Test monitoring config URL parsing."""

    @pytest.mark.parametrize("input_url,expected_db,expected_host", [
        ("rediss://user:pass@host:6380/0", "1", "host"),
        ("rediss://user:pass@host:6380", "1", "host"),
        ("rediss://host:6380/2", "1", "host"),
        ("rediss://host/", "1", "host"),
        ("rediss://host", "1", "host"),
    ])
    def test_url_parsing_robustness(self, input_url, expected_db, expected_host, monkeypatch):
        """Test URL parsing handles various formats."""
        from app.monitoring.config import MonitoringConfig

        # Mock settings.REDIS_URL
        monkeypatch.setenv("REDIS_URL", input_url)

        config = MonitoringConfig.from_env()
        result_url = config.get_redis_url()

        # Verify database number was changed to 1
        assert f"/{expected_db}" in result_url
        # Verify host preserved
        assert expected_host in result_url
        # Verify no password in logs (check via caplog)

    def test_url_parsing_no_password_in_logs(self, caplog):
        """Ensure passwords not logged during URL parsing."""
        from app.monitoring.config import MonitoringConfig

        config = MonitoringConfig()
        config.redis.password = "super-secret-password"

        with caplog.at_level("INFO"):
            url = config.get_redis_url()

        # Check logs don't contain password
        for record in caplog.records:
            assert "super-secret-password" not in record.message
```

---

### 3.2 Integration Tests

**File**: `backend-hormonia/tests/integration/test_redis_ssl_connection.py` (NEW)

```python
import pytest
import redis.asyncio as redis_async
from app.core.redis_manager import get_redis_manager


@pytest.mark.integration
@pytest.mark.asyncio
async def test_redis_ssl_connection_with_certifi():
    """Test real Redis connection using certifi CA bundle."""
    # Requires REDIS_URL in .env.test
    manager = get_redis_manager()

    client = await manager.get_async_client()

    # Test connection
    assert await client.ping() == True

    # Test basic operations
    await client.set("test:ssl:key", "value")
    assert await client.get("test:ssl:key") == "value"

    # Cleanup
    await client.delete("test:ssl:key")
    await manager.close_async()


@pytest.mark.integration
def test_monitoring_redis_connection():
    """Test monitoring Redis connection with correct DB."""
    from app.monitoring.config import get_monitoring_config
    import redis

    config = get_monitoring_config()
    redis_url = config.get_redis_url()

    # Verify URL has correct database
    assert "/1" in redis_url or "db=1" in redis_url

    # Test connection
    client = redis.from_url(redis_url)
    assert client.ping() == True

    # Verify we're on DB 1
    client.set("test:monitoring:key", "value")
    # Switch to DB 0 and verify key doesn't exist
    client.execute_command("SELECT", 0)
    assert client.get("test:monitoring:key") is None

    # Cleanup
    client.execute_command("SELECT", 1)
    client.delete("test:monitoring:key")
```

---

### 3.3 Manual Testing Checklist

- [ ] **Config Validation**: Start app with missing certifi, verify error message
- [ ] **Certifi Fallback**: Start app without `REDIS_SSL_CA_CERTS`, verify certifi used
- [ ] **Custom CA**: Set `REDIS_SSL_CA_CERTS=certs/ca-bundle.crt`, verify file loaded
- [ ] **TLS Version**: Set `REDIS_SSL_MIN_VERSION=TLSV1_2`, check logs for confirmation
- [ ] **URL Parsing**: Check logs for monitoring Redis connection, verify no password shown
- [ ] **Database Isolation**: Verify monitoring uses DB 1, cache uses DB 1, broker uses DB 0

---

## 4. Configuration Reference

### 4.1 Environment Variables

Add to `.env.example` and `.env`:

```bash
# Redis SSL/TLS Configuration (Enhanced)
REDIS_SSL=true
REDIS_SSL_CERT_REQS=required  # Options: none, optional, required
REDIS_SSL_MIN_VERSION=        # Options: TLSV1_2, TLSV1_3, or empty for auto
REDIS_SSL_CA_CERTS=          # Path to CA cert bundle (or leave empty for certifi)

# Base directory (auto-computed, override only if needed)
# BASE_DIR=/app/backend-hormonia
```

### 4.2 Railway Production Config

```bash
# Railway environment (rediss:// URL with SSL)
REDIS_URL=rediss://default:password@redis-12345.railway.app:6380
REDIS_SSL=true
REDIS_SSL_CERT_REQS=required
# Leave REDIS_SSL_CA_CERTS empty to use certifi (recommended for Railway)
REDIS_SSL_MIN_VERSION=TLSV1_2  # If Redis Cloud requires TLS 1.2
```

### 4.3 Local Development Config

```bash
# Local Redis (no SSL)
REDIS_URL=redis://localhost:6379/0
REDIS_SSL=false
# No SSL config needed for local
```

---

## 5. Deployment Checklist

### 5.1 Pre-Deployment

- [ ] Update `requirements.txt` to ensure `certifi>=2023.7.22` present
- [ ] Run `pip install -r requirements.txt` to install/upgrade certifi
- [ ] Update `.env.example` with new SSL configuration options
- [ ] Update documentation (README.md, deployment guides)

### 5.2 Code Changes

- [ ] Update `app/config.py` Settings class (3 new fields + validation)
- [ ] Update `app/core/redis_manager.py` (certifi fallback + logging)
- [ ] Update `app/monitoring/config.py` (URL parsing fix)
- [ ] Create unit tests (`tests/test_redis_ssl_config.py`)
- [ ] Create integration tests (`tests/integration/test_redis_ssl_connection.py`)

### 5.3 Testing

- [ ] Run unit tests: `pytest tests/test_redis_ssl_config.py -v`
- [ ] Run integration tests: `pytest tests/integration/ -m integration -v`
- [ ] Test locally with Redis SSL enabled
- [ ] Test staging deployment on Railway

### 5.4 Production Rollout

- [ ] Deploy to staging environment
- [ ] Verify Redis connections in staging logs (check for certifi usage)
- [ ] Run smoke tests (health check endpoints)
- [ ] Deploy to production
- [ ] Monitor logs for first 15 minutes
- [ ] Verify no SSL/TLS errors in Sentry/logging

---

## 6. Rollback Plan

### If Issues Occur Post-Deployment

**Scenario 1: Certificate Validation Fails**

```bash
# Quick fix: Disable certificate validation (temporary, NOT for production long-term)
REDIS_SSL_CERT_REQS=none
```

**Scenario 2: TLS Version Mismatch**

```bash
# Try different TLS version
REDIS_SSL_MIN_VERSION=TLSV1_2  # or TLSV1_3, or empty
```

**Scenario 3: Certifi Not Found**

```bash
# Specify system CA bundle explicitly
REDIS_SSL_CA_CERTS=/etc/ssl/certs/ca-bundle.crt  # Linux
# or
REDIS_SSL_CA_CERTS=/etc/ssl/cert.pem  # macOS
```

**Full Rollback**:
- Revert to previous commit
- Restart services
- Set `REDIS_SSL=false` temporarily if needed

---

## 7. Future Enhancements

### Phase 2 (Post-MVP)

1. **Certificate Rotation**: Auto-reload CA certificates without restart
2. **Health Checks**: Periodic SSL/TLS handshake validation
3. **Metrics**: Track SSL/TLS errors, certificate expiry warnings
4. **Mutual TLS**: Client certificate authentication for Redis Enterprise

### Phase 3 (Advanced)

1. **Dynamic Configuration**: Hot-reload SSL settings without restart
2. **Multi-Region**: Different SSL configs per Redis instance (primary/replica)
3. **Observability**: OpenTelemetry spans for SSL handshake timing

---

## 8. References

### Documentation

- [redis-py SSL/TLS Guide](https://redis-py.readthedocs.io/en/stable/examples/ssl_connection_examples.html)
- [Python ssl Module](https://docs.python.org/3/library/ssl.html)
- [Certifi Package](https://github.com/certifi/python-certifi)
- [Railway Redis SSL](https://docs.railway.app/databases/redis#connecting-with-ssl)

### Related Issues

- Python 3.13 SSL changes: [PEP 644](https://peps.python.org/pep-0644/)
- redis-py 6.0.0 SSL improvements: [Changelog](https://github.com/redis/redis-py/releases/tag/v6.0.0)

---

## 9. Approval Sign-Off

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Architect | Claude (System Architecture Designer) | ✅ | 2025-10-05 |
| Security Review | - | ⏳ Pending | - |
| DevOps Review | - | ⏳ Pending | - |
| Product Owner | - | ⏳ Pending | - |

---

**Document Status**: ✅ **READY FOR IMPLEMENTATION**

**Next Steps**:
1. Review this architecture plan
2. Create implementation tasks/tickets
3. Assign to development team
4. Begin implementation following section 5.2 (Code Changes)
