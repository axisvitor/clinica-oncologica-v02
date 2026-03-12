/// <reference types="vite/client" />

/**
 * Runtime configuration for the session-first frontend.
 * Values come directly from import.meta.env and are safe to inspect without exposing secrets.
 */

import { createLogger } from './logger'

const logger = createLogger('RuntimeConfig')

export interface RuntimeConfig {
  VITE_API_URL: string
  VITE_API_BASE_URL?: string
  VITE_WS_URL: string
  VITE_WS_BASE_URL?: string
  VITE_WHATSAPP_INSTANCE_NAME?: string

  VITE_AI_CHAT_ENABLED?: string
  VITE_AI_ANALYTICS_ENABLED?: string
  VITE_AI_SUMMARY_ENABLED?: string
  VITE_AI_INSIGHTS_ENABLED?: string
  VITE_AI_RECOMMENDATIONS_ENABLED?: string

  VITE_SENTRY_DSN?: string
  VITE_ANALYTICS_TRACKING_ID?: string

  VITE_ENVIRONMENT?: string
  VITE_DEBUG_MODE?: string
  VITE_SESSION_TIMEOUT?: string
  VITE_TOKEN_REFRESH_THRESHOLD?: string
  VITE_MAX_FILE_SIZE?: string
  VITE_SUPPORTED_FILE_TYPES?: string

  VITE_SHOW_DEMO_CREDENTIALS?: string
}

const CONFIG: RuntimeConfig = {
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

  VITE_SENTRY_DSN: import.meta.env['VITE_SENTRY_DSN'] || undefined,
  VITE_ANALYTICS_TRACKING_ID: import.meta.env['VITE_ANALYTICS_TRACKING_ID'] || undefined,

  VITE_ENVIRONMENT: import.meta.env['VITE_APP_ENVIRONMENT'] || 'development',
  VITE_DEBUG_MODE: import.meta.env['VITE_APP_ENABLE_DEBUG'] || 'false',
  VITE_SESSION_TIMEOUT: import.meta.env['VITE_SESSION_TIMEOUT_MS'] || '3600000',
  VITE_TOKEN_REFRESH_THRESHOLD:
    import.meta.env['VITE_SESSION_TOKEN_REFRESH_THRESHOLD_MS'] || '300000',
  VITE_MAX_FILE_SIZE: import.meta.env['VITE_UPLOAD_MAX_SIZE_BYTES'] || '10485760',
  VITE_SUPPORTED_FILE_TYPES:
    import.meta.env['VITE_UPLOAD_SUPPORTED_MIMETYPES'] ||
    'image/jpeg,image/png,image/gif,application/pdf',

  VITE_SHOW_DEMO_CREDENTIALS: import.meta.env['VITE_SHOW_DEMO_CREDENTIALS'] || 'false',
}

if (import.meta.env['DEV']) {
  logger.log('Config loaded:', {
    API_URL: CONFIG.VITE_API_URL,
    API_BASE_URL: CONFIG.VITE_API_BASE_URL,
    WS_URL: CONFIG.VITE_WS_URL,
    auth_mode: 'first-party-session',
    websocket_ready: Boolean(CONFIG.VITE_WS_URL || CONFIG.VITE_WS_BASE_URL),
  })
}

export async function getRuntimeConfig(): Promise<RuntimeConfig> {
  return CONFIG
}

export function getRuntimeConfigSync(): RuntimeConfig {
  return CONFIG
}

export async function refreshRuntimeConfig(): Promise<RuntimeConfig> {
  return CONFIG
}

export async function getConfigValue<K extends keyof RuntimeConfig>(
  key: K,
  fallback?: RuntimeConfig[K]
): Promise<RuntimeConfig[K] | undefined> {
  return CONFIG[key] || fallback
}

export function isProduction(): boolean {
  return import.meta.env.MODE === 'production' || import.meta.env.PROD === true
}

export { CONFIG as PRODUCTION_FALLBACK_CONFIG }
