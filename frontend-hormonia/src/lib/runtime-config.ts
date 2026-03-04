/// <reference types="vite/client" />

/**
 * Configuration Module - SIMPLIFIED
 *
 * Uses import.meta.env directly from .env file.
 * Vite replaces these values at build time.
 */

import { createLogger } from './logger'

const logger = createLogger('RuntimeConfig')

// Environment configuration interface
export interface RuntimeConfig {
  VITE_API_URL: string
  VITE_API_BASE_URL?: string
  VITE_WS_URL: string
  VITE_WS_BASE_URL?: string
  VITE_WHATSAPP_INSTANCE_NAME?: string

  // Firebase Client Configuration
  VITE_FIREBASE_API_KEY?: string
  VITE_FIREBASE_AUTH_DOMAIN?: string
  VITE_FIREBASE_PROJECT_ID?: string
  VITE_FIREBASE_STORAGE_BUCKET?: string
  VITE_FIREBASE_MESSAGING_SENDER_ID?: string
  VITE_FIREBASE_APP_ID?: string
  VITE_FIREBASE_MEASUREMENT_ID?: string

  // AI Feature Flags
  VITE_AI_CHAT_ENABLED?: string
  VITE_AI_ANALYTICS_ENABLED?: string
  VITE_AI_SUMMARY_ENABLED?: string
  VITE_AI_INSIGHTS_ENABLED?: string
  VITE_AI_RECOMMENDATIONS_ENABLED?: string

  // Monitoring & Analytics
  VITE_SENTRY_DSN?: string
  VITE_ANALYTICS_TRACKING_ID?: string

  // Environment Settings
  VITE_ENVIRONMENT?: string
  VITE_DEBUG_MODE?: string
  VITE_SESSION_TIMEOUT?: string
  VITE_TOKEN_REFRESH_THRESHOLD?: string
  VITE_MAX_FILE_SIZE?: string
  VITE_SUPPORTED_FILE_TYPES?: string

  // Demo Configuration
  VITE_SHOW_DEMO_CREDENTIALS?: string
}

/**
 * Configuration built directly from .env file via import.meta.env
 * Vite replaces these at build time with actual values from .env
 */
const CONFIG: RuntimeConfig = {
  // API URLs - directly from .env
  VITE_API_URL:
    import.meta.env['VITE_API_ENDPOINT_URL'] ||
    import.meta.env['VITE_API_URL'] ||
    `${import.meta.env['VITE_API_BASE_URL'] || 'http://localhost:8000'}/api/v2`,
  VITE_API_BASE_URL: import.meta.env['VITE_API_BASE_URL'] || 'http://localhost:8000',
  VITE_WS_URL:
    import.meta.env['VITE_WS_BASE_URL'] ||
    import.meta.env['VITE_WS_ENDPOINT_URL'] ||
    'ws://localhost:8000/ws',
  VITE_WS_BASE_URL:
    import.meta.env['VITE_WS_BASE_URL'] ||
    import.meta.env['VITE_WS_ENDPOINT_URL'] ||
    'ws://localhost:8000/ws',
  VITE_WHATSAPP_INSTANCE_NAME:
    import.meta.env['VITE_WHATSAPP_INSTANCE_NAME'] || 'hormonia-instance',

  // Firebase Client Configuration
  VITE_FIREBASE_API_KEY: import.meta.env['VITE_FIREBASE_API_KEY'] || '',
  VITE_FIREBASE_AUTH_DOMAIN: import.meta.env['VITE_FIREBASE_AUTH_DOMAIN'] || '',
  VITE_FIREBASE_PROJECT_ID: import.meta.env['VITE_FIREBASE_PROJECT_ID'] || '',
  VITE_FIREBASE_STORAGE_BUCKET: import.meta.env['VITE_FIREBASE_STORAGE_BUCKET'] || '',
  VITE_FIREBASE_MESSAGING_SENDER_ID: import.meta.env['VITE_FIREBASE_MESSAGING_SENDER_ID'] || '',
  VITE_FIREBASE_APP_ID: import.meta.env['VITE_FIREBASE_APP_ID'] || '',
  VITE_FIREBASE_MEASUREMENT_ID: import.meta.env['VITE_FIREBASE_MEASUREMENT_ID'] || '',

  // AI Feature Flags (support legacy *_ENABLED and current ENABLE_* names)
  VITE_AI_CHAT_ENABLED:
    import.meta.env['VITE_AI_CHAT_ENABLED'] || import.meta.env['VITE_AI_ENABLE_CHAT'] || 'true',
  VITE_AI_ANALYTICS_ENABLED:
    import.meta.env['VITE_AI_ANALYTICS_ENABLED'] ||
    import.meta.env['VITE_AI_ENABLE_ANALYTICS'] ||
    'true',
  VITE_AI_SUMMARY_ENABLED:
    import.meta.env['VITE_AI_SUMMARY_ENABLED'] ||
    import.meta.env['VITE_AI_ENABLE_SUMMARY'] ||
    'true',
  VITE_AI_INSIGHTS_ENABLED:
    import.meta.env['VITE_AI_INSIGHTS_ENABLED'] ||
    import.meta.env['VITE_AI_ENABLE_INSIGHTS'] ||
    'false',
  VITE_AI_RECOMMENDATIONS_ENABLED:
    import.meta.env['VITE_AI_RECOMMENDATIONS_ENABLED'] ||
    import.meta.env['VITE_AI_ENABLE_RECOMMENDATIONS'] ||
    'true',

  // Environment Settings
  VITE_ENVIRONMENT: import.meta.env['VITE_APP_ENVIRONMENT'] || 'development',
  VITE_DEBUG_MODE: import.meta.env['VITE_APP_ENABLE_DEBUG'] || 'false',
  VITE_SESSION_TIMEOUT: import.meta.env['VITE_SESSION_TIMEOUT_MS'] || '3600000',
  VITE_TOKEN_REFRESH_THRESHOLD:
    import.meta.env['VITE_SESSION_TOKEN_REFRESH_THRESHOLD_MS'] || '300000',
  VITE_MAX_FILE_SIZE: import.meta.env['VITE_UPLOAD_MAX_SIZE_BYTES'] || '10485760',
  VITE_SUPPORTED_FILE_TYPES:
    import.meta.env['VITE_UPLOAD_SUPPORTED_MIMETYPES'] ||
    'image/jpeg,image/png,image/gif,application/pdf',

  // Demo Configuration
  VITE_SHOW_DEMO_CREDENTIALS: import.meta.env['VITE_SHOW_DEMO_CREDENTIALS'] || 'false',
}

// Log config on load for debugging
if (import.meta.env['DEV']) {
  logger.log('Config loaded:', {
    API_URL: CONFIG.VITE_API_URL,
    API_BASE_URL: CONFIG.VITE_API_BASE_URL,
    WS_URL: CONFIG.VITE_WS_URL,
  })
}

/**
 * Gets the runtime configuration (async for compatibility)
 */
export async function getRuntimeConfig(): Promise<RuntimeConfig> {
  return CONFIG
}

/**
 * Gets the runtime configuration synchronously
 */
export function getRuntimeConfigSync(): RuntimeConfig {
  return CONFIG
}

/**
 * Forces a refresh of the runtime configuration (no-op in simplified version)
 */
export async function refreshRuntimeConfig(): Promise<RuntimeConfig> {
  return CONFIG
}

/**
 * Gets a specific configuration value with fallback
 */
export async function getConfigValue<K extends keyof RuntimeConfig>(
  key: K,
  fallback?: RuntimeConfig[K]
): Promise<RuntimeConfig[K] | undefined> {
  return CONFIG[key] || fallback
}

/**
 * Checks if the app is running in production mode
 */
export function isProduction(): boolean {
  return import.meta.env.MODE === 'production' || import.meta.env.PROD === true
}

// Export the config object for direct access
export { CONFIG as PRODUCTION_FALLBACK_CONFIG }
