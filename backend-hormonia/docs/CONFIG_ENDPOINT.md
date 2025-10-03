# Backend Configuration Endpoint Documentation

## Overview

The `/config` endpoint provides PUBLIC runtime configuration to frontend applications without exposing sensitive secrets.

## Endpoints

- **Primary**: `/api/v1/config`
- **Alias**: `/config` (for frontend convenience)

## Authentication

- **None Required** - This is a public endpoint
- No authentication headers needed
- CORS enabled for all origins

## Response Format

### VITE_* Naming Convention

All frontend-facing variables use the `VITE_*` prefix for compatibility with Vite build tools:

```json
{
  "VITE_API_BASE_URL": "https://backend.railway.app/api/v1",
  "VITE_WS_BASE_URL": "wss://backend.railway.app/ws",
  "VITE_API_URL": "https://backend.railway.app",
  "VITE_ENVIRONMENT": "production",
  "VITE_DEFAULT_LOCALE": "pt-BR",
  "VITE_SUPPORTED_LOCALES": ["en", "pt-BR", "es"],
  "VITE_MONTHLY_QUIZ_URL": "https://quiz.railway.app",

  "features": {
    "enableRealtime": true,
    "enableAnalytics": true,
    "enableEvolution": true,
    "enableMonthlyQuizViaLink": true,
    "enableAIHumanization": true
  },

  "cors": {
    "allowedOrigins": ["http://localhost:3000", "https://frontend.railway.app"],
    "credentials": true
  }
}
```

### Legacy Format

During the transition period, both VITE_* and legacy field names are provided:

```json
{
  "VITE_API_BASE_URL": "...",
  "API_BASE_URL": "...",  // Same value, legacy name

  "VITE_ENVIRONMENT": "production",
  "ENVIRONMENT": "production"  // Same value, legacy name
}
```

## Configuration Variables

### Required Environment Variables

Backend `.env` file should include:

```bash
# API URL for frontend (optional - auto-detected if not set)
FRONTEND_API_URL=https://backend.railway.app

# Frontend URLs for CORS (optional - enhances CORS handling)
FRONTEND_URL=https://frontend.railway.app
QUIZ_URL=https://quiz.railway.app

# Firebase Web App Config (PUBLIC - safe for frontend)
FIREBASE_WEB_API_KEY=AIza...
FIREBASE_WEB_PROJECT_ID=my-project
FIREBASE_WEB_APP_ID=1:123:web:abc
FIREBASE_AUTH_DOMAIN=my-project.firebaseapp.com
```

### Railway Environment Variables

Railway automatically provides:
- `RAILWAY_PUBLIC_DOMAIN` - Public domain for the service
- `RAILWAY_STATIC_URL` - Static URL for the deployment

These are automatically detected and used for URL building.

## URL Building Logic

The endpoint uses the following priority for building API URLs:

1. **Explicit `FRONTEND_API_URL`** from environment
2. **Railway environment** (`RAILWAY_PUBLIC_DOMAIN` or `RAILWAY_STATIC_URL`)
3. **Environment-based default**:
   - Production: `https://backend-production.railway.app`
   - Development: `http://localhost:8000`

## Security Features

### What is EXPOSED (Safe)

✅ API URLs and WebSocket URLs
✅ Environment indicator (development/production)
✅ Feature flags
✅ Localization settings
✅ Public Firebase web app config
✅ CORS allowed origins list
✅ Monthly quiz base URL

### What is NEVER EXPOSED (Sensitive)

❌ `SUPABASE_ANON_KEY` - **REMOVED for security**
❌ `SUPABASE_SERVICE_ROLE_KEY` - Server-only
❌ `SECRET_KEY` - JWT signing key
❌ `DATABASE_URL` - Database credentials
❌ `REDIS_PASSWORD` - Redis credentials
❌ `GEMINI_API_KEY` - AI service keys
❌ `EVOLUTION_API_KEY` - WhatsApp API keys
❌ `FIREBASE_ADMIN_PRIVATE_KEY` - Firebase admin credentials

## CORS Configuration

### Headers Returned

```http
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, OPTIONS
Access-Control-Allow-Headers: Content-Type
Cache-Control: public, max-age=300
```

### Dynamic CORS Origins

The endpoint includes a `cors` object in the response showing allowed origins:

```json
{
  "cors": {
    "allowedOrigins": [
      "http://localhost:3000",
      "http://localhost:5173",
      "https://frontend.railway.app",
      "https://quiz.railway.app"
    ],
    "credentials": true
  }
}
```

This helps frontend developers understand which origins are allowed.

## Frontend Usage

### Vite (Recommended)

Create `.env.development` and `.env.production`:

```bash
# Fetch config at build time or runtime
# Option 1: Build-time (recommended for static values)
VITE_API_BASE_URL=http://localhost:8000/api/v1

# Option 2: Runtime (fetch from /config endpoint)
# Use fetch() in main.tsx/main.js before app initialization
```

### Runtime Configuration Loading

```typescript
// src/config/runtime.ts
export async function loadRuntimeConfig() {
  try {
    const response = await fetch('http://localhost:8000/config');
    const config = await response.json();

    // Store in window or state management
    window.__RUNTIME_CONFIG__ = config;

    return config;
  } catch (error) {
    console.error('Failed to load runtime config:', error);
    // Use fallback values
    return {
      VITE_API_BASE_URL: 'http://localhost:8000/api/v1',
      VITE_WS_BASE_URL: 'ws://localhost:8000/ws'
    };
  }
}

// src/main.tsx
import { loadRuntimeConfig } from './config/runtime';

loadRuntimeConfig().then(config => {
  // Initialize app with config
  createRoot(document.getElementById('root')!).render(
    <App config={config} />
  );
});
```

### React Example

```typescript
// src/hooks/useConfig.ts
import { useEffect, useState } from 'react';

export function useConfig() {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/config')  // Proxied to backend
      .then(res => res.json())
      .then(data => {
        setConfig(data);
        setLoading(false);
      })
      .catch(err => {
        console.error('Config fetch failed:', err);
        setLoading(false);
      });
  }, []);

  return { config, loading };
}

// Usage in component
function App() {
  const { config, loading } = useConfig();

  if (loading) return <div>Loading configuration...</div>;

  return (
    <ApiProvider baseUrl={config.VITE_API_BASE_URL}>
      {/* Your app */}
    </ApiProvider>
  );
}
```

## Feature Flags

### Available Flags

- `enableRealtime` - WebSocket real-time features
- `enableAnalytics` - Analytics and monitoring
- `enableEvolution` - WhatsApp integration
- `enableMonthlyQuizViaLink` - Monthly quiz link mode
- `enableAIHumanization` - AI message humanization

### Usage Example

```typescript
const config = await fetch('/config').then(r => r.json());

if (config.features.enableRealtime) {
  // Initialize WebSocket connection
  const ws = new WebSocket(config.VITE_WS_BASE_URL);
}

if (config.features.enableAnalytics) {
  // Initialize analytics
  initAnalytics();
}
```

## Testing

Run comprehensive tests:

```bash
# From Backend directory
pytest tests/test_config_endpoint.py -v

# Specific test categories
pytest tests/test_config_endpoint.py::TestConfigEndpoint -v
pytest tests/test_config_endpoint.py::TestConfigSecurity -v
```

### Test Coverage

- ✅ Basic endpoint accessibility
- ✅ Response structure validation
- ✅ VITE_* naming convention
- ✅ Security (no sensitive keys)
- ✅ CORS headers
- ✅ Feature flags
- ✅ Backward compatibility
- ✅ Railway environment detection
- ✅ Error handling and fallback
- ✅ Firebase public config
- ✅ URL format validation

## Caching

The endpoint returns `Cache-Control: public, max-age=300` header, allowing:

- **Browser caching** for 5 minutes
- **CDN caching** if deployed behind CDN
- Reduced backend load for static configuration

To force refresh:

```typescript
const config = await fetch('/config', {
  cache: 'no-cache'  // Bypass cache
}).then(r => r.json());
```

## Error Handling

### Fallback Configuration

If the endpoint encounters an error, it returns a fallback config:

```json
{
  "VITE_API_BASE_URL": "http://localhost:8000/api/v1",
  "VITE_WS_BASE_URL": "ws://localhost:8000/ws",
  "VITE_API_URL": "http://localhost:8000",
  "VITE_ENVIRONMENT": "development",
  "error": "Failed to build complete config, using fallback",
  "features": {
    "enableRealtime": false,
    "enableAnalytics": false
  }
}
```

### Frontend Error Handling

```typescript
async function getConfig() {
  try {
    const response = await fetch('/config');
    const config = await response.json();

    if (config.error) {
      console.warn('Config returned with error:', config.error);
      // Use fallback values or retry
    }

    return config;
  } catch (error) {
    console.error('Failed to fetch config:', error);
    // Return hardcoded fallback
    return {
      VITE_API_BASE_URL: 'http://localhost:8000/api/v1'
    };
  }
}
```

## Migration Guide

### From Old Format to VITE_* Format

**Before (Old Config)**:
```typescript
const API_URL = 'http://localhost:8000';
const API_BASE_URL = `${API_URL}/api/v1`;
```

**After (New Config)**:
```typescript
const config = await fetch('/config').then(r => r.json());
const API_URL = config.VITE_API_URL;
const API_BASE_URL = config.VITE_API_BASE_URL;
```

### Transition Period

During migration, both formats are available:

```typescript
// Both work, but prefer VITE_* format
const newWay = config.VITE_API_BASE_URL;  // ✅ Preferred
const oldWay = config.API_BASE_URL;        // ✅ Still works (same value)
```

## Troubleshooting

### Config endpoint returns 404

Check that `config` router is registered in `router_registry.py`:

```python
# Should have both routes:
app.include_router(config.router, prefix="/api/v1", tags=["Configuration"])
app.include_router(config.router, prefix="", tags=["Configuration"])
```

### URLs are incorrect

Set explicit `FRONTEND_API_URL` in backend `.env`:

```bash
FRONTEND_API_URL=https://your-backend.railway.app
```

### CORS errors

Ensure frontend origin is in `ALLOWED_ORIGINS`:

```bash
ALLOWED_ORIGINS=["http://localhost:3000","https://your-frontend.railway.app"]
```

Or set dynamic URLs:

```bash
FRONTEND_URL=https://your-frontend.railway.app
QUIZ_URL=https://your-quiz.railway.app
```

### Firebase config not showing

Set Firebase web app environment variables:

```bash
FIREBASE_WEB_API_KEY=AIza...
FIREBASE_WEB_PROJECT_ID=my-project
```

## Security Audit Checklist

Before deploying:

- [ ] No `SUPABASE_ANON_KEY` in response
- [ ] No `SUPABASE_SERVICE_ROLE_KEY` in response
- [ ] No database credentials in response
- [ ] No API keys in response (except public Firebase web key)
- [ ] No `SECRET_KEY` in response
- [ ] CORS properly configured
- [ ] Only public Firebase keys exposed (not admin SDK)
- [ ] All tests passing

Run security tests:

```bash
pytest tests/test_config_endpoint.py::TestConfigSecurity -v
```

## Support

For issues or questions:
- Check backend logs for config endpoint errors
- Verify environment variables are set correctly
- Test endpoint directly: `curl http://localhost:8000/config`
- Review test output: `pytest tests/test_config_endpoint.py -v --tb=short`
