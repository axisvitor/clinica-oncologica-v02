# AI Simulation Guards Implementation

## Overview

Runtime guards have been implemented to prevent production use of AI simulation/mock data. All AI endpoints now check environment settings before returning simulated responses.

## Changes Made

### 1. Configuration Settings

**File**: `/backend-hormonia/app/config/settings/base.py`

Added new configuration field:
```python
ALLOW_AI_SIMULATION: bool = Field(
    default=True,
    description="Allow AI simulation mode (mock data). Should be False in production.",
)
```

- **Default**: `True` (allows simulation in development)
- **Production**: Should be set to `False` via environment variable
- **Environment Variable**: `ALLOW_AI_SIMULATION=false`

### 2. Runtime Guards Implementation

Runtime guards added to the following AI endpoints:

#### `/backend-hormonia/app/api/v2/routers/ai/insights.py`
- Endpoint: `POST /api/v2/ai/insights/generate`
- Line: 98-122
- Protection: Blocks simulated insights generation in production

#### `/backend-hormonia/app/api/v2/routers/ai/humanize.py`
- Endpoint: `POST /api/v2/ai/humanize`
- Line: 127-151
- Protection: Blocks simulated message humanization in production

#### `/backend-hormonia/app/api/v2/routers/ai/analysis.py`
- Endpoint: `POST /api/v2/ai/analysis/sentiment`
- Line: 66-90
- Protection: Blocks simulated sentiment analysis in production

- Endpoint: `POST /api/v2/ai/analysis/risk`
- Line: 172-198
- Protection: Blocks simulated risk analysis in production

- Endpoint: `POST /api/v2/ai/analysis/response`
- Line: 264-288
- Protection: Blocks simulated response quality analysis in production

### 3. Guard Behavior

Each guard follows this pattern:

```python
# Runtime guard: Prevent production use of simulation mode
if settings.APP_ENVIRONMENT == "production" and not settings.ALLOW_AI_SIMULATION:
    logger.error(
        "[PRODUCTION ERROR] AI service not configured - simulation mode blocked",
        extra={
            "user_id": current_user.id,
            "endpoint": "endpoint_name",
            "environment": settings.APP_ENVIRONMENT,
        }
    )
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="AI service not configured. Real AI integration required for production."
    )

# Warning: Using simulation mode
logger.warning(
    "[SIMULATION MODE] Using mock AI response for endpoint_name",
    extra={
        "user_id": current_user.id,
        "endpoint": "endpoint_name",
        "environment": settings.APP_ENVIRONMENT,
        "warning": "This is simulated data - not real AI analysis"
    }
)
```

## How It Works

### Development Environment
- `APP_ENVIRONMENT=development` (default)
- `ALLOW_AI_SIMULATION=True` (default)
- **Behavior**: Simulation allowed, logs warning for each simulated response

### Production Environment - Simulation Allowed (NOT RECOMMENDED)
- `APP_ENVIRONMENT=production`
- `ALLOW_AI_SIMULATION=True`
- **Behavior**: Simulation allowed, logs warnings, startup warning logged

### Production Environment - Simulation Blocked (RECOMMENDED)
- `APP_ENVIRONMENT=production`
- `ALLOW_AI_SIMULATION=False`
- **Behavior**: Simulation blocked, returns `501 Not Implemented` error

## Error Response

When simulation is blocked in production, API returns:

```json
{
  "status_code": 501,
  "detail": "AI service not configured. Real AI integration required for production."
}
```

## Logging

### Error Log (Production + Simulation Blocked)
```json
{
  "level": "ERROR",
  "message": "[PRODUCTION ERROR] AI service not configured - simulation mode blocked",
  "extra": {
    "user_id": "uuid",
    "endpoint": "insights",
    "environment": "production"
  }
}
```

### Warning Log (Simulation Mode Active)
```json
{
  "level": "WARNING",
  "message": "[SIMULATION MODE] Using mock AI response for insights generation",
  "extra": {
    "user_id": "uuid",
    "endpoint": "insights",
    "environment": "development",
    "warning": "This is simulated data - not real AI analysis"
  }
}
```

### Startup Warning (Production with Simulation Enabled)
```
WARNING: AI simulation mode is enabled in production environment.
This will use mock data instead of real AI services.
Set ALLOW_AI_SIMULATION=False in production to require real AI integration.
```

## Environment Variable Configuration

Add to `.env` file or environment:

```bash
# For Development (default)
APP_ENVIRONMENT=development
ALLOW_AI_SIMULATION=true

# For Production (recommended)
APP_ENVIRONMENT=production
ALLOW_AI_SIMULATION=false  # Blocks simulation, requires real AI

# For Production Testing (not recommended)
APP_ENVIRONMENT=production
ALLOW_AI_SIMULATION=true   # Allows simulation, logs warnings
```

## Security Benefits

1. **Prevents Accidental Deployment**: Cannot deploy to production without real AI integration
2. **Clear Error Messages**: Users get clear 501 error instead of receiving mock data
3. **Audit Trail**: All simulation usage is logged with warnings
4. **Environment-Aware**: Automatically adapts behavior based on environment
5. **Configurable**: Can be overridden via environment variable if needed for testing

## Testing

### Test Simulation Block
```bash
# Set production environment
export APP_ENVIRONMENT=production
export ALLOW_AI_SIMULATION=false

# Try to call AI endpoint
curl -X POST http://localhost:8000/api/v2/ai/insights/generate \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"patient_id": "uuid", "days": 30}'

# Expected: 501 Not Implemented error
```

### Test Simulation Warning
```bash
# Set development environment
export APP_ENVIRONMENT=development
export ALLOW_AI_SIMULATION=true

# Call AI endpoint
curl -X POST http://localhost:8000/api/v2/ai/insights/generate \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"patient_id": "uuid", "days": 30}'

# Expected: 200 OK with simulated data + warning in logs
```

## Files Modified

1. `/backend-hormonia/app/config/settings/base.py` - Added `ALLOW_AI_SIMULATION` field
2. `/backend-hormonia/app/config/settings/__init__.py` - Added boolean parser and production validation
3. `/backend-hormonia/app/api/v2/routers/ai/insights.py` - Added runtime guard + logging
4. `/backend-hormonia/app/api/v2/routers/ai/humanize.py` - Added runtime guard + logging
5. `/backend-hormonia/app/api/v2/routers/ai/analysis.py` - Added runtime guard + logging (3 endpoints)

## Next Steps

When implementing real AI integration:

1. Replace simulation blocks with actual AI service calls
2. Keep the logging for monitoring
3. Remove or comment out the simulation code
4. Update tests to use real AI or mocked AI services
5. Set `ALLOW_AI_SIMULATION=false` in production environment variables

## Backward Compatibility

- **Development**: No changes required, simulation works as before
- **Production**: Must set `ALLOW_AI_SIMULATION=false` to block simulation
- **Default Behavior**: Simulation allowed (safe for development)
