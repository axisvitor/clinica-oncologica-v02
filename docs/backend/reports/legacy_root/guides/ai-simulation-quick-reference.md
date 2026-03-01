# AI Simulation Guards - Quick Reference

## 🚨 P0 Critical Issue - RESOLVED

All AI endpoints now have runtime guards to prevent production use of simulation mode.

## 🎯 Quick Setup

### For Development (Default)
```bash
# .env file or environment
APP_ENVIRONMENT=development
ALLOW_AI_SIMULATION=true
```
✅ Simulation allowed, warnings logged

### For Production (Recommended)
```bash
# .env file or environment
APP_ENVIRONMENT=production
ALLOW_AI_SIMULATION=false
```
🛑 Simulation blocked, 501 error returned

### For Production Testing (Not Recommended)
```bash
# .env file or environment
APP_ENVIRONMENT=production
ALLOW_AI_SIMULATION=true
```
⚠️ Simulation allowed, warnings logged

## 📋 Protected Endpoints

| Endpoint | Method | Purpose | Status |
|----------|--------|---------|--------|
| `/api/v2/ai/insights/generate` | POST | Generate patient insights | ✅ Protected |
| `/api/v2/ai/humanize` | POST | Humanize messages | ✅ Protected |
| `/api/v2/ai/analysis/sentiment` | POST | Sentiment analysis | ✅ Protected |
| `/api/v2/ai/analysis/risk` | POST | Risk analysis | ✅ Protected |
| `/api/v2/ai/analysis/response` | POST | Response quality | ✅ Protected |

## 🔒 What Happens When Blocked?

**Request**:
```bash
curl -X POST https://api.example.com/api/v2/ai/insights/generate \
  -H "Authorization: Bearer TOKEN" \
  -d '{"patient_id": "uuid", "days": 30}'
```

**Response** (when `ALLOW_AI_SIMULATION=false` in production):
```json
{
  "status_code": 501,
  "detail": "AI service not configured. Real AI integration required for production."
}
```

**Logs**:
```json
{
  "level": "ERROR",
  "message": "[PRODUCTION ERROR] AI service not configured - simulation mode blocked",
  "extra": {
    "patient_id": "uuid",
    "user_id": "uuid",
    "endpoint": "insights",
    "environment": "production"
  }
}
```

## 📊 Behavior Matrix

| Environment | Setting | Simulation | Logs | API Response |
|-------------|---------|------------|------|--------------|
| `development` | `true` | ✅ Allowed | ⚠️ Warning | 200 OK + mock data |
| `development` | `false` | 🛑 Blocked | ❌ Error | 501 Not Implemented |
| `production` | `true` | ⚠️ Allowed | ⚠️ Warning | 200 OK + mock data |
| `production` | `false` | 🛑 Blocked | ❌ Error | 501 Not Implemented |

## 🧪 Testing

### Test Simulation Block
```python
import pytest
from fastapi import HTTPException

async def test_blocked_in_production():
    with patch("app.api.v2.routers.ai.insights.settings") as mock_settings:
        mock_settings.APP_ENVIRONMENT = "production"
        mock_settings.ALLOW_AI_SIMULATION = False

        with pytest.raises(HTTPException) as exc:
            await generate_patient_insights(...)

        assert exc.value.status_code == 501
```

### Test Simulation Allowed
```python
async def test_allowed_in_development():
    with patch("app.api.v2.routers.ai.insights.settings") as mock_settings:
        mock_settings.APP_ENVIRONMENT = "development"
        mock_settings.ALLOW_AI_SIMULATION = True

        response = await generate_patient_insights(...)
        assert response is not None  # Should work
```

## 🔍 Monitoring

### Log Search Queries

**Find Production Errors**:
```bash
grep "[PRODUCTION ERROR]" /var/log/app.log
```

**Find Simulation Usage**:
```bash
grep "[SIMULATION MODE]" /var/log/app.log
```

**Count by Endpoint**:
```bash
grep "SIMULATION MODE" /var/log/app.log | grep -o 'endpoint": "[^"]*' | sort | uniq -c
```

## 📝 Files Modified

| File | Purpose |
|------|---------|
| `/app/config/settings/base.py` | Added `ALLOW_AI_SIMULATION` config |
| `/app/config/settings/__init__.py` | Added boolean parser + validation |
| `/app/api/v2/routers/ai/insights.py` | Runtime guard + logging |
| `/app/api/v2/routers/ai/humanize.py` | Runtime guard + logging |
| `/app/api/v2/routers/ai/analysis.py` | Runtime guard + logging (3 endpoints) |

## 🚀 Deployment Checklist

Before deploying to production:

- [ ] Set `APP_ENVIRONMENT=production`
- [ ] Set `ALLOW_AI_SIMULATION=false`
- [ ] Configure real AI services (Gemini API)
- [ ] Test AI endpoints return real data
- [ ] Verify no `[SIMULATION MODE]` logs in production
- [ ] Monitor for `[PRODUCTION ERROR]` logs

## 💡 Quick Tips

1. **Default is safe**: Development mode allows simulation by default
2. **Production requires opt-in**: Must explicitly allow simulation in production
3. **Clear errors**: Users get 501 with clear message, not silent failures
4. **Audit trail**: All simulation usage is logged
5. **Easy override**: Can enable simulation for testing with env var

## 📚 Full Documentation

- Implementation Details: `/docs/ai-simulation-guards-implementation.md`
- Completion Report: `/docs/P0-AI-SIMULATION-GUARDS-COMPLETE.md`
- Tests: `/tests/test_ai_simulation_guards.py`

## 🆘 Troubleshooting

**Problem**: Getting 501 errors in development
```bash
# Solution: Enable simulation
export ALLOW_AI_SIMULATION=true
```

**Problem**: Simulation running in production
```bash
# Solution: Disable simulation
export ALLOW_AI_SIMULATION=false
```

**Problem**: Need to test simulation in production
```bash
# Solution: Temporarily enable (not recommended)
export ALLOW_AI_SIMULATION=true
# Remember to set back to false!
```

## ✅ Verification

Check current configuration:
```python
from app.core.config import settings

print(f"Environment: {settings.APP_ENVIRONMENT}")
print(f"Allow Simulation: {settings.ALLOW_AI_SIMULATION}")
```

Expected in production:
```
Environment: production
Allow Simulation: False
```
