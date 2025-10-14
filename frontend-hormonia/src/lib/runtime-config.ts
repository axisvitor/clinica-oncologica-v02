/// <reference types="vite/client" />

/**
 * Runtime Configuration Loader for Railway Deployment
 *
 * This module provides runtime configuration loading that doesn't depend on build-time
 * environment variables. It solves the Railway deployment issue where build arguments
 * aren't properly passed to the Vite build process.
 *
 * Features:
 * - Runtime environment variable loading
 * - Fallback to production defaults
 * - Type-safe configuration access
 * - Async configuration initialization
 * - Support for Railway's dynamic environment injection
 */

import { createLogger } from './logger';

const logger = createLogger('RuntimeConfig');

// Environment configuration interface
export interface RuntimeConfig {
  VITE_SUPABASE_URL: string;
  VITE_SUPABASE_ANON_KEY: string;
  VITE_SUPABASE_REALTIME_ENABLED?: string;
  VITE_API_URL: string;
  VITE_API_BASE_URL?: string; // Base URL without /api/v1 suffix
  VITE_WS_URL: string;
  VITE_WS_BASE_URL?: string; // WebSocket base URL (standardized variable)
  VITE_WHATSAPP_INSTANCE_NAME?: string;

  // Firebase Client Configuration
  VITE_FIREBASE_API_KEY?: string;
  VITE_FIREBASE_AUTH_DOMAIN?: string;
  VITE_FIREBASE_PROJECT_ID?: string;
  VITE_FIREBASE_STORAGE_BUCKET?: string;
  VITE_FIREBASE_MESSAGING_SENDER_ID?: string;
  VITE_FIREBASE_APP_ID?: string;
  VITE_FIREBASE_MEASUREMENT_ID?: string;

  // AI Service Configuration
  VITE_OPENAI_API_KEY?: string;
  VITE_LANGCHAIN_API_KEY?: string;
  VITE_GEMINI_API_KEY?: string;

  // AI Feature Flags
  VITE_AI_CHAT_ENABLED?: string;
  VITE_AI_ANALYTICS_ENABLED?: string;
  VITE_AI_INSIGHTS_ENABLED?: string;
  VITE_AI_RECOMMENDATIONS_ENABLED?: string;

  // Monitoring & Analytics
  VITE_SENTRY_DSN?: string;
  VITE_ANALYTICS_TRACKING_ID?: string;

  // Environment Settings
  VITE_ENVIRONMENT?: string;
  VITE_DEBUG_MODE?: string;
  VITE_SESSION_TIMEOUT?: string;
  VITE_TOKEN_REFRESH_THRESHOLD?: string;
  VITE_MAX_FILE_SIZE?: string;
  VITE_SUPPORTED_FILE_TYPES?: string;

  // Evolution and Demo Configuration
  VITE_ENABLE_EVOLUTION?: string;
  VITE_EVOLUTION_API_URL?: string;
  VITE_SHOW_DEMO_CREDENTIALS?: string;
}

// Production fallback configuration
// SECURITY: Supabase credentials MUST be provided via environment variables
// WARNING: Hardcoded URLs removed - configuration MUST be provided via environment
const PRODUCTION_FALLBACK_CONFIG: RuntimeConfig = {
  VITE_SUPABASE_URL: '',
  VITE_SUPABASE_ANON_KEY: '',
  VITE_SUPABASE_REALTIME_ENABLED: 'true',
  VITE_API_URL: '', // MUST be set via environment variable
  VITE_API_BASE_URL: '', // MUST be set via environment variable
  VITE_WS_URL: '', // MUST be set via environment variable
  VITE_WS_BASE_URL: '', // MUST be set via environment variable
  VITE_WHATSAPP_INSTANCE_NAME: 'hormonia-instance',

  // Firebase Client Configuration (must be provided via environment)
  VITE_FIREBASE_API_KEY: '',
  VITE_FIREBASE_AUTH_DOMAIN: '',
  VITE_FIREBASE_PROJECT_ID: '',
  VITE_FIREBASE_STORAGE_BUCKET: '',
  VITE_FIREBASE_MESSAGING_SENDER_ID: '',
  VITE_FIREBASE_APP_ID: '',
  VITE_FIREBASE_MEASUREMENT_ID: '',

  // AI Services - Empty in fallback, should be set via environment
  VITE_OPENAI_API_KEY: '',
  VITE_LANGCHAIN_API_KEY: '',
  VITE_GEMINI_API_KEY: '',

  // AI Feature Flags - Enabled by default in production
  VITE_AI_CHAT_ENABLED: 'true',
  VITE_AI_ANALYTICS_ENABLED: 'true',
  VITE_AI_INSIGHTS_ENABLED: 'true',
  VITE_AI_RECOMMENDATIONS_ENABLED: 'true',

  // Environment Settings
  VITE_ENVIRONMENT: 'production',
  VITE_DEBUG_MODE: 'false',
  VITE_SESSION_TIMEOUT: '3600000',
  VITE_TOKEN_REFRESH_THRESHOLD: '300000',
  VITE_MAX_FILE_SIZE: '10485760',
  VITE_SUPPORTED_FILE_TYPES: 'image/jpeg,image/png,image/gif,application/pdf',

  // Evolution and Demo Configuration
  VITE_ENABLE_EVOLUTION: 'false',
  VITE_EVOLUTION_API_URL: '',
  VITE_SHOW_DEMO_CREDENTIALS: 'false'
};

// Runtime configuration state
let runtimeConfig: RuntimeConfig | null = null;
let configPromise: Promise<RuntimeConfig> | null = null;

/**
 * Detects if we're running in production mode
 */
function isProductionMode(): boolean {
  // Check various production indicators
  return (
    import.meta.env.MODE === 'production' ||
    import.meta.env.PROD === true ||
    (typeof window !== 'undefined' && window.location.hostname.includes('railway.app')) ||
    (typeof window !== 'undefined' && window.location.hostname.includes('up.railway.app'))
  );
}

/**
 * Loads configuration from Railway's runtime environment
 * Falls back to build-time env vars, then to production defaults
 */
async function loadRuntimeConfiguration(): Promise<RuntimeConfig> {
  // Return cached config if available
  if (runtimeConfig) {
    return runtimeConfig;
  }

  const isProduction = isProductionMode();
  if (!isProduction) {
    logger.log('Loading configuration, production mode:', isProduction);
  }

  // In development, use Vite's import.meta.env directly
  if (!isProduction) {
    const apiBaseUrl = import.meta.env['VITE_API_BASE_URL'] || 'http://localhost:8000';
    const apiUrl = import.meta.env['VITE_API_URL'] || `${apiBaseUrl}/api/v1`;
    const wsBaseUrl = import.meta.env['VITE_WS_BASE_URL'] || import.meta.env['VITE_WS_URL'] || 'ws://localhost:8000/ws';

    const devConfig: RuntimeConfig = {
      VITE_SUPABASE_URL: import.meta.env['VITE_SUPABASE_URL'] || '',
      VITE_SUPABASE_ANON_KEY: import.meta.env['VITE_SUPABASE_ANON_KEY'] || '',
      ...(import.meta.env['VITE_SUPABASE_REALTIME_ENABLED'] && { VITE_SUPABASE_REALTIME_ENABLED: import.meta.env['VITE_SUPABASE_REALTIME_ENABLED'] }),
      VITE_API_URL: apiUrl,
      ...(apiBaseUrl && { VITE_API_BASE_URL: apiBaseUrl }),
      VITE_WS_URL: wsBaseUrl,
      ...(wsBaseUrl && { VITE_WS_BASE_URL: wsBaseUrl }),
      ...(import.meta.env['VITE_WHATSAPP_INSTANCE_NAME'] && { VITE_WHATSAPP_INSTANCE_NAME: import.meta.env['VITE_WHATSAPP_INSTANCE_NAME'] }),

      // Firebase Client Configuration
      ...(import.meta.env['VITE_FIREBASE_API_KEY'] && { VITE_FIREBASE_API_KEY: import.meta.env['VITE_FIREBASE_API_KEY'] }),
      ...(import.meta.env['VITE_FIREBASE_AUTH_DOMAIN'] && { VITE_FIREBASE_AUTH_DOMAIN: import.meta.env['VITE_FIREBASE_AUTH_DOMAIN'] }),
      ...(import.meta.env['VITE_FIREBASE_PROJECT_ID'] && { VITE_FIREBASE_PROJECT_ID: import.meta.env['VITE_FIREBASE_PROJECT_ID'] }),
      ...(import.meta.env['VITE_FIREBASE_STORAGE_BUCKET'] && { VITE_FIREBASE_STORAGE_BUCKET: import.meta.env['VITE_FIREBASE_STORAGE_BUCKET'] }),
      ...(import.meta.env['VITE_FIREBASE_MESSAGING_SENDER_ID'] && { VITE_FIREBASE_MESSAGING_SENDER_ID: import.meta.env['VITE_FIREBASE_MESSAGING_SENDER_ID'] }),
      ...(import.meta.env['VITE_FIREBASE_APP_ID'] && { VITE_FIREBASE_APP_ID: import.meta.env['VITE_FIREBASE_APP_ID'] }),
      ...(import.meta.env['VITE_FIREBASE_MEASUREMENT_ID'] && { VITE_FIREBASE_MEASUREMENT_ID: import.meta.env['VITE_FIREBASE_MEASUREMENT_ID'] }),

      // AI Services - Development defaults
      ...(import.meta.env['VITE_OPENAI_API_KEY'] && { VITE_OPENAI_API_KEY: import.meta.env['VITE_OPENAI_API_KEY'] }),
      ...(import.meta.env['VITE_LANGCHAIN_API_KEY'] && { VITE_LANGCHAIN_API_KEY: import.meta.env['VITE_LANGCHAIN_API_KEY'] }),
      ...(import.meta.env['VITE_GEMINI_API_KEY'] && { VITE_GEMINI_API_KEY: import.meta.env['VITE_GEMINI_API_KEY'] }),

      // AI Feature Flags - Development defaults (enabled if API keys present)
      VITE_AI_CHAT_ENABLED: import.meta.env['VITE_AI_CHAT_ENABLED'] || 'true',
      VITE_AI_ANALYTICS_ENABLED: import.meta.env['VITE_AI_ANALYTICS_ENABLED'] || 'true',
      VITE_AI_INSIGHTS_ENABLED: import.meta.env['VITE_AI_INSIGHTS_ENABLED'] || 'true',
      VITE_AI_RECOMMENDATIONS_ENABLED: import.meta.env['VITE_AI_RECOMMENDATIONS_ENABLED'] || 'true',

      // Monitoring & Analytics
      ...(import.meta.env['VITE_SENTRY_DSN'] && { VITE_SENTRY_DSN: import.meta.env['VITE_SENTRY_DSN'] }),
      ...(import.meta.env['VITE_ANALYTICS_TRACKING_ID'] && { VITE_ANALYTICS_TRACKING_ID: import.meta.env['VITE_ANALYTICS_TRACKING_ID'] }),

      // Environment Settings
      ...(import.meta.env['VITE_ENVIRONMENT'] && { VITE_ENVIRONMENT: import.meta.env['VITE_ENVIRONMENT'] }),
      ...(import.meta.env['VITE_DEBUG_MODE'] && { VITE_DEBUG_MODE: import.meta.env['VITE_DEBUG_MODE'] }),
      ...(import.meta.env['VITE_SESSION_TIMEOUT'] && { VITE_SESSION_TIMEOUT: import.meta.env['VITE_SESSION_TIMEOUT'] }),
      ...(import.meta.env['VITE_TOKEN_REFRESH_THRESHOLD'] && { VITE_TOKEN_REFRESH_THRESHOLD: import.meta.env['VITE_TOKEN_REFRESH_THRESHOLD'] }),
      ...(import.meta.env['VITE_MAX_FILE_SIZE'] && { VITE_MAX_FILE_SIZE: import.meta.env['VITE_MAX_FILE_SIZE'] }),
      ...(import.meta.env['VITE_SUPPORTED_FILE_TYPES'] && { VITE_SUPPORTED_FILE_TYPES: import.meta.env['VITE_SUPPORTED_FILE_TYPES'] }),

      // Evolution and Demo Configuration
      ...(import.meta.env['VITE_ENABLE_EVOLUTION'] && { VITE_ENABLE_EVOLUTION: import.meta.env['VITE_ENABLE_EVOLUTION'] }),
      ...(import.meta.env['VITE_EVOLUTION_API_URL'] && { VITE_EVOLUTION_API_URL: import.meta.env['VITE_EVOLUTION_API_URL'] }),
      ...(import.meta.env['VITE_SHOW_DEMO_CREDENTIALS'] && { VITE_SHOW_DEMO_CREDENTIALS: import.meta.env['VITE_SHOW_DEMO_CREDENTIALS'] })
    };

    runtimeConfig = devConfig;
    return devConfig;
  }

  // Production: Try multiple configuration sources
  const configSources = [
    loadFromRuntimeAPI,
    loadFromWindowConfig,
    loadFromMetaEnv,
    loadFromFallback
  ];

  for (const loadSource of configSources) {
    try {
      const config = await loadSource();
      if (config && isValidConfig(config)) {
        if (!isProduction) {
          logger.log('Successfully loaded from:', loadSource.name);
        }
        runtimeConfig = config;
        return config;
      }
    } catch (error) {
      if (!isProduction) {
        logger.warn(`Failed to load from ${loadSource.name}:`, error);
      }
    }
  }

  // Final fallback
  if (!isProduction) {
    logger.warn('Using production fallback configuration');
  }
  runtimeConfig = PRODUCTION_FALLBACK_CONFIG;
  return PRODUCTION_FALLBACK_CONFIG;
}

/**
 * Attempts to load config from runtime API endpoint
 * DISABLED: /api/config endpoint not accessible from browser in Railway
 * Frontend uses Railway internal domain which is server-to-server only
 */
async function loadFromRuntimeAPI(): Promise<RuntimeConfig | null> {
  // Skip API endpoint loading - not accessible from browser
  // Railway internal URLs (.railway.internal) only work server-to-server
  if (import.meta.env['DEV']) {
    logger.log('Skipping /api/config endpoint (not accessible from browser)');
  }
  return null;
}

/**
 * Attempts to load config from window object (injected by server)
 */
async function loadFromWindowConfig(): Promise<RuntimeConfig | null> {
  // Check if config was injected by server-side rendering or runtime script
  if (typeof window !== 'undefined' && (window as any).RUNTIME_CONFIG) {
    const rawConfig = (window as any).RUNTIME_CONFIG;
    const config = normalizeConfig(rawConfig);
    if (import.meta.env['DEV']) {
      logger.log('Loaded from window.RUNTIME_CONFIG');
    }
    return config;
  }

  if (typeof window !== 'undefined' && (window as any).__ENV_CONFIG__) {
    const rawConfig = (window as any).__ENV_CONFIG__;
    // Ensure WS variable aliases are set
    const config = normalizeConfig(rawConfig);
    if (import.meta.env['DEV']) {
      logger.log('Loaded from window.__ENV_CONFIG__');
    }
    return config;
  }

  // Check if runtime config loader is available
  if (typeof window !== 'undefined' && (window as any).__RUNTIME_CONFIG__) {
    try {
      const rawConfig = await (window as any).__RUNTIME_CONFIG__.loadConfig();
      if (rawConfig) {
        const config = normalizeConfig(rawConfig);
        if (import.meta.env['DEV']) {
          logger.log('Loaded from window.__RUNTIME_CONFIG__');
        }
        return config;
      }
    } catch (error) {
      if (import.meta.env['DEV']) {
        logger.warn('Runtime config loader failed:', error);
      }
    }
  }

  return null;
}

/**
 * Normalizes configuration to ensure both WS and API variable aliases are present
 */
function normalizeConfig(config: any): RuntimeConfig {
  // Ensure WS_BASE_URL and WS_URL are both set (use whichever is available)
  const wsUrl = config.VITE_WS_BASE_URL || config.VITE_WS_URL || '';
  // Ensure API_BASE_URL is set (prefer explicit base, else derive from API_URL)
  const apiBaseUrl = config.VITE_API_BASE_URL || config.VITE_API_URL?.replace(/\/api\/v1$/, '') || '';

  return {
    ...config,
    VITE_WS_URL: wsUrl,
    VITE_WS_BASE_URL: wsUrl,
    VITE_API_BASE_URL: apiBaseUrl
  };
}

/**
 * Attempts to load config from Vite's import.meta.env
 */
async function loadFromMetaEnv(): Promise<RuntimeConfig | null> {
  // Check if any Vite environment variables are available
  const metaEnvConfig: Partial<RuntimeConfig> = {};
  let hasAnyConfig = false;

  Object.keys(PRODUCTION_FALLBACK_CONFIG).forEach(key => {
    const value = import.meta.env[key];
    if (value) {
      (metaEnvConfig as any)[key] = value;
      hasAnyConfig = true;
    }
  });

  if (hasAnyConfig) {
    // Merge with fallback config for missing values
    const config = { ...PRODUCTION_FALLBACK_CONFIG, ...metaEnvConfig };
    if (import.meta.env['DEV']) {
      logger.log('Loaded from import.meta.env with fallbacks');
    }
    return config;
  }

  return null;
}

/**
 * Returns the production fallback configuration
 */
async function loadFromFallback(): Promise<RuntimeConfig> {
  if (import.meta.env['DEV']) {
    logger.log('Using production fallback configuration');
  }
  return PRODUCTION_FALLBACK_CONFIG;
}

/**
 * Validates that a configuration object has required fields
 */
function isValidConfig(config: any): config is RuntimeConfig {
  // In development mode with mock auth, we don't need Supabase credentials
  const isDev = !isProductionMode();
  const useMockAuth = import.meta.env['VITE_USE_MOCK_AUTH'] === 'true' || isDev;

  // Check if Firebase is configured (Firebase-only auth in production)
  const hasFirebase = Boolean(
    import.meta.env['VITE_FIREBASE_API_KEY'] &&
    import.meta.env['VITE_FIREBASE_PROJECT_ID']
  );

  // Required fields depend on environment and auth method
  // Firebase-only production: only needs API URL (Supabase optional)
  // Mock auth: only needs API URL
  // Supabase auth: needs Supabase credentials + API URL
  const requiredFields = useMockAuth || hasFirebase
    ? ['VITE_API_URL'] // Mock auth or Firebase auth only needs API URL
    : ['VITE_SUPABASE_URL', 'VITE_SUPABASE_ANON_KEY', 'VITE_API_URL'];

  const missingFields = requiredFields.filter(field => {
    const hasField = config && typeof config[field] === 'string' && config[field].length > 0;
    if (!hasField && import.meta.env['DEV']) {
      logger.warn(`Missing required field: ${field}`);
    }
    return !hasField;
  });

  // Warn if Supabase is missing but allow Firebase-only configuration
  if (!useMockAuth && !config?.VITE_SUPABASE_URL && hasFirebase) {
    logger.warn('Supabase not configured - using Firebase-only authentication');
  }

  if (missingFields.length > 0) {
    if (import.meta.env['DEV']) {
      logger.warn(`Configuration validation: missing ${missingFields.join(', ')}`);
      // In dev mode with mock auth or Firebase, allow partial config
      if (useMockAuth || hasFirebase) {
        logger.log('Using mock auth or Firebase, allowing configuration without Supabase');
        return true;
      }
    }
    logger.error(`Configuration validation failed. Missing required fields: ${missingFields.join(', ')}`);
    return false;
  }

  return true;
}

/**
 * Gets the runtime configuration (async)
 * This is the main function to use for loading configuration
 */
export async function getRuntimeConfig(): Promise<RuntimeConfig> {
  // Ensure only one configuration loading process happens
  if (!configPromise) {
    configPromise = loadRuntimeConfiguration();
  }

  return configPromise;
}

/**
 * Gets the runtime configuration synchronously (if already loaded)
 * Returns null if configuration hasn't been loaded yet
 */
export function getRuntimeConfigSync(): RuntimeConfig | null {
  return runtimeConfig;
}

/**
 * Forces a refresh of the runtime configuration
 * Useful for testing or when environment might have changed
 */
export async function refreshRuntimeConfig(): Promise<RuntimeConfig> {
  runtimeConfig = null;
  configPromise = null;
  return getRuntimeConfig();
}

/**
 * Gets a specific configuration value with fallback
 */
export async function getConfigValue<K extends keyof RuntimeConfig>(
  key: K,
  fallback?: RuntimeConfig[K]
): Promise<RuntimeConfig[K] | undefined> {
  const config = await getRuntimeConfig();
  return config[key] || fallback;
}

/**
 * Checks if the app is running in production mode
 */
export function isProduction(): boolean {
  return isProductionMode();
}

// Export for debugging and testing
export { PRODUCTION_FALLBACK_CONFIG };
