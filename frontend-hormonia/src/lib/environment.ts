/**
 * Environment Detection and Configuration Utilities
 *
 * Provides safe environment detection for production optimizations
 * and Railway deployment compatibility
 */

interface EnvironmentConfig {
  isDevelopment: boolean
  isProduction: boolean
  isTest: boolean
  isRailway: boolean
  apiUrl: string
  appVersion: string
  buildTime: string
  enableDebugLogs: boolean
  enableMockApi: boolean
  enableErrorReporting: boolean
  enablePerformanceMonitoring: boolean
}

/**
 * Detect current environment from multiple sources
 */
function detectEnvironment(): string {
  // Vite environment variable
  if (import.meta.env.NODE_ENV) {
    return import.meta.env.NODE_ENV
  }

  // Railway environment detection
  if (import.meta.env.VITE_RAILWAY_ENVIRONMENT) {
    return import.meta.env.VITE_RAILWAY_ENVIRONMENT
  }

  // Check hostname patterns
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname

    // Railway production domains
    if (hostname.includes('.railway.app') || hostname.includes('.up.railway.app')) {
      return 'production'
    }

    // Local development
    if (hostname === 'localhost' || hostname === '127.0.0.1' || hostname.startsWith('192.168.')) {
      return 'development'
    }

    // Preview/staging environments
    if (hostname.includes('preview') || hostname.includes('staging')) {
      return 'staging'
    }
  }

  // Default to production for safety
  return 'production'
}

/**
 * Detect Railway deployment
 */
function detectRailway(): boolean {
  // Railway environment variables
  if (import.meta.env.VITE_RAILWAY_PROJECT_ID ||
      import.meta.env.VITE_RAILWAY_SERVICE_ID ||
      import.meta.env.RAILWAY_PROJECT_ID) {
    return true
  }

  // Railway URL patterns
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname
    return hostname.includes('.railway.app') || hostname.includes('.up.railway.app')
  }

  return false
}

/**
 * Get API URL with Railway compatibility
 */
function getApiUrl(): string {
  // Explicit environment variable
  if (import.meta.env.VITE_API_URL) {
    return import.meta.env.VITE_API_URL
  }

  // Railway environment variables
  if (import.meta.env.VITE_RAILWAY_BACKEND_URL) {
    return import.meta.env.VITE_RAILWAY_BACKEND_URL
  }

  // Auto-detect based on current URL (for Railway)
  if (typeof window !== 'undefined') {
    const { protocol, hostname } = window.location

    // Railway deployment pattern
    if (hostname.includes('.railway.app') || hostname.includes('.up.railway.app')) {
      // Use the same domain for API (assuming backend is on same Railway project)
      return `${protocol}//${hostname}`
    }

    // Local development
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
      return 'http://localhost:8000'
    }
  }

  // Fallback to production URL
  return 'https://clinica-oncologica-v02-production.up.railway.app'
}

/**
 * Get app version from package.json or build
 */
function getAppVersion(): string {
  return import.meta.env.VITE_APP_VERSION ||
         import.meta.env.PACKAGE_VERSION ||
         '1.0.0'
}

/**
 * Get build timestamp
 */
function getBuildTime(): string {
  return import.meta.env.VITE_BUILD_TIME ||
         import.meta.env.BUILD_TIME ||
         new Date().toISOString()
}

/**
 * Create environment configuration
 */
function createEnvironmentConfig(): EnvironmentConfig {
  const env = detectEnvironment()
  const isRailway = detectRailway()

  const isDevelopment = env === 'development'
  const isProduction = env === 'production'
  const isTest = env === 'test'

  return {
    isDevelopment,
    isProduction,
    isTest,
    isRailway,
    apiUrl: getApiUrl(),
    appVersion: getAppVersion(),
    buildTime: getBuildTime(),
    enableDebugLogs: isDevelopment || env === 'staging',
    enableMockApi: isDevelopment && import.meta.env.VITE_ENABLE_MOCK_API === 'true',
    enableErrorReporting: isProduction || env === 'staging',
    enablePerformanceMonitoring: isProduction || env === 'staging'
  }
}

// Export singleton instance
export const environment = createEnvironmentConfig()

// Export utilities
export {
  detectEnvironment,
  detectRailway,
  getApiUrl,
  getAppVersion,
  getBuildTime,
  createEnvironmentConfig
}

export type { EnvironmentConfig }

// Development helpers
if (environment.enableDebugLogs) {
  console.log('🌍 Environment Configuration:', {
    environment: detectEnvironment(),
    isRailway: environment.isRailway,
    apiUrl: environment.apiUrl,
    version: environment.appVersion,
    buildTime: environment.buildTime
  })
}

// Production optimization flags
export const PRODUCTION_FLAGS = {
  // Enable React strict mode only in development
  ENABLE_STRICT_MODE: environment.isDevelopment,

  // Enable React DevTools only in development
  ENABLE_DEVTOOLS: environment.isDevelopment,

  // Enable source maps in production for debugging
  ENABLE_SOURCE_MAPS: environment.isProduction && environment.isRailway,

  // Enable performance profiling
  ENABLE_PROFILING: environment.enablePerformanceMonitoring,

  // Enable error boundaries everywhere except development
  ENABLE_ERROR_BOUNDARIES: !environment.isDevelopment,

  // Enable service worker in production
  ENABLE_SERVICE_WORKER: environment.isProduction,

  // Enable code splitting and lazy loading
  ENABLE_CODE_SPLITTING: true,

  // Enable bundle analysis in staging/production
  ENABLE_BUNDLE_ANALYSIS: environment.enableDebugLogs
} as const

// Railway-specific configurations
export const RAILWAY_CONFIG = {
  // Railway automatically provides HTTPS
  FORCE_HTTPS: environment.isRailway,

  // Railway has different timeout requirements
  API_TIMEOUT: environment.isRailway ? 30000 : 10000,

  // Railway deployment detection
  DEPLOYMENT_PLATFORM: environment.isRailway ? 'railway' : 'local',

  // Railway environment variables
  PROJECT_ID: import.meta.env.VITE_RAILWAY_PROJECT_ID || null,
  SERVICE_ID: import.meta.env.VITE_RAILWAY_SERVICE_ID || null
} as const

// Feature flags for React 19 compatibility
export const REACT_19_FLAGS = {
  // Enable React 19 concurrent features
  ENABLE_CONCURRENT_FEATURES: true,

  // Enable automatic batching
  ENABLE_AUTOMATIC_BATCHING: true,

  // Enable suspense for data fetching
  ENABLE_SUSPENSE_DATA_FETCHING: true,

  // Enable new JSX transform
  ENABLE_NEW_JSX_TRANSFORM: true,

  // Enable React 19 strict effects
  ENABLE_STRICT_EFFECTS: environment.isDevelopment
} as const