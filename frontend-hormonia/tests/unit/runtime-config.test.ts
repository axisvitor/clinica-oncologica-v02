/**
 * Runtime Configuration Tests
 *
 * Tests for the runtime configuration system that ensures environment variables
 * work correctly in Railway deployment scenarios.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
  getRuntimeConfig,
  getRuntimeConfigSync,
  refreshRuntimeConfig,
  getConfigValue,
  isProduction,
  PRODUCTION_FALLBACK_CONFIG
} from '../runtime-config';

// Mock global objects
const mockWindow = {
  location: {
    hostname: 'localhost'
  }
} as any;

const mockImportMeta = {
  env: {
    MODE: 'development',
    PROD: false,
    VITE_SUPABASE_URL: 'http://localhost:8000/supabase',
    VITE_SUPABASE_ANON_KEY: 'test-anon-key',
    VITE_API_URL: 'http://localhost:8000/api/v2'
  }
} as any;

describe('Runtime Configuration', () => {
  beforeEach(() => {
    // Reset global state
    (global as any).window = mockWindow;
    vi.stubGlobal('import', { meta: mockImportMeta });

    // Clear any cached config
    refreshRuntimeConfig();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    delete (global as any).window;
    delete (global as any).__ENV_CONFIG__;
    delete (global as any).__RUNTIME_CONFIG__;
  });

  describe('Production Detection', () => {
    it('should detect development mode correctly', () => {
      expect(isProduction()).toBe(false);
    });

    it('should detect production mode from environment', () => {
      mockImportMeta.env.MODE = 'production';
      mockImportMeta.env.PROD = true;
      expect(isProduction()).toBe(true);
    });

    it('should detect Railway production from hostname', () => {
      mockWindow.location.hostname = 'app.up.railway.app';
      expect(isProduction()).toBe(true);
    });
  });

  describe('Configuration Loading - Development', () => {
    it('should load development configuration from import.meta.env', async () => {
      const config = await getRuntimeConfig();

      expect(config.VITE_SUPABASE_URL).toBe('http://localhost:8000/supabase');
      expect(config.VITE_SUPABASE_ANON_KEY).toBe('test-anon-key');
      expect(config.VITE_API_URL).toBe('http://localhost:8000/api/v2');
    });

    it('should provide development fallbacks', async () => {
      mockImportMeta.env = {}; // Empty environment

      const config = await getRuntimeConfig();

      expect(config.VITE_API_URL).toBe('http://127.0.0.1:8000/api/v2');
      expect(config.VITE_WS_URL).toBe('ws://127.0.0.1:8000/ws');
    });
  });

  describe('Configuration Loading - Production', () => {
    beforeEach(() => {
      mockImportMeta.env.MODE = 'production';
      mockImportMeta.env.PROD = true;
      mockWindow.location.hostname = 'app.up.railway.app';
    });

    it('should load production configuration from window.__ENV_CONFIG__', async () => {
      (global as any).window.__ENV_CONFIG__ = {
        VITE_SUPABASE_URL: 'https://prod.supabase.co',
        VITE_SUPABASE_ANON_KEY: 'prod-anon-key',
        VITE_API_URL: 'https://api.production.com/api/v2'
      };

      const config = await getRuntimeConfig();

      expect(config.VITE_SUPABASE_URL).toBe('https://prod.supabase.co');
      expect(config.VITE_SUPABASE_ANON_KEY).toBe('prod-anon-key');
      expect(config.VITE_API_URL).toBe('https://api.production.com/api/v2');
    });

    it('should fall back to production defaults when no runtime config available', async () => {
      mockImportMeta.env = {}; // Empty environment

      const config = await getRuntimeConfig();

      expect(config.VITE_SUPABASE_URL).toBe(PRODUCTION_FALLBACK_CONFIG.VITE_SUPABASE_URL);
      expect(config.VITE_SUPABASE_ANON_KEY).toBe(PRODUCTION_FALLBACK_CONFIG.VITE_SUPABASE_ANON_KEY);
      expect(config.VITE_API_URL).toBe(PRODUCTION_FALLBACK_CONFIG.VITE_API_URL);
    });

    it('should handle runtime API endpoint loading', async () => {
      // Mock fetch for runtime API
      global.fetch = vi.fn().mockImplementation(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({
            VITE_SUPABASE_URL: 'https://api.supabase.co',
            VITE_SUPABASE_ANON_KEY: 'api-anon-key',
            VITE_API_URL: 'https://api.railway.app/api/v2'
          })
        })
      );

      const config = await getRuntimeConfig();

      expect(fetch).toHaveBeenCalledWith('/api/config', expect.any(Object));
      expect(config.VITE_SUPABASE_URL).toBe('https://api.supabase.co');
      expect(config.VITE_API_URL).toBe('https://api.railway.app/api/v2');
    });

    it('should handle fetch API failures gracefully', async () => {
      global.fetch = vi.fn().mockImplementation(() =>
        Promise.reject(new Error('Network error'))
      );

      const config = await getRuntimeConfig();

      // Should fall back to production config
      expect(config.VITE_SUPABASE_URL).toBe(PRODUCTION_FALLBACK_CONFIG.VITE_SUPABASE_URL);
    });
  });

  describe('Synchronous Configuration Access', () => {
    it('should return null when config not loaded yet', () => {
      const config = getRuntimeConfigSync();
      expect(config).toBeNull();
    });

    it('should return config after async loading', async () => {
      await getRuntimeConfig();
      const config = getRuntimeConfigSync();
      expect(config).not.toBeNull();
      expect(config?.VITE_SUPABASE_URL).toBeDefined();
    });
  });

  describe('Configuration Value Access', () => {
    it('should get specific config value with fallback', async () => {
      const value = await getConfigValue('VITE_SUPABASE_URL', 'fallback-url');
      expect(value).toBe('http://localhost:8000/supabase');
    });

    it('should return fallback when key not found', async () => {
      const value = await getConfigValue('VITE_NONEXISTENT_KEY' as any, 'fallback-value');
      expect(value).toBe('fallback-value');
    });
  });

  describe('Configuration Validation', () => {
    it('should validate required configuration fields', async () => {
      const config = await getRuntimeConfig();

      // Required fields should be present
      expect(config.VITE_SUPABASE_URL).toBeTruthy();
      expect(config.VITE_SUPABASE_ANON_KEY).toBeTruthy();
      expect(config.VITE_API_URL || config.VITE_API_BASE_URL).toBeTruthy();
    });

    it('should handle missing required fields in production', async () => {
      mockImportMeta.env.MODE = 'production';
      mockImportMeta.env.PROD = true;
      mockWindow.location.hostname = 'app.up.railway.app';

      // Set empty config
      (global as any).window.__ENV_CONFIG__ = {
        VITE_SUPABASE_URL: '',
        VITE_SUPABASE_ANON_KEY: '',
        VITE_API_URL: ''
      };

      const config = await getRuntimeConfig();

      // Should fall back to production defaults
      expect(config.VITE_SUPABASE_URL).toBe(PRODUCTION_FALLBACK_CONFIG.VITE_SUPABASE_URL);
    });
  });

  describe('Configuration Refresh', () => {
    it('should allow configuration refresh', async () => {
      // Load initial config
      const config1 = await getRuntimeConfig();
      expect(config1.VITE_API_URL).toBe('http://localhost:8000/api/v2');

      // Change environment and refresh
      mockImportMeta.env.VITE_API_URL = 'http://localhost:9000/api/v2';
      const config2 = await refreshRuntimeConfig();
      expect(config2.VITE_API_URL).toBe('http://localhost:9000/api/v2');
    });
  });

  describe('Railway Integration', () => {
    beforeEach(() => {
      mockImportMeta.env.MODE = 'production';
      mockImportMeta.env.PROD = true;
      mockWindow.location.hostname = 'frontend-production.up.railway.app';
    });

    it('should load Railway environment variables correctly', async () => {
      (global as any).window.__RUNTIME_CONFIG__ = {
        loadConfig: vi.fn().mockResolvedValue({
          VITE_SUPABASE_URL: 'https://railway.supabase.co',
          VITE_SUPABASE_ANON_KEY: 'railway-anon-key',
          VITE_API_URL: 'https://backend-production.up.railway.app/api/v2',
          VITE_WS_URL: 'wss://backend-production.up.railway.app/ws'
        })
      };

      const config = await getRuntimeConfig();

      expect(config.VITE_SUPABASE_URL).toBe('https://railway.supabase.co');
      expect(config.VITE_API_URL).toBe('https://backend-production.up.railway.app/api/v2');
      expect(config.VITE_WS_URL).toBe('wss://backend-production.up.railway.app/ws');
    });

    it('should handle Railway configuration loading errors', async () => {
      (global as any).window.__RUNTIME_CONFIG__ = {
        loadConfig: vi.fn().mockRejectedValue(new Error('Railway config error'))
      };

      const config = await getRuntimeConfig();

      // Should fall back to production defaults
      expect(config.VITE_SUPABASE_URL).toBe(PRODUCTION_FALLBACK_CONFIG.VITE_SUPABASE_URL);
    });
  });

  describe('Edge Cases', () => {
    it('should handle undefined window object', async () => {
      delete (global as any).window;

      const config = await getRuntimeConfig();

      // Should still work with development fallbacks
      expect(config).toBeDefined();
      expect(config.VITE_API_URL).toBeDefined();
    });

    it('should handle malformed runtime config', async () => {
      mockImportMeta.env.MODE = 'production';
      (global as any).window.__ENV_CONFIG__ = null;

      const config = await getRuntimeConfig();

      // Should fall back to production defaults
      expect(config.VITE_SUPABASE_URL).toBe(PRODUCTION_FALLBACK_CONFIG.VITE_SUPABASE_URL);
    });

    it('should handle concurrent configuration loading', async () => {
      // Start multiple configuration loads simultaneously
      const [config1, config2, config3] = await Promise.all([
        getRuntimeConfig(),
        getRuntimeConfig(),
        getRuntimeConfig()
      ]);

      // All should return the same configuration
      expect(config1).toEqual(config2);
      expect(config2).toEqual(config3);
    });
  });
});