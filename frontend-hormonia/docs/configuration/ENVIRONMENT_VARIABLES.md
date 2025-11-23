# Environment Variable Configuration Guide

## Overview

The frontend uses a multi-layered configuration system with proper fallback mechanisms to ensure reliable operation in development, staging, and production environments.

## Configuration Priority Order

### API Base URL Resolution

The application resolves the API base URL in the following priority order:

1. **Runtime Config** (`API_BASE_URL` from config.ts)
   - Loaded asynchronously from `/api/config` endpoint
   - Used in production deployments with dynamic configuration

2. **VITE_API_BASE_URL** (Environment Variable)
   - Explicit base URL without `/api/v2` suffix
   - Preferred for production builds
   - Example: `https://api.yourdomain.com`

3. **VITE_API_URL** (Environment Variable)
   - Full API URL with `/api/v2` suffix
   - Base URL extracted by removing suffix
   - Example: `https://api.yourdomain.com/api/v2`

4. **Auto-Detection** (Production Only)
   - Uses `window.location` to determine base URL
   - Only active when not on localhost
   - Example: `https://yourdomain.com` → `https://yourdomain.com`

5. **Localhost Fallback** (Development)
   - Default: `http://localhost:8000`
   - Used when no other configuration is available

### WebSocket URL Resolution

WebSocket URLs are automatically upgraded based on page protocol:

1. **VITE_WS_BASE_URL** or **VITE_WS_URL**
   - Example: `ws://api.yourdomain.com/ws`

2. **Auto-Upgrade**
   - HTTP page: `ws://` protocol
   - HTTPS page: `wss://` protocol
   - Prevents mixed-content errors

3. **Development Fallback**
   - Default: `ws://localhost:8000/ws`

## Environment Variables Reference

### Required Variables

```bash
# API Configuration (choose one)
VITE_API_BASE_URL=https://api.yourdomain.com     # Preferred
# OR
VITE_API_URL=https://api.yourdomain.com/api/v2   # Alternative

# WebSocket Configuration
VITE_WS_BASE_URL=wss://api.yourdomain.com/ws     # Auto-upgraded based on protocol
```

### Optional Variables

```bash
# Environment Settings
VITE_ENVIRONMENT=production
VITE_DEBUG_MODE=false

# Security Settings
VITE_SESSION_TIMEOUT=3600000
VITE_TOKEN_REFRESH_THRESHOLD=300000

# Feature Flags
VITE_AI_CHAT_ENABLED=true
VITE_AI_ANALYTICS_ENABLED=true
```

## Configuration Examples

### Development (.env.development)

```bash
# Local development
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_BASE_URL=ws://localhost:8000/ws
VITE_ENVIRONMENT=development
VITE_DEBUG_MODE=true
```

### Staging (.env.staging)

```bash
# Staging environment
VITE_API_BASE_URL=https://staging-api.yourdomain.com
VITE_WS_BASE_URL=wss://staging-api.yourdomain.com/ws
VITE_ENVIRONMENT=staging
VITE_DEBUG_MODE=true
```

### Production (.env.production)

```bash
# Production environment
VITE_API_BASE_URL=https://api.yourdomain.com
VITE_WS_BASE_URL=wss://api.yourdomain.com/ws
VITE_ENVIRONMENT=production
VITE_DEBUG_MODE=false
```

### Railway Deployment

```bash
# Railway automatically provides these
RAILWAY_PROJECT_ID=<auto-set>
RAILWAY_SERVICE_ID=<auto-set>

# You must set these in Railway UI
VITE_API_BASE_URL=${{RAILWAY_PUBLIC_DOMAIN}}
VITE_WS_BASE_URL=wss://${{RAILWAY_PUBLIC_DOMAIN}}/ws
```

## Security Features

### HTTP to HTTPS Auto-Upgrade

The API client automatically upgrades HTTP URLs to HTTPS in production:

```typescript
// If page is served over HTTPS and API URL is HTTP
// http://api.yourdomain.com → https://api.yourdomain.com
```

**Conditions for auto-upgrade:**
- Page protocol is HTTPS
- Hostname is not localhost or 127.0.0.1
- Hostname is not a private IP (192.168.x.x)

### WebSocket Protocol Auto-Upgrade

WebSocket URLs are automatically upgraded to match page protocol:

```typescript
// HTTPS page
ws://api.yourdomain.com/ws → wss://api.yourdomain.com/ws

// HTTP page (development)
ws://localhost:8000/ws → ws://localhost:8000/ws
```

## Configuration Validation

The system validates configuration on startup:

```typescript
import { validateConfiguration, getConfigurationStatus } from '@/lib/config-loader';

// Check for missing required values
const missing = validateConfiguration();
if (missing.length > 0) {
  console.error('Missing configuration:', missing);
}

// Get detailed configuration status
const status = getConfigurationStatus();
console.log('Configuration status:', status);
```

## Troubleshooting

### Issue: API requests failing with CORS errors

**Solution:** Ensure API base URL is correctly configured

```bash
# Check current configuration
console.log(apiClient.getBaseURL());

# Should match your backend URL
# Development: http://localhost:8000
# Production: https://api.yourdomain.com
```

### Issue: Mixed content errors (HTTP/HTTPS)

**Solution:** Verify protocol configuration

```bash
# Production must use HTTPS
VITE_API_BASE_URL=https://api.yourdomain.com  # Not http://

# WebSocket will auto-upgrade to wss://
VITE_WS_BASE_URL=wss://api.yourdomain.com/ws
```

### Issue: WebSocket connection fails

**Solution:** Check WebSocket URL and protocol

```bash
# Development
VITE_WS_BASE_URL=ws://localhost:8000/ws

# Production (auto-upgrades to wss:// on HTTPS pages)
VITE_WS_BASE_URL=ws://api.yourdomain.com/ws
```

### Issue: Configuration not loading

**Solution:** Initialize configuration early in app lifecycle

```typescript
import { initializeConfig } from '@/lib/config-loader';

// In your app entry point (main.tsx)
async function initApp() {
  await initializeConfig();
  // ... render app
}
```

## Runtime Configuration

For dynamic configuration (Railway, Docker), use runtime config loading:

1. **Create `/public/config.js`:**

```javascript
window.RUNTIME_CONFIG = {
  VITE_API_BASE_URL: 'https://api.yourdomain.com',
  VITE_WS_BASE_URL: 'wss://api.yourdomain.com/ws'
};
```

2. **Load in `index.html`:**

```html
<head>
  <script src="/config.js"></script>
</head>
```

3. **Backend endpoint** (recommended):

```python
# FastAPI endpoint
@app.get("/api/config")
async def get_config():
    return {
        "VITE_API_BASE_URL": os.getenv("API_BASE_URL"),
        "VITE_WS_BASE_URL": os.getenv("WS_BASE_URL")
    }
```

## Best Practices

1. **Always use base URLs without trailing slashes**
   ```bash
   ✓ VITE_API_BASE_URL=https://api.yourdomain.com
   ✗ VITE_API_BASE_URL=https://api.yourdomain.com/
   ```

2. **Prefer VITE_API_BASE_URL over VITE_API_URL**
   ```bash
   # Preferred
   VITE_API_BASE_URL=https://api.yourdomain.com

   # Alternative (if you have full URL)
   VITE_API_URL=https://api.yourdomain.com/api/v2
   ```

3. **Use environment-specific files**
   ```
   .env.development
   .env.staging
   .env.production
   ```

4. **Never commit .env files to git**
   ```gitignore
   .env
   .env.local
   .env.*.local
   ```

5. **Validate configuration in production**
   ```typescript
   if (import.meta.env.PROD) {
     const missing = validateConfiguration();
     if (missing.length > 0) {
       console.error('Production configuration incomplete:', missing);
     }
   }
   ```
