/**
 * Runtime Configuration Loader
 *
 * This module provides a centralized way to load and manage runtime configuration
 * with proper error handling and fallback mechanisms.
 */

import { createLogger } from './logger';
import { loadConfig, getRuntimeConfigSync } from '../config';

const logger = createLogger('ConfigLoader');

/**
 * Configuration state management
 */
let configLoaded = false;
let configLoadPromise: Promise<void> | null = null;

/**
 * Initialize runtime configuration
 * This should be called early in the app lifecycle
 */
export async function initializeConfig(): Promise<void> {
  if (configLoaded) {
    logger.debug('Configuration already loaded');
    return;
  }

  if (configLoadPromise) {
    logger.debug('Configuration load in progress, waiting...');
    return configLoadPromise;
  }

  configLoadPromise = (async () => {
    try {
      logger.log('Loading runtime configuration...');
      await loadConfig();
      configLoaded = true;
      logger.log('✓ Runtime configuration loaded successfully');
    } catch (error) {
      logger.error('Failed to load runtime configuration:', error);
      // Don't throw - allow app to continue with build-time config
      logger.warn('Continuing with build-time configuration fallback');
    } finally {
      configLoadPromise = null;
    }
  })();

  return configLoadPromise;
}

/**
 * Get configuration value with fallback
 * @param key Configuration key
 * @param fallback Fallback value if not found
 */
export function getConfigValue<T>(key: string, fallback: T): T {
  const config = getRuntimeConfigSync();
  if (config && Object.prototype.hasOwnProperty.call(config, key)) {
    return (config as Record<string, unknown>)[key] as T;
  }
  return fallback;
}

/**
 * Check if configuration is loaded
 */
export function isConfigLoaded(): boolean {
  return configLoaded;
}

/**
 * Wait for configuration to be loaded
 * Use this in components that depend on runtime config
 */
export async function waitForConfig(): Promise<void> {
  if (configLoaded) {
    return;
  }
  await initializeConfig();
}

/**
 * Get API Base URL from configuration
 * This handles all the fallback logic
 */
export function getAPIBaseURL(): string {
  // Try runtime config first
  const config = getRuntimeConfigSync();
  if (config?.VITE_API_BASE_URL) {
    return config.VITE_API_BASE_URL;
  }

  // Fallback to environment variables
  if (import.meta.env['VITE_API_BASE_URL']) {
    return import.meta.env['VITE_API_BASE_URL'];
  }

  // Extract from VITE_API_URL
  if (import.meta.env['VITE_API_URL']) {
    return import.meta.env['VITE_API_URL'].replace(/\/api\/v2$/, '');
  }

  // Auto-detect from window location in production
  if (typeof window !== 'undefined') {
    const { protocol, hostname } = window.location;
    if (hostname !== 'localhost' && hostname !== '127.0.0.1') {
      return `${protocol}//${hostname}`;
    }
  }

  // Development fallback only
  if (import.meta.env.DEV) {
    return import.meta.env.VITE_API_BASE_URL || (import.meta.env.VITE_API_URL || "http://localhost:8000");
  }

  throw new Error("VITE_API_BASE_URL is required in production");
}

/**
 * Get WebSocket URL from configuration
 */
export function getWebSocketURL(): string {
  const config = getRuntimeConfigSync();
  if (config?.VITE_WS_BASE_URL) {
    return config.VITE_WS_BASE_URL;
  }

  const wsUrl = import.meta.env['VITE_WS_BASE_URL'] ||
                import.meta.env['VITE_WS_URL'] ||
                'ws://localhost:8000/ws';

  // Auto-upgrade protocol based on page protocol
  if (typeof window !== 'undefined') {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return wsUrl.replace(/^(ws|wss):/, protocol);
  }

  return wsUrl;
}

/**
 * Validate configuration
 * Returns list of missing required configuration values
 */
export function validateConfiguration(): string[] {
  const missing: string[] = [];
  const config = getRuntimeConfigSync();

  // Check required values
  if (!config?.VITE_API_URL && !getAPIBaseURL()) {
    missing.push('API_URL or API_BASE_URL');
  }

  if (missing.length > 0) {
    logger.warn('Missing required configuration:', missing);
  }

  return missing;
}

/**
 * Export configuration status for debugging
 */
export function getConfigurationStatus(): {
  loaded: boolean;
  sources: {
    runtime: boolean;
    environment: boolean;
    autoDetect: boolean;
  };
  values: {
    apiBaseUrl: string;
    wsUrl: string;
  };
} {
  const config = getRuntimeConfigSync();

  return {
    loaded: configLoaded,
    sources: {
      runtime: !!config,
      environment: !!(import.meta.env['VITE_API_BASE_URL'] || import.meta.env['VITE_API_URL']),
      autoDetect: typeof window !== 'undefined' &&
                  window.location.hostname !== 'localhost' &&
                  window.location.hostname !== '127.0.0.1'
    },
    values: {
      apiBaseUrl: getAPIBaseURL(),
      wsUrl: getWebSocketURL()
    }
  };
}
