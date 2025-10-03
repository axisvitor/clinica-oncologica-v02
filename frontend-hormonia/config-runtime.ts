// Runtime Configuration Handler for Railway Deployment
// This handles cases where Docker buildArgs are not passed correctly

interface RuntimeConfig {
  VITE_SUPABASE_URL: string;
  VITE_SUPABASE_ANON_KEY: string;
  VITE_API_URL: string;
  VITE_API_BASE_URL: string;
  VITE_WS_BASE_URL: string;
  NODE_ENV: string;
}

// Check if we're in development mode
const isDevelopment = typeof import.meta !== 'undefined' && import.meta.env?.DEV;

// Declare global runtime config
declare global {
  interface Window {
    RUNTIME_CONFIG?: RuntimeConfig;
  }
}

/**
 * Get configuration with fallback priority:
 * 1. Runtime config (injected by Railway at runtime)
 * 2. Build-time environment variables (if buildArgs worked)
 * 3. Fallback defaults for development
 */
export function getRuntimeConfig(): RuntimeConfig {
  // Try runtime config first (injected by start.sh)
  if (typeof window !== 'undefined' && window.RUNTIME_CONFIG) {
    if (isDevelopment) {
      console.log('✅ Using runtime configuration from Railway');
    }
    return window.RUNTIME_CONFIG;
  }

  // Fallback to build-time environment variables
  const buildTimeConfig: RuntimeConfig = {
    VITE_SUPABASE_URL: import.meta.env['VITE_SUPABASE_URL'] || '',
    VITE_SUPABASE_ANON_KEY: import.meta.env['VITE_SUPABASE_ANON_KEY'] || '',
    VITE_API_URL: import.meta.env['VITE_API_URL'] || 'https://backend-production-e0bd.up.railway.app/api/v1', // deprecated, use VITE_API_BASE_URL
    VITE_API_BASE_URL: import.meta.env['VITE_API_BASE_URL'] || 'https://backend-production-e0bd.up.railway.app',
    VITE_WS_BASE_URL: import.meta.env['VITE_WS_BASE_URL'] || 'wss://backend-production-e0bd.up.railway.app/ws',
    NODE_ENV: import.meta.env['NODE_ENV'] || 'production'
  };

  if (isDevelopment) {
    console.log('⚠️  Using build-time configuration (runtime config not available)');
  }
  return buildTimeConfig;
}

/**
 * Get API configuration object
 */
export function getApiConfig() {
  const config = getRuntimeConfig();

  return {
    apiUrl: config.VITE_API_URL,
    apiBaseUrl: config.VITE_API_BASE_URL,
    wsUrl: config.VITE_WS_BASE_URL,
    supabaseUrl: config.VITE_SUPABASE_URL,
    supabaseAnonKey: config.VITE_SUPABASE_ANON_KEY,
    isProduction: config.NODE_ENV === 'production'
  };
}

/**
 * Debug configuration - logs current config
 */
export function debugConfig() {
  const config = getRuntimeConfig();
  if (isDevelopment) {
    console.group('🔧 Frontend Configuration Debug');
    console.log('Supabase URL:', config.VITE_SUPABASE_URL);
    console.log('API URL:', config.VITE_API_URL);
    console.log('API Base URL:', config.VITE_API_BASE_URL);
    console.log('WebSocket URL:', config.VITE_WS_BASE_URL);
    console.log('Environment:', config.NODE_ENV);
    console.groupEnd();
  }
  return config;
}

// Auto-debug in development
if (typeof window !== 'undefined' && isDevelopment) {
  debugConfig();
}