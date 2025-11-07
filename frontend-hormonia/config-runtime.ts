// Runtime Configuration Handler for Railway Deployment
// This handles cases where Docker buildArgs are not passed correctly

interface RuntimeConfig {
  VITE_API_URL: string
  VITE_API_BASE_URL?: string
  VITE_WS_URL: string
  NODE_ENV: string
}

// Check if we're in development mode
const isDevelopment = typeof import.meta !== 'undefined' && import.meta.env?.DEV

const devLog = (...args: unknown[]) => {
  if (isDevelopment) {
    console.warn(...args)
  }
}

// Declare global runtime config
declare global {
  interface Window {
    RUNTIME_CONFIG?: RuntimeConfig
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
    devLog('✅ Using runtime configuration from Railway')
    return window.RUNTIME_CONFIG
  }

  // Fallback to build-time environment variables
  const buildTimeConfig: RuntimeConfig = {
    VITE_API_URL: import.meta.env['VITE_API_URL'] || 'http://localhost:8000/api/v2',
    VITE_API_BASE_URL: import.meta.env['VITE_API_BASE_URL'] || '',
    VITE_WS_URL: import.meta.env['VITE_WS_URL'] || 'ws://localhost:8000/ws',
    NODE_ENV: import.meta.env['NODE_ENV'] || 'development'
  }

  devLog('⚙️  Using build-time configuration (runtime config not available)')
  return buildTimeConfig
}

/**
 * Get API configuration object
 */
export function getApiConfig() {
  const config = getRuntimeConfig()
  const baseUrl = config.VITE_API_BASE_URL || config.VITE_API_URL

  return {
    apiUrl: baseUrl,
    wsUrl: config.VITE_WS_URL,
    isProduction: config.NODE_ENV === 'production'
  }
}

/**
 * Debug configuration - logs current config
 */
export function debugConfig() {
  const config = getRuntimeConfig()
  devLog('🧭 Frontend Configuration Debug', {
    apiUrl: config.VITE_API_URL,
    wsUrl: config.VITE_WS_URL,
    environment: config.NODE_ENV
  })
  return config
}

// Auto-debug in development
if (typeof window !== 'undefined' && isDevelopment) {
  debugConfig()
}
