/**
 * Runtime Configuration - Entrypoint Substitution
 *
 * This file contains placeholders that are replaced by the Docker entrypoint at runtime.
 * This allows dynamic configuration without rebuilding the frontend image.
 *
 * Placeholders replaced by entrypoint.sh:
 * - BACKEND_URL_PLACEHOLDER → $BACKEND_URL environment variable
 *
 * The entrypoint uses sed to perform substitution before nginx serves this file.
 */

// Runtime configuration - valores substituídos pelo entrypoint
window.__RUNTIME_CONFIG__ = {
  // These placeholders are replaced by entrypoint.sh at container startup
  apiUrl: 'BACKEND_URL_PLACEHOLDER/api/v1',
  wsUrl: 'BACKEND_URL_PLACEHOLDER/ws'.replace('https://', 'wss://').replace('http://', 'ws://'),
  backendUrl: 'BACKEND_URL_PLACEHOLDER',

  // Build-time fallbacks (se entrypoint falhar ou para desenvolvimento local)
  fallbackApiUrl: typeof window.__ENV__ !== 'undefined' ? window.__ENV__.VITE_API_URL : undefined,
  fallbackWsUrl: typeof window.__ENV__ !== 'undefined' ? window.__ENV__.VITE_WS_BASE_URL : undefined,
}

/**
 * Helper function para obter configuração válida
 *
 * Verifica se o placeholder foi substituído e usa fallbacks se necessário.
 * Em desenvolvimento local, usa valores do .env automaticamente.
 *
 * @returns {Object} Configuração com apiUrl, wsUrl e backendUrl
 */
window.getRuntimeConfig = function() {
  const config = window.__RUNTIME_CONFIG__

  // Se placeholder ainda existe, usar fallback
  if (config.backendUrl.includes('PLACEHOLDER')) {
    console.warn('[Config] Runtime config not substituted, using build-time fallbacks')
    return {
      apiUrl: config.fallbackApiUrl || 'http://localhost:8000/api/v1',
      wsUrl: config.fallbackWsUrl || 'ws://localhost:8000/ws',
      backendUrl: config.fallbackApiUrl?.replace('/api/v1', '') || 'http://localhost:8000'
    }
  }

  return {
    apiUrl: config.apiUrl,
    wsUrl: config.wsUrl,
    backendUrl: config.backendUrl
  }
}

// Backward compatibility - mantém window.__ENV_CONFIG__ para código legado
window.__ENV_CONFIG__ = {
  VITE_API_BASE_URL: window.getRuntimeConfig().backendUrl,
  VITE_WS_BASE_URL: window.getRuntimeConfig().wsUrl,
  VITE_SUPABASE_URL: '',
  VITE_SUPABASE_ANON_KEY: '',
  VITE_WHATSAPP_INSTANCE_NAME: 'hormonia-instance',
  VITE_ENVIRONMENT: 'production',
  VITE_DEBUG_MODE: 'false',
  VITE_SESSION_TIMEOUT: '3600000',
  VITE_TOKEN_REFRESH_THRESHOLD: '300000',
  VITE_MAX_FILE_SIZE: '10485760',
  VITE_SUPPORTED_FILE_TYPES: 'image/jpeg,image/png,image/gif,application/pdf'
}

console.log('[Config] Runtime config loaded:', window.getRuntimeConfig())

// Suporte para renderização JSON (se acessado diretamente)
if (window.location.pathname === '/api/config') {
  document.body.innerHTML = JSON.stringify(window.getRuntimeConfig(), null, 2);
  document.body.style.fontFamily = 'monospace';
  document.body.style.whiteSpace = 'pre';
}