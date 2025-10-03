# Frontend Deployment Guide - Complete Guide

## Overview

This comprehensive guide covers deployment of the Hormonia Frontend (React + TypeScript + Vite) with its advanced runtime configuration system, optimized for Railway, Vercel, Docker, and other cloud platforms.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Environment Configuration](#environment-configuration)
3. [Build Process](#build-process)
4. [Deployment Platforms](#deployment-platforms)
5. [Performance Optimization](#performance-optimization)
6. [Security Configuration](#security-configuration)
7. [Monitoring & Analytics](#monitoring--analytics)
8. [Troubleshooting](#troubleshooting)

## Architecture Overview

### Runtime Configuration System

The frontend uses a sophisticated configuration system that works in both build-time and runtime contexts:

```typescript
// config.ts - Main configuration orchestrator
export async function loadConfig() {
  const runtimeConfig = await getRuntimeConfig();

  const config = {
    // Supabase Configuration
    SUPABASE_URL: runtimeConfig.VITE_SUPABASE_URL,
    SUPABASE_ANON_KEY: runtimeConfig.VITE_SUPABASE_ANON_KEY,

    // API Configuration
    API_BASE_URL: runtimeConfig.VITE_API_URL || runtimeConfig.VITE_API_BASE_URL,
    WS_BASE_URL: runtimeConfig.VITE_WS_BASE_URL,

    // AI Features
    AI_CHAT_ENABLED: runtimeConfig.VITE_AI_CHAT_ENABLED === 'true',
    AI_ANALYTICS_ENABLED: runtimeConfig.VITE_AI_ANALYTICS_ENABLED === 'true',
    // ... more configurations
  };

  return config;
}
```

### Runtime Config Loading Strategy

The system uses a multi-layer configuration loading approach:

```typescript
// runtime-config.ts - Smart configuration loader
const configSources = [
  loadFromRuntimeAPI,      // 1. Runtime API endpoint
  loadFromWindowConfig,    // 2. Server-injected config
  loadFromMetaEnv,        // 3. Vite environment variables
  loadFromFallback        // 4. Production fallbacks
];
```

This ensures configuration works regardless of deployment platform limitations.

## Environment Configuration

### Required Environment Variables

Create a `.env` file in the Frontend-v2 directory:

```env
# Core Configuration
VITE_ENVIRONMENT=production
VITE_DEBUG_MODE=false

# Supabase Configuration
VITE_SUPABASE_URL=https://xxxxx.supabase.co
VITE_SUPABASE_ANON_KEY=your-supabase-anon-key
VITE_SUPABASE_REALTIME_ENABLED=true

# API Configuration
VITE_API_URL=https://your-backend-domain.com/api/v1
VITE_API_BASE_URL=https://your-backend-domain.com
VITE_WS_BASE_URL=wss://your-backend-domain.com/ws

# WhatsApp Integration
VITE_WHATSAPP_INSTANCE_NAME=hormonia-instance

# AI Services Configuration
VITE_OPENAI_API_KEY=your-openai-api-key
VITE_LANGCHAIN_API_KEY=your-langchain-api-key
VITE_GEMINI_API_KEY=your-gemini-api-key

# AI Feature Flags
VITE_AI_CHAT_ENABLED=true
VITE_AI_ANALYTICS_ENABLED=true
VITE_AI_INSIGHTS_ENABLED=true
VITE_AI_RECOMMENDATIONS_ENABLED=true

# Monitoring & Analytics
VITE_SENTRY_DSN=your-sentry-dsn
VITE_ANALYTICS_TRACKING_ID=your-analytics-id

# Security Settings
VITE_SESSION_TIMEOUT=3600000
VITE_TOKEN_REFRESH_THRESHOLD=300000

# File Upload Settings
VITE_MAX_FILE_SIZE=10485760
VITE_SUPPORTED_FILE_TYPES=image/jpeg,image/png,image/gif,application/pdf
```

### Optional Environment Variables

```env
# Development Settings
VITE_API_MOCK_MODE=false
VITE_ENABLE_DEVTOOLS=false

# Performance Settings
VITE_ENABLE_PWA=true
VITE_ENABLE_SERVICE_WORKER=true

# Feature Flags
VITE_ENABLE_EXPERIMENTAL_FEATURES=false
VITE_ENABLE_BETA_FEATURES=false
```

### Environment Validation

```typescript
// src/utils/env-validation.ts
export function validateEnvironmentVariables() {
  const required = [
    'VITE_SUPABASE_URL',
    'VITE_SUPABASE_ANON_KEY',
    'VITE_API_URL'
  ];

  const missing = required.filter(key => !import.meta.env[key]);

  if (missing.length > 0) {
    throw new Error(`Missing required environment variables: ${missing.join(', ')}`);
  }
}

// Validate on app startup
validateEnvironmentVariables();
```

## Build Process

### Production Build Configuration

**vite.config.ts:**

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'

export default defineConfig({
  plugins: [react()],

  resolve: {
    alias: {
      "@": resolve(__dirname, "./src"),
    },
  },

  build: {
    // Optimization for production
    target: 'esnext',
    minify: 'terser',
    sourcemap: false,

    // Code splitting
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom'],
          ui: ['@radix-ui/react-dialog', '@radix-ui/react-dropdown-menu'],
          utils: ['date-fns', 'clsx', 'tailwind-merge'],
          charts: ['recharts'],
          forms: ['react-hook-form', '@hookform/resolvers'],
        }
      }
    },

    // Bundle size limits
    chunkSizeWarningLimit: 1000,
  },

  // Preview server configuration (for Railway)
  preview: {
    port: 3000,
    host: '0.0.0.0'
  },

  // Development server
  server: {
    port: 3000,
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://127.0.0.1:8000',
        ws: true,
      }
    }
  }
})
```

### Build Scripts

**package.json scripts:**

```json
{
  "scripts": {
    "build": "vite build",
    "build:analyze": "vite build && npx vite-bundle-analyzer dist",
    "build:prod": "NODE_ENV=production vite build --mode production",
    "preview": "vite preview --port 3000 --host 0.0.0.0",
    "optimize": "npm run build:prod && npm run compress",
    "compress": "gzip -k -6 dist/**/*.{js,css,html,json}",
    "lighthouse": "lighthouse http://localhost:3000 --output html"
  }
}
```

### Bundle Analysis

```bash
# Analyze bundle size
npm run build
npx vite-bundle-analyzer dist

# Performance audit
npm run build
npx lighthouse http://localhost:3000 --output html --output-path ./lighthouse-report.html
```

## Deployment Platforms

### 1. Railway Deployment (Recommended)

Railway provides excellent support for React applications with automatic builds and deployments.

**Step 1: Prepare Repository**

```bash
# Ensure your project is ready
cd Frontend-v2
npm install
npm run build  # Test build locally
```

**Step 2: Configure Railway**

Create `railway.toml`:

```toml
[build]
builder = "nixpacks"
buildCommand = "npm ci && npm run build"

[deploy]
startCommand = "npm run preview"
healthcheckPath = "/"
healthcheckTimeout = 300

[[services]]
name = "frontend"
[services.settings]
generateDomain = true
[services.env]
NODE_ENV = "production"
```

**Step 3: Environment Configuration**

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and link project
railway login
railway link

# Set environment variables
railway variables set VITE_ENVIRONMENT=production
railway variables set VITE_DEBUG_MODE=false
railway variables set VITE_SUPABASE_URL="your-supabase-url"
railway variables set VITE_SUPABASE_ANON_KEY="your-supabase-anon-key"
railway variables set VITE_API_URL="https://your-backend-railway-url.up.railway.app/api/v1"
railway variables set VITE_API_BASE_URL="https://your-backend-railway-url.up.railway.app"
railway variables set VITE_WS_BASE_URL="wss://your-backend-railway-url.up.railway.app/ws"

# Set all other environment variables
railway variables set VITE_AI_CHAT_ENABLED=true
railway variables set VITE_AI_ANALYTICS_ENABLED=true
# ... continue with all variables
```

**Step 4: Deploy**

```bash
railway up
```

### 2. Vercel Deployment

Vercel is excellent for React applications with edge optimization.

**vercel.json Configuration:**

```json
{
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "framework": "vite",
  "installCommand": "npm ci",
  "env": {
    "VITE_ENVIRONMENT": "production",
    "VITE_DEBUG_MODE": "false"
  },
  "build": {
    "env": {
      "VITE_SUPABASE_URL": "@vite_supabase_url",
      "VITE_SUPABASE_ANON_KEY": "@vite_supabase_anon_key",
      "VITE_API_URL": "@vite_api_url",
      "VITE_API_BASE_URL": "@vite_api_base_url",
      "VITE_WS_BASE_URL": "@vite_ws_base_url"
    }
  },
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        {
          "key": "X-Content-Type-Options",
          "value": "nosniff"
        },
        {
          "key": "X-Frame-Options",
          "value": "DENY"
        },
        {
          "key": "X-XSS-Protection",
          "value": "1; mode=block"
        },
        {
          "key": "Strict-Transport-Security",
          "value": "max-age=63072000; includeSubDomains; preload"
        }
      ]
    }
  ],
  "rewrites": [
    {
      "source": "/((?!api/).*)",
      "destination": "/index.html"
    }
  ]
}
```

**Deploy to Vercel:**

```bash
# Install Vercel CLI
npm install -g vercel

# Deploy
vercel

# Set environment variables
vercel env add VITE_SUPABASE_URL production
vercel env add VITE_SUPABASE_ANON_KEY production
# ... add all environment variables

# Redeploy with new environment
vercel --prod
```

### 3. Netlify Deployment

**netlify.toml Configuration:**

```toml
[build]
  publish = "dist"
  command = "npm run build"

[build.environment]
  NODE_VERSION = "18"
  NPM_VERSION = "9"

[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200

[[headers]]
  for = "/*"
  [headers.values]
    X-Frame-Options = "DENY"
    X-XSS-Protection = "1; mode=block"
    X-Content-Type-Options = "nosniff"
    Strict-Transport-Security = "max-age=63072000; includeSubDomains; preload"

[[headers]]
  for = "/assets/*"
  [headers.values]
    Cache-Control = "public, max-age=31536000, immutable"
```

### 4. Docker Deployment

**Multi-stage Dockerfile:**

```dockerfile
# Build stage
FROM node:18-alpine as build

WORKDIR /app

# Copy package files
COPY package*.json ./
COPY pnpm-lock.yaml ./

# Install dependencies
RUN npm install -g pnpm
RUN pnpm install

# Copy source code
COPY . .

# Build application
RUN pnpm run build

# Production stage
FROM nginx:alpine

# Copy built assets
COPY --from=build /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Add runtime configuration script
COPY docker-runtime-config.sh /docker-entrypoint.d/
RUN chmod +x /docker-entrypoint.d/docker-runtime-config.sh

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

**nginx.conf:**

```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # Security headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/xml+rss application/json;

    # Static assets with long cache
    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # API proxy
    location /api/ {
        proxy_pass $BACKEND_URL/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket proxy
    location /ws {
        proxy_pass $BACKEND_WS_URL;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # SPA fallback
    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

**docker-runtime-config.sh:**

```bash
#!/bin/sh

# Runtime configuration injection for Docker
cat > /usr/share/nginx/html/config.js << EOF
window.__ENV_CONFIG__ = {
  VITE_SUPABASE_URL: '${VITE_SUPABASE_URL}',
  VITE_SUPABASE_ANON_KEY: '${VITE_SUPABASE_ANON_KEY}',
  VITE_API_URL: '${VITE_API_URL}',
  VITE_API_BASE_URL: '${VITE_API_BASE_URL}',
  VITE_WS_BASE_URL: '${VITE_WS_BASE_URL}',
  VITE_AI_CHAT_ENABLED: '${VITE_AI_CHAT_ENABLED:-true}',
  VITE_AI_ANALYTICS_ENABLED: '${VITE_AI_ANALYTICS_ENABLED:-true}',
  VITE_AI_INSIGHTS_ENABLED: '${VITE_AI_INSIGHTS_ENABLED:-true}',
  VITE_AI_RECOMMENDATIONS_ENABLED: '${VITE_AI_RECOMMENDATIONS_ENABLED:-true}',
  VITE_ENVIRONMENT: '${VITE_ENVIRONMENT:-production}',
  VITE_DEBUG_MODE: '${VITE_DEBUG_MODE:-false}'
};
EOF

# Add script tag to index.html
sed -i '/<head>/a \    <script src="/config.js"></script>' /usr/share/nginx/html/index.html
```

## Performance Optimization

### Code Splitting

```typescript
// Lazy loading components
const PatientDetail = lazy(() => import('@/pages/PatientDetail'));
const AIAnalytics = lazy(() => import('@/pages/AIAnalytics'));

// Route-based code splitting
const routes = [
  {
    path: '/patients/:id',
    element: (
      <Suspense fallback={<div>Loading...</div>}>
        <PatientDetail />
      </Suspense>
    ),
  },
  {
    path: '/analytics',
    element: (
      <Suspense fallback={<div>Loading...</div>}>
        <AIAnalytics />
      </Suspense>
    ),
  },
];
```

### Bundle Optimization

```typescript
// vite.config.ts
export default defineConfig({
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom'],
          ui: ['@radix-ui/react-dialog', '@radix-ui/react-dropdown-menu'],
          utils: ['date-fns', 'clsx', 'tailwind-merge'],
          charts: ['recharts'],
        }
      }
    },
    chunkSizeWarningLimit: 1000,
  },
});
```

### CDN and Caching

**Cloudflare Configuration:**

```javascript
// cloudflare-workers.js
addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

async function handleRequest(request) {
  const url = new URL(request.url)

  // Cache static assets for 1 year
  if (url.pathname.startsWith('/assets/')) {
    const response = await fetch(request)
    const newResponse = new Response(response.body, response)
    newResponse.headers.set('Cache-Control', 'public, max-age=31536000, immutable')
    return newResponse
  }

  // Default behavior
  return fetch(request)
}
```

## Security Configuration

### Content Security Policy

```html
<!-- index.html -->
<meta http-equiv="Content-Security-Policy" content="
  default-src 'self';
  script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net;
  style-src 'self' 'unsafe-inline' https://fonts.googleapis.com;
  font-src 'self' https://fonts.gstatic.com;
  img-src 'self' data: https:;
  connect-src 'self'
    https://*.supabase.co
    https://your-backend-domain.com
    wss://your-backend-domain.com
    https://api.openai.com
    https://api.anthropic.com;
  media-src 'self';
  object-src 'none';
  base-uri 'self';
  form-action 'self';
">
```

### API Security

```typescript
// API client with authentication
class APIClient {
  private getAuthHeaders() {
    const token = localStorage.getItem('auth_token');
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const response = await fetch(`${this.baseURL}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...this.getAuthHeaders(),
        ...options.headers,
      },
    });

    if (!response.ok) {
      throw new Error(`API Error: ${response.status}`);
    }

    return response.json();
  }
}
```

## Monitoring & Analytics

### Performance Monitoring

```typescript
// Performance tracking
export const usePerformanceMonitor = () => {
  const trackPageLoad = useCallback((pageName: string) => {
    if (typeof window !== 'undefined' && 'performance' in window) {
      const loadTime = performance.now();
      console.log(`[Performance] ${pageName} loaded in ${loadTime.toFixed(2)}ms`);

      // Send to analytics
      if (window.gtag) {
        window.gtag('event', 'page_load_time', {
          event_category: 'Performance',
          event_label: pageName,
          value: Math.round(loadTime)
        });
      }
    }
  }, []);

  return { trackPageLoad };
};
```

### Error Tracking

```typescript
// Error boundary with Sentry integration
import * as Sentry from '@sentry/react';

export function initializeErrorTracking() {
  if (import.meta.env.PROD && import.meta.env.VITE_SENTRY_DSN) {
    Sentry.init({
      dsn: import.meta.env.VITE_SENTRY_DSN,
      integrations: [
        new Sentry.BrowserTracing(),
      ],
      tracesSampleRate: 0.1,
      environment: import.meta.env.VITE_ENVIRONMENT || 'production'
    });
  }
}

export function logError(error: Error, context?: Record<string, any>) {
  console.error(error);

  if (import.meta.env.PROD) {
    Sentry.captureException(error, {
      contexts: { additional: context }
    });
  }
}
```

## Testing and Quality Assurance

### Pre-deployment Testing

```bash
# Run full test suite
npm run test

# Build and test production build
npm run build
npm run preview &
PREVIEW_PID=$!

# Wait for server to start
sleep 5

# Run E2E tests against preview
npm run test:e2e -- --baseUrl http://localhost:3000

# Kill preview server
kill $PREVIEW_PID
```

### Deployment Validation

```typescript
// scripts/validate-deployment.ts
async function validateDeployment() {
  const config = await loadConfig();

  // Test API connectivity
  try {
    const response = await fetch(`${config.API_BASE_URL}/health`);
    if (!response.ok) {
      throw new Error(`API health check failed: ${response.status}`);
    }
    console.log('✅ API connectivity: OK');
  } catch (error) {
    console.error('❌ API connectivity failed:', error);
    process.exit(1);
  }

  // Test Supabase connectivity
  try {
    const { createClient } = await import('@supabase/supabase-js');
    const supabase = createClient(config.SUPABASE_URL, config.SUPABASE_ANON_KEY);
    const { error } = await supabase.auth.getSession();
    if (error) throw error;
    console.log('✅ Supabase connectivity: OK');
  } catch (error) {
    console.error('❌ Supabase connectivity failed:', error);
    process.exit(1);
  }

  console.log('🎉 Deployment validation successful!');
}

validateDeployment();
```

## Troubleshooting

### Common Issues

1. **Environment Variables Not Loading:**
   ```typescript
   // Check runtime config loading
   import { getRuntimeConfig } from './lib/runtime-config';

   async function debugConfig() {
     const config = await getRuntimeConfig();
     console.log('Loaded config:', config);
   }
   ```

2. **API Connection Issues:**
   ```typescript
   // Test API connectivity
   async function testAPI() {
     try {
       const response = await fetch('/api/health');
       console.log('API Status:', response.status);
     } catch (error) {
       console.error('API Error:', error);
     }
   }
   ```

3. **Build Failures:**
   ```bash
   # Clear cache and rebuild
   rm -rf node_modules dist .vite
   npm ci
   npm run build
   ```

### Performance Issues

```bash
# Analyze bundle size
npm run build:analyze

# Check for unused dependencies
npx depcheck

# Audit for security issues
npm audit
```

### Debugging in Production

```typescript
// Add debug utilities for production
window.debugFrontend = {
  async getConfig() {
    return await getRuntimeConfig();
  },

  testAPI() {
    return fetch('/api/health').then(r => r.json());
  },

  getPerformance() {
    return performance.getEntriesByType('navigation');
  }
};
```

## Deployment Checklist

### Pre-deployment

- [ ] All tests passing
- [ ] Build successful without errors
- [ ] Environment variables configured
- [ ] Performance benchmarks met
- [ ] Security headers configured
- [ ] API endpoints validated
- [ ] Error tracking enabled

### Post-deployment

- [ ] Application loads successfully
- [ ] API connectivity verified
- [ ] Authentication working
- [ ] Real-time features operational
- [ ] AI features functioning (if enabled)
- [ ] Performance monitoring active
- [ ] Error tracking operational

### Monitoring Setup

- [ ] Performance dashboards configured
- [ ] Error alerts configured
- [ ] Usage analytics tracking
- [ ] Uptime monitoring active
- [ ] Security monitoring enabled

---

**Last Updated**: 2025-09-25
**Version**: 2.0.0
**Maintained By**: DevOps Team

This comprehensive deployment guide ensures your Hormonia Frontend System works reliably across different platforms and environments with optimal performance and security.