# Security Headers Implementation

## Overview

This document describes the security headers middleware implementation for the Hormonia Oncology Clinic backend API. The middleware adds essential HTTP security headers to all responses to protect against common web vulnerabilities.

## Security Headers Implemented

### 1. X-Frame-Options

**Value:** `DENY`

**Purpose:** Prevents clickjacking attacks by prohibiting the application from being embedded in frames or iframes.

**Why DENY:** Medical applications should never be embedded in other sites to prevent UI redressing attacks and maintain full control over the user interface context.

### 2. X-Content-Type-Options

**Value:** `nosniff`

**Purpose:** Prevents MIME-type sniffing by instructing browsers to respect the declared Content-Type.

**Impact:** Reduces risk of MIME confusion attacks where malicious content could be executed by browsers interpreting file types incorrectly.

### 3. Strict-Transport-Security (HSTS)

**Value:** `max-age=31536000; includeSubDomains`

**Purpose:** Forces all connections to use HTTPS for the specified duration (1 year).

**Configuration:**
- Only set when request is over HTTPS
- Applies to all subdomains
- Can be configured with preload option (disabled by default, enable only after testing)

**Important:** HSTS should only be enabled after:
1. Ensuring all resources are available via HTTPS
2. Testing thoroughly in staging environment
3. Understanding that it cannot be easily reverted once set

### 4. X-XSS-Protection

**Value:** `1; mode=block`

**Purpose:** Enables XSS filtering in older browsers and blocks the page if an attack is detected.

**Note:** Modern browsers use Content-Security-Policy instead, but this header provides defense-in-depth for older clients.

### 5. Referrer-Policy

**Value:** `strict-origin-when-cross-origin`

**Purpose:** Controls how much referrer information is sent with requests.

**Behavior:**
- Same-origin requests: Full URL is sent
- Cross-origin HTTPS→HTTPS: Only origin is sent
- HTTPS→HTTP: No referrer is sent (prevents leaking HTTPS URLs to HTTP sites)

**Why this value:** Balances functionality (allowing analytics and debugging) with privacy (preventing sensitive information in URLs from leaking).

### 6. Content-Security-Policy (CSP)

**Default Value:**
```
default-src 'self';
script-src 'self';
style-src 'self' 'unsafe-inline';
img-src 'self' data: https:;
font-src 'self' data:;
connect-src 'self';
frame-ancestors 'none';
base-uri 'self';
form-action 'self'
```

**Purpose:** Primary defense against XSS attacks by controlling which resources can be loaded.

**Directives Explained:**
- `default-src 'self'`: Only allow resources from same origin by default
- `script-src 'self'`: JavaScript can only be loaded from same origin (no inline scripts)
- `style-src 'self' 'unsafe-inline'`: Styles from same origin + inline styles (needed for many UI libraries)
- `img-src 'self' data: https:`: Images from same origin, data URIs, and HTTPS sources
- `font-src 'self' data:`: Fonts from same origin and data URIs
- `connect-src 'self'`: API calls only to same origin
- `frame-ancestors 'none'`: Cannot be embedded (complements X-Frame-Options)
- `base-uri 'self'`: Restricts base tag to same origin
- `form-action 'self'`: Forms can only submit to same origin

**Customization:** Can be overridden with custom policy if needed (e.g., for CDN usage).

### 7. Permissions-Policy

**Default Value:**
```
geolocation=(), microphone=(), camera=(), payment=(),
usb=(), magnetometer=(), gyroscope=(), accelerometer=()
```

**Purpose:** Disables browser features that are not needed for the application.

**Why these restrictions:** Medical record applications typically don't need:
- Geolocation (PHI privacy concern)
- Camera/Microphone (unless explicitly needed for telemedicine)
- Payment APIs (handled separately)
- Device sensors (not relevant for medical records)

## Usage

### Basic Usage

Add the middleware to your FastAPI application:

```python
from app.middleware.security_headers import SecurityHeadersMiddleware

app = FastAPI()
app.add_middleware(SecurityHeadersMiddleware)
```

### Production Configuration

Use the production factory for secure defaults:

```python
from app.middleware.security_headers import create_production_security_middleware

app = FastAPI()

# Apply production security middleware
middleware = create_production_security_middleware(app)
app.add_middleware(
    SecurityHeadersMiddleware,
    enable_hsts=middleware.enable_hsts,
    hsts_max_age=middleware.hsts_max_age,
    hsts_include_subdomains=middleware.hsts_include_subdomains,
    frame_options=middleware.frame_options,
    content_type_options=middleware.content_type_options,
    xss_protection=middleware.xss_protection,
    referrer_policy=middleware.referrer_policy,
    csp_policy=middleware.csp_policy,
    permissions_policy=middleware.permissions_policy,
)
```

### Custom CSP Configuration

If you need to allow resources from specific CDNs:

```python
custom_csp = (
    "default-src 'self'; "
    "script-src 'self' https://cdn.example.com; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data: https:; "
    "connect-src 'self' https://api.example.com"
)

middleware = create_production_security_middleware(app, custom_csp=custom_csp)
```

## Testing

### Running Tests

```bash
# Run all security headers tests
pytest backend-hormonia/tests/middleware/test_security_headers.py -v

# Run specific test class
pytest backend-hormonia/tests/middleware/test_security_headers.py::TestSecurityHeadersMiddleware -v

# Run with coverage
pytest backend-hormonia/tests/middleware/test_security_headers.py --cov=app.middleware.security_headers
```

### Manual Testing

Test security headers in production:

```bash
# Check all security headers
curl -I https://your-api-domain.com/api/v2/health

# Expected headers:
# X-Frame-Options: DENY
# X-Content-Type-Options: nosniff
# Strict-Transport-Security: max-age=31536000; includeSubDomains
# X-XSS-Protection: 1; mode=block
# Referrer-Policy: strict-origin-when-cross-origin
# Content-Security-Policy: default-src 'self'; ...
# Permissions-Policy: geolocation=(), ...
```

### Security Scanning

Use online tools to verify headers:
- [Security Headers](https://securityheaders.com/)
- [Mozilla Observatory](https://observatory.mozilla.org/)

## Security Considerations

### HIPAA Compliance

These security headers support HIPAA compliance by:
1. Preventing unauthorized embedding of PHI displays (X-Frame-Options)
2. Enforcing HTTPS for all connections (HSTS)
3. Preventing XSS attacks that could leak PHI (CSP)
4. Controlling information leakage via referrers (Referrer-Policy)

### Defense in Depth

Security headers are ONE layer of defense. Also ensure:
- ✅ Input validation on all endpoints
- ✅ Output encoding to prevent XSS
- ✅ Authentication and authorization on all protected routes
- ✅ Rate limiting to prevent abuse
- ✅ HTTPS/TLS configuration with strong ciphers
- ✅ Regular security updates for dependencies

### CSP Reporting

For production monitoring, consider adding CSP reporting:

```python
csp_with_reporting = (
    "default-src 'self'; "
    "script-src 'self'; "
    "report-uri https://your-domain.com/api/csp-report"
)
```

This allows monitoring of CSP violations to detect potential attacks or misconfigurations.

## Migration to Main Application

### Step 1: Add to main.py

```python
# In backend-hormonia/app/main.py

from app.middleware.security_headers import create_production_security_middleware

app = FastAPI(
    title="Hormonia Oncology Clinic API",
    version="1.0.0"
)

# Add security headers middleware FIRST
# (middleware is executed in reverse order of registration)
middleware = create_production_security_middleware(app)
app.add_middleware(
    SecurityHeadersMiddleware,
    enable_hsts=middleware.enable_hsts,
    hsts_max_age=middleware.hsts_max_age,
    hsts_include_subdomains=middleware.hsts_include_subdomains,
    frame_options=middleware.frame_options,
    content_type_options=middleware.content_type_options,
    xss_protection=middleware.xss_protection,
    referrer_policy=middleware.referrer_policy,
    csp_policy=middleware.csp_policy,
    permissions_policy=middleware.permissions_policy,
)

# Add other middleware after...
app.add_middleware(CORSMiddleware, ...)
```

### Step 2: Environment Configuration

Add to `.env.production`:

```bash
# Security Headers Configuration
SECURITY_HEADERS_ENABLED=true
SECURITY_HEADERS_HSTS_ENABLED=true
SECURITY_HEADERS_HSTS_MAX_AGE=31536000
SECURITY_HEADERS_HSTS_INCLUDE_SUBDOMAINS=true
SECURITY_HEADERS_HSTS_PRELOAD=false
```

### Step 3: Verify in Production

After deployment:
1. Check headers with curl or browser DevTools
2. Run security scanner (securityheaders.com)
3. Verify application functionality (especially authentication flows)
4. Monitor CSP reports if enabled

## Troubleshooting

### Issue: Inline styles not working

**Solution:** The CSP allows `'unsafe-inline'` for styles by default. If still blocked, check if other middleware is setting conflicting CSP headers.

### Issue: Third-party resources blocked

**Solution:** Update CSP to allow specific domains:
```python
custom_csp = create_production_security_middleware(
    app,
    custom_csp="default-src 'self'; script-src 'self' https://trusted-cdn.com"
)
```

### Issue: HSTS prevents access to local development

**Solution:** HSTS is only set for HTTPS requests. Local HTTP development is not affected. For testing HTTPS locally, use a reverse proxy with self-signed certificates.

### Issue: Application embedded in iframe breaks

**Solution:** This is intentional. If legitimate embedding is needed (e.g., in a trusted portal), change to:
```python
app.add_middleware(SecurityHeadersMiddleware, frame_options="SAMEORIGIN")
```

## References

- [OWASP Secure Headers Project](https://owasp.org/www-project-secure-headers/)
- [MDN Web Security Headers](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers#security)
- [Content Security Policy Reference](https://content-security-policy.com/)
- [HSTS Preload List](https://hstspreload.org/)

## Changelog

### v1.0.0 (2025-10-09)
- Initial implementation of security headers middleware
- Production-ready defaults for medical applications
- Comprehensive test suite
- Documentation and migration guide
