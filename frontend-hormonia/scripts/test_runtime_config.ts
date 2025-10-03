/**
 * Runtime Config Testing Script
 * Tests config.ts runtime loading and environment variable handling
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { getRuntimeConfig } from '../src/config';

// Mock environment variables for testing
const mockEnv = {
  VITE_API_URL: 'http://localhost:8000',
  VITE_SUPABASE_URL: 'https://test-project.supabase.co',
  VITE_SUPABASE_ANON_KEY: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test-key',
  VITE_WEBSOCKET_URL: 'ws://localhost:8000/ws',
  VITE_ENVIRONMENT: 'test'
};

// Mock window.APP_CONFIG for runtime testing
const mockWindowConfig = {
  API_URL: 'http://window-api.localhost:8000',
  SUPABASE_URL: 'https://window-project.supabase.co',
  SUPABASE_ANON_KEY: 'window-anon-key',
  WEBSOCKET_URL: 'ws://window-ws.localhost:8000/ws'
};

describe('Runtime Config Tests', () => {
  let originalImportMetaEnv: any;
  let originalWindow: any;

  beforeEach(() => {
    // Store original values
    originalImportMetaEnv = (global as any).import?.meta?.env;
    originalWindow = (global as any).window;

    // Setup mock environment
    (global as any).import = {
      meta: {
        env: mockEnv
      }
    };
  });

  afterEach(() => {
    // Restore original values
    if (originalImportMetaEnv) {
      (global as any).import.meta.env = originalImportMetaEnv;
    }
    if (originalWindow) {
      (global as any).window = originalWindow;
    }
  });

  describe('Environment Variable Loading', () => {
    it('should load API_URL from environment', () => {
      const config = getRuntimeConfig();
      expect(config.API_URL).toBe(mockEnv.VITE_API_URL);
    });

    it('should load Supabase configuration', () => {
      const config = getRuntimeConfig();
      expect(config.SUPABASE.URL).toBe(mockEnv.VITE_SUPABASE_URL);
      expect(config.SUPABASE.ANON_KEY).toBe(mockEnv.VITE_SUPABASE_ANON_KEY);
    });

    it('should load WebSocket URL', () => {
      const config = getRuntimeConfig();
      expect(config.WEBSOCKET_URL).toBe(mockEnv.VITE_WEBSOCKET_URL);
    });

    it('should handle missing environment variables with defaults', () => {
      // Test with empty environment
      (global as any).import.meta.env = {};

      const config = getRuntimeConfig();

      // Should have default values
      expect(config.API_URL).toBeTruthy();
      expect(config.SUPABASE.URL).toBeTruthy();
      expect(config.SUPABASE.ANON_KEY).toBeTruthy();
    });
  });

  describe('Window APP_CONFIG Priority', () => {
    it('should prioritize window.APP_CONFIG over environment variables', () => {
      // Setup window.APP_CONFIG
      (global as any).window = {
        APP_CONFIG: mockWindowConfig
      };

      const config = getRuntimeConfig();

      // Should use window config values
      expect(config.API_URL).toBe(mockWindowConfig.API_URL);
      expect(config.SUPABASE.URL).toBe(mockWindowConfig.SUPABASE_URL);
      expect(config.SUPABASE.ANON_KEY).toBe(mockWindowConfig.SUPABASE_ANON_KEY);
      expect(config.WEBSOCKET_URL).toBe(mockWindowConfig.WEBSOCKET_URL);
    });

    it('should fallback to environment when window.APP_CONFIG is partial', () => {
      // Setup partial window config
      (global as any).window = {
        APP_CONFIG: {
          API_URL: mockWindowConfig.API_URL
          // Missing other config values
        }
      };

      const config = getRuntimeConfig();

      // Should use window config for API_URL
      expect(config.API_URL).toBe(mockWindowConfig.API_URL);

      // Should fallback to env for missing values
      expect(config.SUPABASE.URL).toBe(mockEnv.VITE_SUPABASE_URL);
      expect(config.SUPABASE.ANON_KEY).toBe(mockEnv.VITE_SUPABASE_ANON_KEY);
      expect(config.WEBSOCKET_URL).toBe(mockEnv.VITE_WEBSOCKET_URL);
    });
  });

  describe('Configuration Structure', () => {
    it('should have proper API configuration structure', () => {
      const config = getRuntimeConfig();

      expect(config).toHaveProperty('API_URL');
      expect(typeof config.API_URL).toBe('string');
      expect(config.API_URL).toMatch(/^https?:\/\//);
    });

    it('should have proper Supabase configuration structure', () => {
      const config = getRuntimeConfig();

      expect(config).toHaveProperty('SUPABASE');
      expect(config.SUPABASE).toHaveProperty('URL');
      expect(config.SUPABASE).toHaveProperty('ANON_KEY');
      expect(typeof config.SUPABASE.URL).toBe('string');
      expect(typeof config.SUPABASE.ANON_KEY).toBe('string');
    });

    it('should have proper WebSocket configuration', () => {
      const config = getRuntimeConfig();

      expect(config).toHaveProperty('WEBSOCKET_URL');
      expect(typeof config.WEBSOCKET_URL).toBe('string');
      expect(config.WEBSOCKET_URL).toMatch(/^wss?:\/\//);
    });
  });

  describe('URL Validation', () => {
    it('should validate API URLs are properly formatted', () => {
      const config = getRuntimeConfig();

      expect(config.API_URL).toMatch(/^https?:\/\/[^\s/$.?#].[^\s]*$/);
    });

    it('should validate Supabase URLs', () => {
      const config = getRuntimeConfig();

      expect(config.SUPABASE.URL).toMatch(/^https:\/\/.*\.supabase\.co$|^http:\/\/localhost/);
    });

    it('should validate WebSocket URLs', () => {
      const config = getRuntimeConfig();

      expect(config.WEBSOCKET_URL).toMatch(/^wss?:\/\/[^\s/$.?#].[^\s]*$/);
    });
  });

  describe('Environment-specific Configuration', () => {
    it('should handle development environment', () => {
      (global as any).import.meta.env = {
        ...mockEnv,
        VITE_ENVIRONMENT: 'development',
        DEV: true
      };

      const config = getRuntimeConfig();

      // Should allow localhost URLs in development
      expect(config.API_URL).toMatch(/localhost|127\.0\.0\.1/);
    });

    it('should handle production environment', () => {
      (global as any).import.meta.env = {
        ...mockEnv,
        VITE_ENVIRONMENT: 'production',
        PROD: true,
        VITE_API_URL: 'https://api.production.com',
        VITE_SUPABASE_URL: 'https://prod-project.supabase.co'
      };

      const config = getRuntimeConfig();

      // Should use HTTPS in production
      expect(config.API_URL).toMatch(/^https:\/\//);
      expect(config.SUPABASE.URL).toMatch(/^https:\/\//);
    });
  });

  describe('Error Handling', () => {
    it('should handle undefined import.meta.env gracefully', () => {
      (global as any).import = undefined;

      expect(() => getRuntimeConfig()).not.toThrow();

      const config = getRuntimeConfig();
      expect(config).toBeTruthy();
      expect(config.API_URL).toBeTruthy();
    });

    it('should handle missing window object', () => {
      (global as any).window = undefined;

      expect(() => getRuntimeConfig()).not.toThrow();

      const config = getRuntimeConfig();
      expect(config.API_URL).toBe(mockEnv.VITE_API_URL);
    });

    it('should provide fallback values for all required config', () => {
      // Clear all environment
      (global as any).import = { meta: { env: {} } };
      (global as any).window = undefined;

      const config = getRuntimeConfig();

      // Should have fallback values
      expect(config.API_URL).toBeTruthy();
      expect(config.SUPABASE.URL).toBeTruthy();
      expect(config.SUPABASE.ANON_KEY).toBeTruthy();
      expect(config.WEBSOCKET_URL).toBeTruthy();
    });
  });
});

// Integration test function for manual testing
export async function runIntegrationTests() {
  console.log('🧪 Running Runtime Config Integration Tests...\n');

  const tests = [
    {
      name: 'Basic Config Loading',
      test: () => {
        const config = getRuntimeConfig();
        return config && config.API_URL && config.SUPABASE.URL;
      }
    },
    {
      name: 'Environment Variable Access',
      test: () => {
        const hasImportMeta = typeof globalThis !== 'undefined' &&
                            (globalThis as any).import?.meta?.env !== undefined;
        console.log('import.meta.env available:', !!hasImportMeta);
        return true; // Always pass, just for information
      }
    },
    {
      name: 'Window APP_CONFIG Check',
      test: () => {
        const hasWindow = typeof window !== 'undefined';
        const hasAppConfig = hasWindow && (window as any).APP_CONFIG;
        console.log('window.APP_CONFIG available:', !!hasAppConfig);
        return true; // Always pass, just for information
      }
    },
    {
      name: 'URL Format Validation',
      test: () => {
        const config = getRuntimeConfig();
        const apiUrlValid = /^https?:\/\//.test(config.API_URL);
        const supabaseUrlValid = /^https?:\/\//.test(config.SUPABASE.URL);
        const websocketUrlValid = /^wss?:\/\//.test(config.WEBSOCKET_URL);
        return apiUrlValid && supabaseUrlValid && websocketUrlValid;
      }
    }
  ];

  let passed = 0;
  let failed = 0;

  for (const test of tests) {
    try {
      const result = test.test();
      if (result) {
        console.log(`✅ ${test.name}`);
        passed++;
      } else {
        console.log(`❌ ${test.name}`);
        failed++;
      }
    } catch (error) {
      console.log(`❌ ${test.name}: ${(error as Error).message}`);
      failed++;
    }
  }

  console.log(`\n📊 Integration Test Results:`);
  console.log(`✅ Passed: ${passed}`);
  console.log(`❌ Failed: ${failed}`);

  // Display current config for debugging
  try {
    const config = getRuntimeConfig();
    console.log('\n🔧 Current Runtime Config:');
    console.log(JSON.stringify(config, null, 2));
  } catch (error) {
    console.log('\n❌ Failed to load runtime config:', (error as Error).message);
  }

  return failed === 0;
}

// Run integration tests if called directly
if (typeof require !== 'undefined' && require.main === module) {
  runIntegrationTests().then(success => {
    process.exit(success ? 0 : 1);
  });
}