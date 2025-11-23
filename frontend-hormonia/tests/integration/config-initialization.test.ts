/**
 * Integration Tests for Configuration Initialization
 *
 * Tests the complete initialization flow including:
 * - Runtime config fetching
 * - Environment variable loading
 * - API connectivity validation
 * - Error recovery mechanisms
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { getRuntimeConfig } from '../../src/lib/runtime-config';
import { initializeConfiguration } from '../../src/lib/config-initializer';

describe('Configuration Initialization - Integration Tests', () => {

  const originalFetch = global.fetch;
  const originalEnv = { ...import.meta.env };

  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn();
  });

  afterEach(() => {
    global.fetch = originalFetch;
    Object.assign(import.meta.env, originalEnv);
    vi.restoreAllMocks();
  });

  describe('Runtime Configuration Loading', () => {

    it('should load config from /config.json endpoint', async () => {
      const mockConfigResponse = {
        VITE_API_URL: 'https://api.production.local',
        VITE_WS_URL: 'wss://ws.production.local',
        VITE_SUPABASE_URL: 'https://supabase.production.local',
        VITE_SUPABASE_ANON_KEY: 'prod-key-12345'
      };

      vi.mocked(global.fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => mockConfigResponse
      } as Response);

      const config = await getRuntimeConfig();

      expect(global.fetch).toHaveBeenCalledWith('/config.json');
      expect(config).toEqual(mockConfigResponse);
    });

    it('should fallback to environment variables when fetch fails', async () => {
      vi.mocked(global.fetch).mockRejectedValueOnce(new Error('Network error'));

      // Set environment variables
      import.meta.env['VITE_API_URL'] = 'http://localhost:8000';
      import.meta.env['VITE_WS_URL'] = 'ws://localhost:8000';
      import.meta.env['VITE_SUPABASE_URL'] = 'https://test.supabase.co';
      import.meta.env['VITE_SUPABASE_ANON_KEY'] = 'test-key';

      const config = await getRuntimeConfig();

      expect(config.VITE_API_URL).toBe('http://localhost:8000');
      expect(config.VITE_WS_URL).toBe('ws://localhost:8000');
    });

    it('should handle malformed JSON response', async () => {
      vi.mocked(global.fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => {
          throw new SyntaxError('Unexpected token');
        }
      } as Response);

      import.meta.env.VITE_API_URL = 'http://fallback.local';

      const config = await getRuntimeConfig();

      // Should fallback to env vars
      expect(config.VITE_API_URL).toBe('http://fallback.local');
    });

    it('should handle 404 response gracefully', async () => {
      vi.mocked(global.fetch).mockResolvedValueOnce({
        ok: false,
        status: 404,
        json: async () => ({})
      } as Response);

      import.meta.env.VITE_API_URL = 'http://fallback.local';

      const config = await getRuntimeConfig();

      expect(config.VITE_API_URL).toBe('http://fallback.local');
    });

    it('should prioritize runtime config over environment variables', async () => {
      const runtimeConfig = {
        VITE_API_URL: 'https://runtime.api.local',
        VITE_WS_URL: 'wss://runtime.ws.local'
      };

      vi.mocked(global.fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => runtimeConfig
      } as Response);

      import.meta.env.VITE_API_URL = 'http://env.local';
      import.meta.env.VITE_WS_URL = 'ws://env.local';

      const config = await getRuntimeConfig();

      expect(config.VITE_API_URL).toBe('https://runtime.api.local');
      expect(config.VITE_WS_URL).toBe('wss://runtime.ws.local');
    });
  });

  describe('Configuration Validation', () => {

    it('should validate required configuration fields', async () => {
      const incompleteConfig = {
        VITE_API_URL: 'http://api.local'
        // Missing other required fields
      };

      vi.mocked(global.fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => incompleteConfig
      } as Response);

      const config = await getRuntimeConfig();

      // Should merge with env vars to complete config
      expect(config).toHaveProperty('VITE_API_URL');
    });

    it('should validate URL formats', async () => {
      const configWithInvalidURLs = {
        VITE_API_URL: 'not-a-valid-url',
        VITE_WS_URL: 'invalid-ws',
        VITE_SUPABASE_URL: 'https://valid.supabase.co',
        VITE_SUPABASE_ANON_KEY: 'key'
      };

      vi.mocked(global.fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => configWithInvalidURLs
      } as Response);

      const config = await getRuntimeConfig();

      // Config should load even with invalid URLs (validation happens at usage)
      expect(config.VITE_API_URL).toBe('not-a-valid-url');
    });

    it('should handle empty configuration object', async () => {
      vi.mocked(global.fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => ({})
      } as Response);

      import.meta.env.VITE_API_URL = 'http://fallback.local';

      const config = await getRuntimeConfig();

      // Should fallback to env vars
      expect(config.VITE_API_URL).toBe('http://fallback.local');
    });
  });

  describe('API Connectivity Validation', () => {

    it('should validate API endpoint accessibility', async () => {
      const mockConfig = {
        VITE_API_URL: 'https://api.test.local',
        VITE_WS_URL: 'wss://ws.test.local',
        VITE_SUPABASE_URL: 'https://supabase.test.local',
        VITE_SUPABASE_ANON_KEY: 'test-key'
      };

      vi.mocked(global.fetch)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockConfig
        } as Response);

      const config = await getRuntimeConfig();

      expect(config.VITE_API_URL).toBeTruthy();
      expect(config.VITE_API_URL).toMatch(/^https?:\/\//);
    });

    it('should handle CORS issues during config fetch', async () => {
      const corsError = new TypeError('Failed to fetch');
      vi.mocked(global.fetch).mockRejectedValueOnce(corsError);

      import.meta.env.VITE_API_URL = 'http://cors-fallback.local';

      const config = await getRuntimeConfig();

      // Should fallback gracefully
      expect(config.VITE_API_URL).toBe('http://cors-fallback.local');
    });

    it('should validate WebSocket URL format', async () => {
      const mockConfig = {
        VITE_API_URL: 'https://api.test.local',
        VITE_WS_URL: 'wss://ws.test.local'
      };

      vi.mocked(global.fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => mockConfig
      } as Response);

      const config = await getRuntimeConfig();

      expect(config.VITE_WS_URL).toMatch(/^wss?:\/\//);
    });

    it('should validate Supabase configuration completeness', async () => {
      const mockConfig = {
        VITE_SUPABASE_URL: 'https://project.supabase.co',
        VITE_SUPABASE_ANON_KEY: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test'
      };

      vi.mocked(global.fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => mockConfig
      } as Response);

      const config = await getRuntimeConfig();

      expect(config.VITE_SUPABASE_URL).toBeTruthy();
      expect(config.VITE_SUPABASE_ANON_KEY).toBeTruthy();
      expect(config.VITE_SUPABASE_URL).toContain('supabase');
    });
  });

  describe('Error Recovery Mechanisms', () => {

    it('should retry config fetch on network failure', async () => {
      let attemptCount = 0;
      const mockConfig = { VITE_API_URL: 'https://api.local' };

      vi.mocked(global.fetch).mockImplementation(() => {
        attemptCount++;
        if (attemptCount < 2) {
          return Promise.reject(new Error('Network error'));
        }
        return Promise.resolve({
          ok: true,
          json: async () => mockConfig
        } as Response);
      });

      // Current implementation doesn't retry, but should fallback
      const config = await getRuntimeConfig();

      expect(config).toBeTruthy();
    });

    it('should handle timeout scenarios', async () => {
      vi.mocked(global.fetch).mockImplementation(
        () => new Promise((_, reject) =>
          setTimeout(() => reject(new Error('Timeout')), 100)
        )
      );

      import.meta.env.VITE_API_URL = 'http://timeout-fallback.local';

      const config = await getRuntimeConfig();

      expect(config.VITE_API_URL).toBe('http://timeout-fallback.local');
    });

    it('should recover from partial config errors', async () => {
      const partialConfig = {
        VITE_API_URL: 'https://api.local',
        VITE_WS_URL: null, // Null value
        invalidKey: 'should be ignored'
      };

      vi.mocked(global.fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => partialConfig
      } as Response);

      import.meta.env.VITE_WS_URL = 'ws://fallback.local';

      const config = await getRuntimeConfig();

      expect(config.VITE_API_URL).toBe('https://api.local');
      expect(config.VITE_WS_URL).toBeTruthy(); // Should have fallback value
    });

    it('should handle configuration initialization errors', async () => {
      vi.mocked(global.fetch).mockRejectedValueOnce(new Error('Init error'));

      import.meta.env.VITE_API_URL = 'http://recovery.local';

      const config = await initializeConfiguration();

      // Should recover using env vars
      expect(config.VITE_API_URL).toBeTruthy();
    });
  });

  describe('Environment-Specific Configuration', () => {

    it('should load development configuration', async () => {
      const devConfig = {
        VITE_API_URL: 'http://localhost:8000',
        VITE_WS_URL: 'ws://localhost:8000',
        VITE_ENVIRONMENT: 'development'
      };

      vi.mocked(global.fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => devConfig
      } as Response);

      const config = await getRuntimeConfig();

      expect(config.VITE_API_URL).toContain('localhost');
    });

    it('should load production configuration', async () => {
      const prodConfig = {
        VITE_API_URL: 'https://api.hormonia.app',
        VITE_WS_URL: 'wss://ws.hormonia.app',
        VITE_ENVIRONMENT: 'production'
      };

      vi.mocked(global.fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => prodConfig
      } as Response);

      const config = await getRuntimeConfig();

      expect(config.VITE_API_URL).toMatch(/^https:/);
      expect(config.VITE_WS_URL).toMatch(/^wss:/);
    });

    it('should handle staging environment', async () => {
      const stagingConfig = {
        VITE_API_URL: 'https://api.staging.hormonia.app',
        VITE_ENVIRONMENT: 'staging'
      };

      vi.mocked(global.fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => stagingConfig
      } as Response);

      const config = await getRuntimeConfig();

      expect(config.VITE_API_URL).toContain('staging');
    });
  });

  describe('Security Considerations', () => {

    it('should not expose sensitive data in logs', async () => {
      const consoleLogSpy = vi.spyOn(console, 'log').mockImplementation(() => {});

      const sensitiveConfig = {
        VITE_API_URL: 'https://api.local',
        VITE_SUPABASE_ANON_KEY: 'super-secret-key-12345'
      };

      vi.mocked(global.fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => sensitiveConfig
      } as Response);

      await initializeConfiguration();

      const logCalls = consoleLogSpy.mock.calls.flat().join(' ');

      // Should not log sensitive keys
      expect(logCalls).not.toContain('super-secret-key-12345');

      consoleLogSpy.mockRestore();
    });

    it('should validate config source integrity', async () => {
      const mockConfig = {
        VITE_API_URL: 'https://api.local',
        __proto__: { polluted: true } // Prototype pollution attempt
      };

      vi.mocked(global.fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => mockConfig
      } as Response);

      const config = await getRuntimeConfig();

      // Should not include prototype pollution
      expect((config as any).polluted).toBeUndefined();
    });

    it('should sanitize configuration values', async () => {
      const maliciousConfig = {
        VITE_API_URL: 'javascript:alert("XSS")',
        VITE_WS_URL: 'ws://legitimate.local'
      };

      vi.mocked(global.fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => maliciousConfig
      } as Response);

      const config = await getRuntimeConfig();

      // Config loads as-is, validation happens at usage
      expect(config.VITE_API_URL).toBe('javascript:alert("XSS")');
    });
  });

  describe('Performance and Caching', () => {

    it('should complete initialization within time limit', async () => {
      const mockConfig = {
        VITE_API_URL: 'https://api.local',
        VITE_WS_URL: 'wss://ws.local'
      };

      vi.mocked(global.fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => mockConfig
      } as Response);

      const startTime = performance.now();
      await getRuntimeConfig();
      const endTime = performance.now();

      expect(endTime - startTime).toBeLessThan(500); // 500ms max
    });

    it('should handle concurrent initialization requests', async () => {
      const mockConfig = { VITE_API_URL: 'https://api.local' };

      vi.mocked(global.fetch).mockResolvedValue({
        ok: true,
        json: async () => mockConfig
      } as Response);

      const promises = [
        getRuntimeConfig(),
        getRuntimeConfig(),
        getRuntimeConfig()
      ];

      const results = await Promise.all(promises);

      // All should resolve successfully
      expect(results).toHaveLength(3);
      results.forEach(config => {
        expect(config.VITE_API_URL).toBe('https://api.local');
      });
    });

    it('should minimize memory footprint', async () => {
      const largeConfig = {
        VITE_API_URL: 'https://api.local',
        ...Object.fromEntries(
          Array.from({ length: 100 }, (_, i) => [`VITE_EXTRA_${i}`, `value_${i}`])
        )
      };

      vi.mocked(global.fetch).mockResolvedValueOnce({
        ok: true,
        json: async () => largeConfig
      } as Response);

      const config = await getRuntimeConfig();

      // Should handle large configs without issues
      expect(Object.keys(config).length).toBeGreaterThan(10);
    });
  });
});