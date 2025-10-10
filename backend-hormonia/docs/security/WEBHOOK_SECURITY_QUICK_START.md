# Webhook Security - Quick Start Guide

## ⚡ Quick Setup (2 minutes)

### 1. Generate Webhook Secret
```bash
python -c 'import secrets; print(secrets.token_urlsafe(32))'
```

### 2. Add to Environment
```bash
# In .env file
EVOLUTION_WEBHOOK_SECRET="<generated-secret-from-step-1>"
```

### 3. Restart Application
```bash
# Webhook validation is now enabled automatically
```

---

## ✅ Verify Installation

### Test Endpoints
```bash
# Should succeed with valid signature
curl -X POST http://localhost:8000/webhooks/whatsapp/evolution/test \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Signature: <valid-signature>" \
  -H "X-Webhook-Timestamp: $(date +%s)" \
  -d '{"test":true}'

# Should fail without signature (401 Unauthorized)
curl -X POST http://localhost:8000/webhooks/whatsapp/evolution/test \
  -H "Content-Type: application/json" \
  -d '{"test":true}'
```

---

## 📋 Key Files

| File | Purpose |
|------|---------|
| `app/middleware/webhook_validator.py` | Middleware implementation |
| `app/utils/security_validation.py` | Signature utilities |
| `tests/middleware/test_webhook_security.py` | Comprehensive tests |
| `docs/security/WEBHOOK_SECURITY.md` | Full documentation |

---

## 🔑 Signature Generation (For Webhook Senders)

```python
import hmac
import hashlib
import time

def generate_webhook_signature(body: bytes, secret_key: str) -> tuple[str, str]:
    """Generate signature and timestamp for webhook."""
    timestamp = str(int(time.time()))
    message = body + timestamp.encode('utf-8')
    signature = hmac.new(
        secret_key.encode('utf-8'),
        message,
        hashlib.sha256
    ).hexdigest()
    return signature, timestamp

# Example usage
body = b'{"event": "message.sent"}'
secret = "your-webhook-secret"
signature, timestamp = generate_webhook_signature(body, secret)

# Include in headers:
# X-Webhook-Signature: <signature>
# X-Webhook-Timestamp: <timestamp>
```

---

## 🛡️ Security Features

- ✅ HMAC-SHA256 signature validation
- ✅ Replay attack prevention (5-minute window)
- ✅ Constant-time comparison (timing-attack resistant)
- ✅ Configurable time windows
- ✅ Comprehensive logging

---

## ⚙️ Configuration Options

```python
# In app/core/middleware_setup.py
app.add_middleware(
    WebhookValidatorMiddleware,
    secret_key=settings.EVOLUTION_WEBHOOK_SECRET,  # Required
    max_timestamp_age=300,                         # 5 minutes (default)
    signature_header="X-Webhook-Signature",        # Custom header name
    timestamp_header="X-Webhook-Timestamp",        # Custom header name
    webhook_paths=["/webhooks/"]                   # Paths to validate
)
```

---

## 🐛 Troubleshooting

### "Missing required header: x-webhook-signature"
**Solution:** Ensure webhook sender includes `X-Webhook-Signature` header

### "Invalid webhook signature"
**Solution:** Verify secret key matches between sender and receiver

### "Invalid or expired webhook timestamp"
**Solution:** Check timestamp is within 5 minutes and clocks are synchronized

### Validation Disabled
**Solution:** Set `EVOLUTION_WEBHOOK_SECRET` in environment variables

---

## 📊 Test Results

```bash
# Run comprehensive test suite
cd backend-hormonia
pytest tests/middleware/test_webhook_security.py -v

# Expected: 29 passed in <1s
```

---

## 📚 Full Documentation

See **`docs/security/WEBHOOK_SECURITY.md`** for:
- Detailed security model
- Integration examples
- Performance analysis
- Compliance information
- Advanced configurations

---

**Quick Reference Version:** 1.0.0
**Last Updated:** 2025-10-09
**Status:** ✅ Production Ready
