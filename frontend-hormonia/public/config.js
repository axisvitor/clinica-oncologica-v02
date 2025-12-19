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

  const FALLBACK_CONFIG = {
    VITE_API_URL: 'https://backend-clinica-production-161d.up.railway.app/api/v2',
    VITE_API_BASE_URL: 'https://backend-clinica-production-161d.up.railway.app',
    VITE_WS_BASE_URL: 'wss://backend-clinica-production-161d.up.railway.app/ws',
    VITE_WHATSAPP_INSTANCE_NAME: 'hormonia-instance',
    VITE_ENVIRONMENT: 'production',
    VITE_DEBUG_MODE: 'false',
    VITE_SESSION_TIMEOUT: '3600000',
    VITE_TOKEN_REFRESH_THRESHOLD: '300000',
    VITE_MAX_FILE_SIZE: '10485760',
    VITE_SUPPORTED_FILE_TYPES: 'image/jpeg,image/png,image/gif,application/pdf'
  };

  window.__ENV_CONFIG__ = window.__ENV_CONFIG__ || FALLBACK_CONFIG;

  const looksVersionedApiUrl = (value) => {
    return typeof value === 'string' && /\/api\/v2\/?$/.test(value);
  };

  const normalizeBackendConfig = (payload) => {
    if (!payload || typeof payload !== 'object') {
      return {};
    }

    const next = { ...payload };
    const apiUrl = next.VITE_API_URL;
    const apiBaseUrl = next.VITE_API_BASE_URL;

    const versionedApiUrl =
      looksVersionedApiUrl(apiUrl)
        ? apiUrl
        : looksVersionedApiUrl(apiBaseUrl)
          ? apiBaseUrl
          : null;

    const baseApiUrl =
      typeof apiBaseUrl === 'string' && apiBaseUrl.length > 0 && !looksVersionedApiUrl(apiBaseUrl)
        ? apiBaseUrl
        : typeof apiUrl === 'string' && apiUrl.length > 0 && !looksVersionedApiUrl(apiUrl)
          ? apiUrl
          : versionedApiUrl
            ? String(versionedApiUrl).replace(/\/api\/v2\/?$/, '')
            : null;

    if (baseApiUrl) {
      next.VITE_API_BASE_URL = baseApiUrl;
    }

    if (versionedApiUrl) {
      next.VITE_API_URL = versionedApiUrl;
    } else if (baseApiUrl) {
      next.VITE_API_URL = String(baseApiUrl).replace(/\/+$/, '') + '/api/v2';
    }

    if (next.VITE_WS_BASE_URL && !next.VITE_WS_URL) {
      next.VITE_WS_URL = next.VITE_WS_BASE_URL;
    }

    if (next.VITE_WS_URL && !next.VITE_WS_BASE_URL) {
      next.VITE_WS_BASE_URL = next.VITE_WS_URL;
    }

    return next;
  };

  if (typeof fetch !== 'function') {
    console.warn('[Config] Fetch API unavailable, using defaults');
    window.__ENV_CONFIG__ = FALLBACK_CONFIG;
    return;
  }

  fetch('/api/v2/system/config', {
    method: 'GET',
    cache: 'no-store',
    credentials: 'same-origin',
    headers: { 'Accept': 'application/json' }
  })
    .then((response) => (response && response.ok ? response.json() : null))
    .then((payload) => {
      const normalized = normalizeBackendConfig(payload);
      window.__ENV_CONFIG__ = Object.assign({}, FALLBACK_CONFIG, normalized);
    })
    .catch((error) => {
      console.warn('[Config] Failed to load config from /api/v2/system/config, using defaults', error);
      window.__ENV_CONFIG__ = FALLBACK_CONFIG;
    });
})();
