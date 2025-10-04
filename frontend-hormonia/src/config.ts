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

// Re-export runtime config functions for external access
export { getRuntimeConfig, getRuntimeConfigSync, isProduction } from './lib/runtime-config';

// Configuration state
let configPromise: Promise<any> | null = null;
let syncConfig: any = null;

/**
 * Loads configuration asynchronously
 * Use this in React components with useEffect or in async functions
 */
export async function loadConfig() {
  if (!configPromise) {
    configPromise = (async () => {
      try {
        const runtimeConfig = await getRuntimeConfig();

        const config = {
          // Supabase Configuration
          SUPABASE_URL: runtimeConfig.VITE_SUPABASE_URL,
          SUPABASE_ANON_KEY: runtimeConfig.VITE_SUPABASE_ANON_KEY,

          // API Configuration
          API_BASE_URL: runtimeConfig.VITE_API_URL,

          // WebSocket Configuration
          WS_BASE_URL: runtimeConfig.VITE_WS_URL,

          // WhatsApp Configuration
          WHATSAPP_INSTANCE_NAME: runtimeConfig.VITE_WHATSAPP_INSTANCE_NAME || 'hormonia-instance',

          // AI Services Configuration
          OPENAI_API_KEY: runtimeConfig.VITE_OPENAI_API_KEY,
          LANGCHAIN_API_KEY: runtimeConfig.VITE_LANGCHAIN_API_KEY,
          GEMINI_API_KEY: runtimeConfig.VITE_GEMINI_API_KEY,

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
          SESSION_TIMEOUT: parseInt(runtimeConfig.VITE_SESSION_TIMEOUT || '3600000', 10),
          TOKEN_REFRESH_THRESHOLD: parseInt(runtimeConfig.VITE_TOKEN_REFRESH_THRESHOLD || '300000', 10),

          // File upload settings
          maxFileSize: parseInt(runtimeConfig.VITE_MAX_FILE_SIZE || '10485760', 10),
          allowedFileTypes: runtimeConfig.VITE_SUPPORTED_FILE_TYPES?.split(',') || ['image/jpeg', 'image/png', 'image/gif', 'application/pdf']
        };

        // Validate required configuration
        if (!config.API_BASE_URL) {
          throw new Error('API URL is required. Check your environment configuration.');
        }

        // Supabase is optional (only required if using Supabase features)
        if (!config.SUPABASE_URL) {
          logger.warn('Supabase URL not configured. Supabase features will be disabled.');
        }
        if (!config.SUPABASE_ANON_KEY) {
          logger.warn('Supabase Anon Key not configured. Supabase features will be disabled.');
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

/**
 * Gets configuration synchronously (if already loaded)
 * Returns null if configuration hasn't been loaded yet
 */
export function getConfigSync() {
  return syncConfig || getRuntimeConfigSync();
}

// Backward compatibility exports - these will work once config is loaded
export let SUPABASE_URL = '';
export let SUPABASE_ANON_KEY = '';
export let API_BASE_URL = '';
export let WS_BASE_URL = '';
export let WHATSAPP_INSTANCE_NAME = '';
export let OPENAI_API_KEY = '';
export let LANGCHAIN_API_KEY = '';
export let GEMINI_API_KEY = '';
export let SENTRY_DSN = '';
export let ANALYTICS_TRACKING_ID = '';
export let ENVIRONMENT = '';
export let DEBUG_MODE = false;
export let SESSION_TIMEOUT = 3600000;
export let TOKEN_REFRESH_THRESHOLD = 300000;

// Update exports when config is loaded
loadConfig().then(config => {
  // Only update if different to avoid circular assignments
  if (config.SUPABASE_URL !== SUPABASE_URL) SUPABASE_URL = config.SUPABASE_URL;
  if (config.SUPABASE_ANON_KEY !== SUPABASE_ANON_KEY) SUPABASE_ANON_KEY = config.SUPABASE_ANON_KEY;
  if (config.API_BASE_URL !== API_BASE_URL) API_BASE_URL = config.API_BASE_URL;
  if (config.WS_BASE_URL !== WS_BASE_URL) WS_BASE_URL = config.WS_BASE_URL;
}).catch(error => {
  logger.error('Failed to initialize configuration:', error);
});

// Static fallback values from environment
const STATIC_WHATSAPP_INSTANCE_NAME = import.meta.env['VITE_WHATSAPP_INSTANCE_NAME'] || 'hormonia-instance';
const STATIC_OPENAI_API_KEY = import.meta.env['VITE_OPENAI_API_KEY'];
const STATIC_LANGCHAIN_API_KEY = import.meta.env['VITE_LANGCHAIN_API_KEY'];
const STATIC_GEMINI_API_KEY = import.meta.env['VITE_GEMINI_API_KEY'];
const STATIC_SENTRY_DSN = import.meta.env['VITE_SENTRY_DSN'];
const STATIC_ANALYTICS_TRACKING_ID = import.meta.env['VITE_ANALYTICS_TRACKING_ID'];
const STATIC_ENVIRONMENT = import.meta.env['VITE_ENVIRONMENT'] || 'development';
const STATIC_DEBUG_MODE = import.meta.env['VITE_DEBUG_MODE'] === 'true';
const STATIC_SESSION_TIMEOUT = parseInt(import.meta.env['VITE_SESSION_TIMEOUT'] || '3600000', 10);
const STATIC_TOKEN_REFRESH_THRESHOLD = parseInt(import.meta.env['VITE_TOKEN_REFRESH_THRESHOLD'] || '300000', 10);

// AI Feature Flag Statics
const STATIC_AI_CHAT_ENABLED = import.meta.env['VITE_AI_CHAT_ENABLED'] === 'true' || import.meta.env['VITE_AI_CHAT_ENABLED'] === undefined;
const STATIC_AI_ANALYTICS_ENABLED = import.meta.env['VITE_AI_ANALYTICS_ENABLED'] === 'true' || import.meta.env['VITE_AI_ANALYTICS_ENABLED'] === undefined;
const STATIC_AI_INSIGHTS_ENABLED = import.meta.env['VITE_AI_INSIGHTS_ENABLED'] === 'true' || import.meta.env['VITE_AI_INSIGHTS_ENABLED'] === undefined;
const STATIC_AI_RECOMMENDATIONS_ENABLED = import.meta.env['VITE_AI_RECOMMENDATIONS_ENABLED'] === 'true' || import.meta.env['VITE_AI_RECOMMENDATIONS_ENABLED'] === undefined;

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

  // File upload settings (from env vars)
  maxFileSize: parseInt(import.meta.env['VITE_MAX_FILE_SIZE'] || '10485760', 10),
  allowedFileTypes: import.meta.env['VITE_SUPPORTED_FILE_TYPES']?.split(',') || ['image/jpeg', 'image/png', 'image/gif', 'application/pdf'],

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
 * Environment Variables:
 * - VITE_AI_CHAT_ENABLED: 'true' | 'false' (default: true if API keys present)
 * - VITE_AI_ANALYTICS_ENABLED: 'true' | 'false' (default: true)
 * - VITE_AI_INSIGHTS_ENABLED: 'true' | 'false' (default: true)
 * - VITE_AI_RECOMMENDATIONS_ENABLED: 'true' | 'false' (default: true)
 * - VITE_OPENAI_API_KEY: OpenAI API key for AI features
 * - VITE_GEMINI_API_KEY: Google Gemini API key for AI features
 * - VITE_LANGCHAIN_API_KEY: LangChain API key for advanced AI workflows
 */
export const FEATURES = {
  // AI Features - Controlled by feature flags and API key availability
  AI_CHAT: STATIC_AI_CHAT_ENABLED && (!!STATIC_OPENAI_API_KEY || !!STATIC_GEMINI_API_KEY || STATIC_ENVIRONMENT === 'development'),
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
  hasOpenAI: !!STATIC_OPENAI_API_KEY,
  hasGemini: !!STATIC_GEMINI_API_KEY,
  hasLangChain: !!STATIC_LANGCHAIN_API_KEY,
  chatEnabled: FEATURES.AI_CHAT,
  analyticsEnabled: FEATURES.AI_ANALYTICS,
  insightsEnabled: FEATURES.AI_INSIGHTS,
  recommendationsEnabled: FEATURES.AI_RECOMMENDATIONS,
  preferredProvider: STATIC_GEMINI_API_KEY ? 'gemini' : STATIC_OPENAI_API_KEY ? 'openai' : 'mock'
});
