# Rate Limiting Documentation

## Overview

This document describes the rate limiting implementation for authentication endpoints in the Hormonia Backend API. Rate limiting is essential for preventing brute force attacks, credential stuffing, and API abuse.

## Implementation

### Technology

- **Library**: SlowAPI (https://github.com/laurents/slowapi)
- **Storage**: Redis (production) or in-memory (development)
- **Strategy**: Fixed time window

### Configuration

Rate limiting is configured in `app/config.py`:

```python
RATE_LIMIT_ENABLED: bool = True  # Enable/disable rate limiting
RATE_LIMIT_REDIS_URL: Optional[str] = None  # Custom Redis URL (uses REDIS_URL if not set)
```

### Rate Limits by Endpoint

| Endpoint | Limit | Description |
|----------|-------|-------------|
| `/api/v1/auth/login` | 5/minute | Login attempts per IP |
| `/api/v1/auth/login-json` | 5/minute | JSON login attempts per IP |
| `/api/v1/auth/refresh` | 20/minute | Token refresh per IP |
| `/api/v1/auth/password` | 3/hour | Password changes per IP |
| `/api/v1/auth/avatar` | 10/hour | Avatar uploads per IP |
| `/api/v1/auth/profile` | 20/hour | Profile updates per IP |

### IP Detection

The rate limiter uses intelligent IP detection:

1. **X-Forwarded-For**: Checks for proxy/load balancer header
2. **X-Real-IP**: Alternative proxy header
3. **Direct IP**: Falls back to direct client IP

This ensures accurate rate limiting even behind proxies (Railway, Nginx, etc.).

## Usage

### Environment Variables

```bash
# Enable rate limiting (default: true)
RATE_LIMIT_ENABLED=true

# Use custom Redis URL for rate limiting (optional)
# Falls back to REDIS_URL, then in-memory
RATE_LIMIT_REDIS_URL=rediss://your-redis-url:6379

# Main Redis URL (used if RATE_LIMIT_REDIS_URL not set)
REDIS_URL=rediss://your-redis-url:6379
```

### Error Response Format

When rate limit is exceeded, the API returns HTTP 429:

```json
{
  "error": "too_many_requests",
  "message": "Muitas tentativas. Tente novamente mais tarde.",
  "retry_after": "60",
  "limit": "5/minute"
}
```

### Testing

Run the rate limiting tests:

```bash
# Run all rate limit tests
pytest backend-hormonia/tests/test_rate_limiting.py -v

# Run specific test
pytest backend-hormonia/tests/test_rate_limiting.py::TestLoginRateLimit::test_login_rate_limit_exceeded -v
```

### Monitoring

Rate limit violations are logged with structured logging:

```python
logger.warning(
    f"Rate limit exceeded for IP {client_ip} on {request.method} {request.url.path}",
    extra={
        "client_ip": client_ip,
        "path": str(request.url.path),
        "method": request.method
    }
)
```

## Security Considerations

### Bypassing Rate Limits

Rate limits are per-IP address, which provides basic protection but can be bypassed by:

1. **Distributed attacks**: Attackers using multiple IPs
2. **VPNs/Proxies**: Rotating IP addresses

### Additional Protection Layers

For production environments, consider:

1. **Account lockout**: Lock accounts after N failed attempts
2. **CAPTCHA**: Challenge users after rate limit
3. **WAF**: Web Application Firewall for advanced protection
4. **Geo-blocking**: Block requests from suspicious countries
5. **Behavioral analysis**: Detect patterns across IPs

### Redis Security

Ensure Redis is secured:

```bash
# Use TLS/SSL
REDIS_URL=rediss://...  # Note: 'rediss' with double 's'

# Use authentication
REDIS_PASSWORD=your-secure-password

# Enable SSL certificate verification
REDIS_SSL_CERT_REQS=required
```

## Deployment

### Railway Deployment

Rate limiting works automatically on Railway:

1. **Redis**: Use Railway Redis plugin or external Redis
2. **Environment**: Set `REDIS_URL` in Railway environment
3. **Scaling**: Rate limits are shared across all instances (via Redis)

### Local Development

For local development without Redis:

```bash
# Rate limiting will use in-memory storage
# Warning will be logged
RATE_LIMIT_ENABLED=true
```

**Note**: In-memory storage means:
- Rate limits are per-process
- Not suitable for production
- Resets on application restart

## Customization

### Adjusting Limits

Edit `app/utils/rate_limiter.py`:

```python
RATE_LIMITS = {
    "login": "5/minute",              # Change to "10/minute"
    "password_reset": "3/hour",       # Change to "5/hour"
    # ... etc
}
```

### Adding New Protected Endpoints

```python
from app.utils.rate_limiter import limiter

@router.post("/new-endpoint")
@limiter.limit("10/minute")  # Add rate limit
async def new_endpoint(request: Request):
    # ... endpoint logic
```

### Custom Rate Limit Keys

By default, rate limiting uses IP address. To use custom keys:

```python
from app.utils.rate_limiter import limiter

def get_user_id(request: Request) -> str:
    # Extract user ID from token
    return request.state.user_id

# Apply user-based rate limiting
@limiter.limit("100/hour", key_func=get_user_id)
async def user_specific_endpoint(request: Request):
    # ... endpoint logic
```

## Troubleshooting

### Issue: Rate Limit Not Working

**Check**:
1. `RATE_LIMIT_ENABLED=true` in environment
2. Redis connection is healthy
3. Limiter is registered in `application_factory.py`

### Issue: Too Restrictive

**Solution**:
- Increase limits in `RATE_LIMITS` dict
- Add IP whitelist for internal services
- Use user-based limiting instead of IP-based

### Issue: Redis Connection Errors

**Solution**:
```python
# Falls back to in-memory automatically
# Check logs for: "Using in-memory rate limiting"
```

## References

- [SlowAPI Documentation](https://github.com/laurents/slowapi)
- [OWASP Rate Limiting Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Denial_of_Service_Cheat_Sheet.html)
- [Redis Documentation](https://redis.io/docs/)

## Changelog

### v2.0.0 (2025-01-03)
- Implemented Redis-based rate limiting
- Added rate limits to all auth endpoints
- Created comprehensive test suite
- Added monitoring and logging
