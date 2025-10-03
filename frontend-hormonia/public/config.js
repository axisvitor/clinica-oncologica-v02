/**
 * Runtime Configuration
 * This file provides fallback configuration for development
 */

(function() {
  // Skip loading in development - Vite handles env vars
  const isDev = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';

  if (isDev) {
    console.log('[Config] Development mode - using Vite environment variables');
    return;
  }

  // In production, try to load configuration from the API endpoint
  const script = document.createElement('script');
  script.src = '/api/config.js';
  script.type = 'text/javascript';

  // Add to head before other scripts
  const firstScript = document.getElementsByTagName('script')[0];
  if (firstScript && firstScript.parentNode) {
    firstScript.parentNode.insertBefore(script, firstScript);
  } else {
    document.head.appendChild(script);
  }

  // Fallback configuration if API config fails to load
  window.addEventListener('error', function(e) {
    if (e.target && e.target.src && e.target.src.includes('/api/config.js')) {
      console.warn('[Config] Failed to load config from /api/config.js, using defaults');

      window.__ENV_CONFIG__ = {
        VITE_SUPABASE_URL: '',
        VITE_SUPABASE_ANON_KEY: '',
        VITE_API_URL: 'https://backend-production-e0bd.up.railway.app/api/v1',
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
    }
  }, true);
})();