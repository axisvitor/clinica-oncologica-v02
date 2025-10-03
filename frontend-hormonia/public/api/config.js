/**
 * Railway Environment Configuration Endpoint
 *
 * This endpoint provides runtime configuration for the frontend application.
 * It reads environment variables that Railway sets at runtime and exposes them
 * to the frontend in a safe way.
 *
 * This file should be served as a static asset by the web server.
 * In Railway, this will be served at /api/config
 */

// Check if we're in a browser environment
if (typeof window !== 'undefined') {
  // Browser environment - provide configuration
  // SECURITY: These placeholder values should be replaced by Railway environment variables
  window.__ENV_CONFIG__ = {
    VITE_SUPABASE_URL: '',
    VITE_SUPABASE_ANON_KEY: '',
    // VITE_API_URL is deprecated - use VITE_API_BASE_URL instead
    VITE_API_BASE_URL: 'https://backend-production-e0bd.up.railway.app',
    VITE_WS_BASE_URL: 'wss://backend-production-e0bd.up.railway.app/ws',
    VITE_WHATSAPP_INSTANCE_NAME: 'hormonia-instance',
    VITE_ENVIRONMENT: 'production',
    VITE_DEBUG_MODE: 'false',
    VITE_SESSION_TIMEOUT: '3600000',
    VITE_TOKEN_REFRESH_THRESHOLD: '300000',
    VITE_MAX_FILE_SIZE: '10485760',
    VITE_SUPPORTED_FILE_TYPES: 'image/jpeg,image/png,image/gif,application/pdf'
  };

  // Also make it available as a response for fetch requests
  if (window.location.pathname === '/api/config') {
    // Return as JSON response
    document.body.innerHTML = JSON.stringify(window.__ENV_CONFIG__, null, 2);
    document.body.style.fontFamily = 'monospace';
    document.body.style.whiteSpace = 'pre';
  }
} else {
  // Node.js environment (if this file is somehow loaded in Node.js)
  // SECURITY: These placeholder values should be replaced by Railway environment variables
  const config = {
    VITE_SUPABASE_URL: process.env['VITE_SUPABASE_URL'] || '',
    VITE_SUPABASE_ANON_KEY: process.env['VITE_SUPABASE_ANON_KEY'] || '',
    // VITE_API_URL is deprecated - use VITE_API_BASE_URL instead
    VITE_API_BASE_URL: process.env['VITE_API_BASE_URL'] || 'https://backend-production-e0bd.up.railway.app',
    VITE_WS_BASE_URL: process.env['VITE_WS_BASE_URL'] || 'wss://backend-production-e0bd.up.railway.app/ws',
    VITE_WHATSAPP_INSTANCE_NAME: process.env['VITE_WHATSAPP_INSTANCE_NAME'] || 'hormonia-instance',
    VITE_OPENAI_API_KEY: process.env['VITE_OPENAI_API_KEY'],
    VITE_LANGCHAIN_API_KEY: process.env['VITE_LANGCHAIN_API_KEY'],
    VITE_SENTRY_DSN: process.env['VITE_SENTRY_DSN'],
    VITE_ANALYTICS_TRACKING_ID: process.env['VITE_ANALYTICS_TRACKING_ID'],
    VITE_ENVIRONMENT: process.env['VITE_ENVIRONMENT'] || 'production',
    VITE_DEBUG_MODE: process.env['VITE_DEBUG_MODE'] || 'false',
    VITE_SESSION_TIMEOUT: process.env['VITE_SESSION_TIMEOUT'] || '3600000',
    VITE_TOKEN_REFRESH_THRESHOLD: process.env['VITE_TOKEN_REFRESH_THRESHOLD'] || '300000',
    VITE_MAX_FILE_SIZE: process.env['VITE_MAX_FILE_SIZE'] || '10485760',
    VITE_SUPPORTED_FILE_TYPES: process.env['VITE_SUPPORTED_FILE_TYPES'] || 'image/jpeg,image/png,image/gif,application/pdf'
  };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = config;
  }
}