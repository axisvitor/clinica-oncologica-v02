/// <reference types="vite/client" />

/**
 * Configuration System with Runtime Support for Railway Deployment
 *
 * This configuration system supports both build-time and runtime configuration loading.
 * It's designed to work with Railway deployments where build arguments might not be
 * properly passed to the Vite build process.
 */

import { createLogger } from './lib/logger';
import { getRuntimeConfig, getRuntimeConfigSync, isProduction } from './lib/runtime-config';

const logger = createLogger('Config');

/**
 * Automatically upgrades WebSocket protocol based on page protocol
 * Ensures wss:// is used when page is served over HTTPS
 *
 * @param wsUrl - WebSocket URL to upgrade
 * @returns Upgraded WebSocket URL with appropriate protocol
 */
function upgradeWebSocketProtocol(wsUrl: string | undefined): string | undefined {
  if (!wsUrl || typeof window === 'undefined') {
    return wsUrl
  }

  // Determine the appropriate protocol based on current page protocol
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'

  // Replace ws:// or wss:// with the appropriate protocol
  return wsUrl.replace(/^(ws|wss):/, protocol)
}

// Re-export runtime config functions for external access
export { getRuntimeConfig, getRuntimeConfigSync, isProduction } from './lib/runtime-config';

/**
 * Runtime configuration type definition
 */
interface RuntimeConfigType {
  API_BASE_URL: string
  WS_BASE_URL?: string
  WHATSAPP_INSTANCE_NAME: string
  AI_CHAT_ENABLED: boolean
  AI_ANALYTICS_ENABLED: boolean
  AI_INSIGHTS_ENABLED: boolean
  AI_RECOMMENDATIONS_ENABLED: boolean
  SENTRY_DSN?: string
  ANALYTICS_TRACKING_ID?: string
  ENVIRONMENT: string
  DEBUG_MODE: boolean
  SESSION_TIMEOUT: number
  TOKEN_REFRESH_THRESHOLD: number
  maxFileSize: number
  allowedFileTypes: string[]
  [key: string]: string | boolean | number | string[] | undefined
}

// Configuration state
let configPromise: Promise<RuntimeConfigType> | null = null;
let syncConfig: RuntimeConfigType | null = null;

/**
 * Use this in React components with useEffect or in async functions
 */
export async function loadConfig() {
  if (!configPromise) {
    configPromise = (async () => {
      try {
        const runtimeConfig = await getRuntimeConfig();

        const config = {

          // API Configuration
          // Prefer API base (domain) if provided; otherwise derive from API URL
          API_BASE_URL: runtimeConfig.VITE_API_BASE_URL || runtimeConfig.VITE_API_URL?.replace(/\/api\/v2$/, ''),

          // WebSocket Configuration
          // Prefer WS base if provided; fallback to WS URL
          // Auto-upgrade protocol to wss:// when using HTTPS
          WS_BASE_URL: upgradeWebSocketProtocol(runtimeConfig.VITE_WS_BASE_URL || runtimeConfig.VITE_WS_URL),

          // WhatsApp Configuration
          WHATSAPP_INSTANCE_NAME: runtimeConfig.VITE_WHATSAPP_INSTANCE_NAME || 'hormonia-instance',

          // AI Feature Flags
          AI_CHAT_ENABLED: runtimeConfig.VITE_AI_CHAT_ENABLED === 'true',
          AI_ANALYTICS_ENABLED: runtimeConfig.VITE_AI_ANALYTICS_ENABLED === 'true',
          AI_INSIGHTS_ENABLED: runtimeConfig.VITE_AI_INSIGHTS_ENABLED === 'true',
          AI_RECOMMENDATIONS_ENABLED: runtimeConfig.VITE_AI_RECOMMENDATIONS_ENABLED === 'true',

          // Monitoring & Analytics
          SENTRY_DSN: runtimeConfig.VITE_SENTRY_DSN,
          ANALYTICS_TRACKING_ID: runtimeConfig.VITE_ANALYTICS_TRACKING_ID,

          // Development Settings
          ENVIRONMENT: runtimeConfig.VITE_ENVIRONMENT || 'development',
          DEBUG_MODE: runtimeConfig.VITE_DEBUG_MODE === 'true',

          // Security Settings
          SESSION_TIMEOUT: parseInt(runtimeConfig.VITE_SESSION_TIMEOUT || '28800000', 10),
          TOKEN_REFRESH_THRESHOLD: parseInt(runtimeConfig.VITE_TOKEN_REFRESH_THRESHOLD || '300000', 10),

          // File upload settings
          maxFileSize: parseInt(runtimeConfig.VITE_MAX_FILE_SIZE || '10485760', 10),
          allowedFileTypes: runtimeConfig.VITE_SUPPORTED_FILE_TYPES?.split(',') || ['image/jpeg', 'image/png', 'image/gif', 'application/pdf']
        };

        // Validate required configuration
        if (!config.API_BASE_URL) {
          throw new Error('API URL is required. Check your environment configuration.');
        }

        // WebSocket is optional
        if (!config.WS_BASE_URL) {
          logger.warn('WebSocket URL not configured. Real-time features may be limited.');
        }

        syncConfig = config;
        return config;
      } catch (error) {
        logger.error('Failed to load configuration:', error);
        throw error;
      }
    })();
  }

  return configPromise;
}

// Backward compatibility exports - these will work once config is loaded
export let API_BASE_URL = '';
export let WS_BASE_URL = '';
export let WHATSAPP_INSTANCE_NAME = '';
export let SENTRY_DSN = '';
export let ANALYTICS_TRACKING_ID = '';
export let ENVIRONMENT = '';
export let DEBUG_MODE = false;
export let SESSION_TIMEOUT = 28800000;
export let TOKEN_REFRESH_THRESHOLD = 300000;

// Update exports when config is loaded
loadConfig().then(config => {
  if (config.API_BASE_URL !== API_BASE_URL) API_BASE_URL = config.API_BASE_URL;
  if (config.WS_BASE_URL && config.WS_BASE_URL !== WS_BASE_URL) WS_BASE_URL = config.WS_BASE_URL;
}).catch(error => {
  logger.error('Failed to initialize configuration:', error);
});

// Static fallback values from environment - NEW NAMING CONVENTION
const STATIC_WHATSAPP_INSTANCE_NAME = import.meta.env['VITE_WHATSAPP_INSTANCE_NAME'] || 'hormonia-instance';
const STATIC_SENTRY_DSN = import.meta.env['VITE_MONITORING_SENTRY_DSN'];
const STATIC_ANALYTICS_TRACKING_ID = import.meta.env['VITE_MONITORING_ANALYTICS_ID'];
const STATIC_ENVIRONMENT = import.meta.env['VITE_APP_ENVIRONMENT'] || 'development';
const STATIC_DEBUG_MODE = import.meta.env['VITE_APP_ENABLE_DEBUG'] === 'true';
const STATIC_SESSION_TIMEOUT = parseInt(import.meta.env['VITE_SESSION_TIMEOUT_MS'] || '28800000', 10);
const STATIC_TOKEN_REFRESH_THRESHOLD = parseInt(import.meta.env['VITE_SESSION_TOKEN_REFRESH_THRESHOLD_MS'] || '300000', 10);

// AI Feature Flag Statics - NEW NAMING: VITE_AI_ENABLE_*
const STATIC_AI_CHAT_ENABLED = import.meta.env['VITE_AI_ENABLE_CHAT'] === 'true' || import.meta.env['VITE_AI_ENABLE_CHAT'] === undefined;
const STATIC_AI_ANALYTICS_ENABLED = import.meta.env['VITE_AI_ENABLE_ANALYTICS'] === 'true' || import.meta.env['VITE_AI_ENABLE_ANALYTICS'] === undefined;
const STATIC_AI_INSIGHTS_ENABLED = import.meta.env['VITE_AI_ENABLE_INSIGHTS'] === 'true' || import.meta.env['VITE_AI_ENABLE_INSIGHTS'] === undefined;
const STATIC_AI_RECOMMENDATIONS_ENABLED = import.meta.env['VITE_AI_ENABLE_RECOMMENDATIONS'] === 'true' || import.meta.env['VITE_AI_ENABLE_RECOMMENDATIONS'] === undefined;

// Remove duplicate declarations - these variables are already declared above

/**
 * Application Configuration
 *
 * Core application settings and defaults.
 */
export const APP_CONFIG = {
  name: 'Neoplasias Litoral',
  version: '1.0.0',
  description: 'Sistema de Gestão de Terapia Hormonal',

  // Pagination defaults
  defaultPageSize: 20,
  maxPageSize: 100,

  // Cache settings
  cacheTime: 10 * 60 * 1000, // 10 minutes
  staleTime: 5 * 60 * 1000,  // 5 minutes

  // Real-time settings
  reconnectAttempts: 5,
  reconnectDelay: 1000,

  // File upload settings (from env vars) - NEW NAMING: VITE_UPLOAD_*
  maxFileSize: parseInt(import.meta.env['VITE_UPLOAD_MAX_SIZE_BYTES'] || '10485760', 10),
  allowedFileTypes: import.meta.env['VITE_UPLOAD_SUPPORTED_MIMETYPES']?.split(',') || ['image/jpeg', 'image/png', 'image/gif', 'application/pdf'],

  // AI Settings
  ai: {
    chatModelTemperature: 0.7,
    chatMaxTokens: 2000,
    analyticsRefreshInterval: 5 * 60 * 1000, // 5 minutes
    insightsUpdateInterval: 15 * 60 * 1000, // 15 minutes
    recommendationsCacheTime: 30 * 60 * 1000 // 30 minutes
  }
}

// Theme configuration
export const THEME_CONFIG = {
  defaultTheme: 'light',
  themes: ['light', 'dark'],
  colors: {
    primary: 'hsl(221.2 83.2% 53.3%)',
    secondary: 'hsl(210 40% 98%)',
    accent: 'hsl(210 40% 96%)',
    muted: 'hsl(210 40% 96%)',
    destructive: 'hsl(0 84.2% 60.2%)',
    success: 'hsl(142.1 76.2% 36.3%)',
    warning: 'hsl(47.9 95.8% 53.1%)'
  }
}

/**
 * Feature Flags Configuration
 *
 * Controls which features are enabled in the application.
 * Flags can be controlled via environment variables for easy toggling
 * between development and production environments.
 *
 * AI Features:
 * - AI_CHAT: Enable AI-powered chat interface (requires OPENAI_API_KEY or GEMINI_API_KEY)
 * - AI_INSIGHTS: Enable AI-driven insights and recommendations
 * - AI_ANALYTICS: Enable AI analytics dashboard with predictive analytics
 * - AI_RECOMMENDATIONS: Enable AI-powered treatment recommendations
 *
 * Environment Variables (NEW NAMING):
 * - VITE_AI_ENABLE_CHAT: 'true' | 'false' (default: true if API keys present)
 * - VITE_AI_ENABLE_ANALYTICS: 'true' | 'false' (default: true)
 * - VITE_AI_ENABLE_INSIGHTS: 'true' | 'false' (default: true)
 * - VITE_AI_ENABLE_RECOMMENDATIONS: 'true' | 'false' (default: true)
 * - VITE_OPENAI_API_KEY: OpenAI API key for AI features
 * - VITE_GEMINI_API_KEY: Google Gemini API key for AI features
 * - VITE_LANGCHAIN_API_KEY: LangChain API key for advanced AI workflows
 */
export const FEATURES = {
  // AI Features - Controlled by feature flags and API key availability
  AI_CHAT: STATIC_AI_CHAT_ENABLED,
  AI_INSIGHTS: STATIC_AI_INSIGHTS_ENABLED,
  AI_ANALYTICS: STATIC_AI_ANALYTICS_ENABLED,
  AI_RECOMMENDATIONS: STATIC_AI_RECOMMENDATIONS_ENABLED,

  // Integration Features
  ANALYTICS: !!STATIC_ANALYTICS_TRACKING_ID,
  ERROR_TRACKING: !!STATIC_SENTRY_DSN,
  WHATSAPP_INTEGRATION: !!STATIC_WHATSAPP_INSTANCE_NAME,

  // Development Features
  DEBUG: STATIC_DEBUG_MODE && STATIC_ENVIRONMENT === 'development',

  // Dashboard Features
  PHYSICIAN_DASHBOARD: true // Enable physician-specific dashboard
};

/**
 * AI Configuration Helper
 * Returns current AI service configuration and availability
 */
export const getAIConfig = () => ({
  chatEnabled: FEATURES.AI_CHAT,
  analyticsEnabled: FEATURES.AI_ANALYTICS,
  insightsEnabled: FEATURES.AI_INSIGHTS,
  recommendationsEnabled: FEATURES.AI_RECOMMENDATIONS,
  preferredProvider: 'backend'
});
