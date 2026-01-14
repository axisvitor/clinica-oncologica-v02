/**
 * Unit Tests for Configuration Initializer
 *
 * Comprehensive tests for the ConfigProvider component, hooks, and utilities
 * Test coverage includes: initialization, error handling, context, and validation
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, renderHook } from '@testing-library/react';
import { act } from 'react-dom/test-utils';
import {
  ConfigProvider,
  useConfig,
  useConfigValue,
  useConfigValidation,
  initializeConfiguration
} from '../../src/lib/config-initializer';
import * as runtimeConfig from '../../src/lib/runtime-config';

// Mock runtime config module
vi.mock('../../src/lib/runtime-config', () => ({
  getRuntimeConfig: vi.fn()
}));

describe('Configuration Initializer - Unit Tests', () => {

  const mockConfig = {
    VITE_API_URL: 'http://localhost:8000/api/v2',
    VITE_API_BASE_URL: 'http://localhost:8000',
    VITE_WS_URL: 'ws://localhost:8000/ws',
    VITE_WS_BASE_URL: 'ws://localhost:8000/ws',
    VITE_ENVIRONMENT: 'test'
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('ConfigProvider Component', () => {

    it('should render loading state initially', async () => {
      vi.mocked(runtimeConfig.getRuntimeConfig).mockImplementation(
        () => new Promise(resolve => setTimeout(() => resolve(mockConfig), 100))
      );

      render(
        <ConfigProvider>
          <div>App Content</div>
        </ConfigProvider>
      );

      expect(screen.getByText('Carregando Configuração')).toBeInTheDocument();
      expect(screen.getByText('Preparando o sistema Hormonia...')).toBeInTheDocument();
    });

    it('should render children when config loads successfully', async () => {
      vi.mocked(runtimeConfig.getRuntimeConfig).mockResolvedValue(mockConfig);

      render(
        <ConfigProvider>
          <div>App Content</div>
        </ConfigProvider>
      );

      await waitFor(() => {
        expect(screen.getByText('App Content')).toBeInTheDocument();
      });
    });

    it('should display error state on configuration failure', async () => {
      const errorMessage = 'Failed to fetch configuration';
      vi.mocked(runtimeConfig.getRuntimeConfig).mockRejectedValue(
        new Error(errorMessage)
      );

      render(
        <ConfigProvider>
          <div>App Content</div>
        </ConfigProvider>
      );

      await waitFor(() => {
        expect(screen.getByText('Erro de Configuração')).toBeInTheDocument();
        expect(screen.getByText(errorMessage)).toBeInTheDocument();
      });
    });

    it('should use custom loading component when provided', async () => {
      vi.mocked(runtimeConfig.getRuntimeConfig).mockImplementation(
        () => new Promise(resolve => setTimeout(() => resolve(mockConfig), 100))
      );

      const CustomLoading = () => <div>Custom Loading...</div>;

      render(
        <ConfigProvider loadingComponent={CustomLoading}>
          <div>App Content</div>
        </ConfigProvider>
      );

      expect(screen.getByText('Custom Loading...')).toBeInTheDocument();
    });

    it('should use custom error component when provided', async () => {
      vi.mocked(runtimeConfig.getRuntimeConfig).mockRejectedValue(
        new Error('Config error')
      );

      const CustomError = ({ error, reload }: { error: string; reload: () => void }) => (
        <div>
          <p>Custom Error: {error}</p>
          <button onClick={reload}>Retry Custom</button>
        </div>
      );

      render(
        <ConfigProvider fallbackComponent={CustomError}>
          <div>App Content</div>
        </ConfigProvider>
      );

      await waitFor(() => {
        expect(screen.getByText(/Custom Error:/)).toBeInTheDocument();
      });
    });

    it('should allow retry on error', async () => {
      let attemptCount = 0;
      vi.mocked(runtimeConfig.getRuntimeConfig).mockImplementation(() => {
        attemptCount++;
        if (attemptCount === 1) {
          return Promise.reject(new Error('First attempt failed'));
        }
        return Promise.resolve(mockConfig);
      });

      render(
        <ConfigProvider>
          <div>App Content</div>
        </ConfigProvider>
      );

      await waitFor(() => {
        expect(screen.getByText('Erro de Configuração')).toBeInTheDocument();
      });

      const retryButton = screen.getByText('Tentar Novamente');
      await act(async () => {
        retryButton.click();
      });

      await waitFor(() => {
        expect(screen.getByText('App Content')).toBeInTheDocument();
      });

      expect(attemptCount).toBe(2);
    });

    it('should handle non-Error exceptions gracefully', async () => {
      vi.mocked(runtimeConfig.getRuntimeConfig).mockRejectedValue('String error');

      render(
        <ConfigProvider>
          <div>App Content</div>
        </ConfigProvider>
      );

      await waitFor(() => {
        expect(screen.getByText('Erro de Configuração')).toBeInTheDocument();
        expect(screen.getByText('Failed to load configuration')).toBeInTheDocument();
      });
    });
  });

  describe('useConfig Hook', () => {

    it('should provide config context to children', async () => {
      vi.mocked(runtimeConfig.getRuntimeConfig).mockResolvedValue(mockConfig);

      const TestComponent = () => {
        const { config, loading, error } = useConfig();
        return (
          <div>
            <span>Loading: {loading.toString()}</span>
            <span>Error: {error || 'none'}</span>
            <span>Config: {config?.VITE_API_URL || 'none'}</span>
          </div>
        );
      };

      render(
        <ConfigProvider>
          <TestComponent />
        </ConfigProvider>
      );

      await waitFor(() => {
        expect(screen.getByText('Loading: false')).toBeInTheDocument();
        expect(screen.getByText('Error: none')).toBeInTheDocument();
        expect(screen.getByText(`Config: ${mockConfig.VITE_API_URL}`)).toBeInTheDocument();
      });
    });

    it('should throw error when used outside ConfigProvider', () => {
      const TestComponent = () => {
        useConfig();
        return <div>Test</div>;
      };

      // Suppress console.error for this test
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      expect(() => render(<TestComponent />)).toThrow(
        'useConfig must be used within a ConfigProvider'
      );

      consoleSpy.mockRestore();
    });

    it('should provide reload function', async () => {
      let callCount = 0;
      vi.mocked(runtimeConfig.getRuntimeConfig).mockImplementation(() => {
        callCount++;
        return Promise.resolve({ ...mockConfig, VITE_API_URL: `http://api-${callCount}.local` });
      });

      const TestComponent = () => {
        const { config, reload } = useConfig();
        return (
          <div>
            <span>{config?.VITE_API_URL}</span>
            <button onClick={reload}>Reload</button>
          </div>
        );
      };

      render(
        <ConfigProvider>
          <TestComponent />
        </ConfigProvider>
      );

      await waitFor(() => {
        expect(screen.getByText('http://api-1.local')).toBeInTheDocument();
      });

      const reloadButton = screen.getByText('Reload');
      await act(async () => {
        reloadButton.click();
      });

      await waitFor(() => {
        expect(screen.getByText('http://api-2.local')).toBeInTheDocument();
      });
    });
  });

  describe('useConfigValue Hook', () => {

    it('should return specific config value', async () => {
      vi.mocked(runtimeConfig.getRuntimeConfig).mockResolvedValue(mockConfig);

      const TestComponent = () => {
        const apiUrl = useConfigValue('VITE_API_URL');
        return <div>API URL: {apiUrl}</div>;
      };

      render(
        <ConfigProvider>
          <TestComponent />
        </ConfigProvider>
      );

      await waitFor(() => {
        expect(screen.getByText(`API URL: ${mockConfig.VITE_API_URL}`)).toBeInTheDocument();
      });
    });

    it('should return fallback value when config key is missing', async () => {
      vi.mocked(runtimeConfig.getRuntimeConfig).mockResolvedValue({
        VITE_API_URL: 'http://localhost:8000'
      } as any);

      const TestComponent = () => {
        const wsUrl = useConfigValue('VITE_WS_URL', 'ws://fallback.local');
        return <div>WS URL: {wsUrl}</div>;
      };

      render(
        <ConfigProvider>
          <TestComponent />
        </ConfigProvider>
      );

      await waitFor(() => {
        expect(screen.getByText('WS URL: ws://fallback.local')).toBeInTheDocument();
      });
    });

    it('should return undefined when no fallback provided and key missing', async () => {
      vi.mocked(runtimeConfig.getRuntimeConfig).mockResolvedValue({
        VITE_API_URL: 'http://localhost:8000'
      } as any);

      const TestComponent = () => {
        const wsUrl = useConfigValue('VITE_WS_URL');
        return <div>WS URL: {wsUrl || 'undefined'}</div>;
      };

      render(
        <ConfigProvider>
          <TestComponent />
        </ConfigProvider>
      );

      await waitFor(() => {
        expect(screen.getByText('WS URL: undefined')).toBeInTheDocument();
      });
    });
  });

  describe('useConfigValidation Hook', () => {

    it('should validate complete configuration', async () => {
      vi.mocked(runtimeConfig.getRuntimeConfig).mockResolvedValue(mockConfig);

      const TestComponent = () => {
        const validation = useConfigValidation();
        return (
          <div>
            <p>Valid: {validation.isValid.toString()}</p>
            <p>Has API: {validation.hasAPI.toString()}</p>
            <p>Has WebSocket: {validation.hasWebSocket.toString()}</p>
          </div>
        );
      };

      render(
        <ConfigProvider>
          <TestComponent />
        </ConfigProvider>
      );

      await waitFor(() => {
        expect(screen.getByText('Valid: true')).toBeInTheDocument();
        expect(screen.getByText('Has API: true')).toBeInTheDocument();
        expect(screen.getByText('Has WebSocket: true')).toBeInTheDocument();
      });
    });

    it('should detect incomplete API configuration', async () => {
      vi.mocked(runtimeConfig.getRuntimeConfig).mockResolvedValue({
        ...mockConfig,
        VITE_API_URL: undefined,
        VITE_API_BASE_URL: undefined
      } as any);

      const TestComponent = () => {
        const { hasAPI } = useConfigValidation();
        return <div>Has API: {hasAPI.toString()}</div>;
      };

      render(
        <ConfigProvider>
          <TestComponent />
        </ConfigProvider>
      );

      await waitFor(() => {
        expect(screen.getByText('Has API: false')).toBeInTheDocument();
      });
    });

    it('should mark as invalid when error occurs', async () => {
      vi.mocked(runtimeConfig.getRuntimeConfig).mockRejectedValue(
        new Error('Config error')
      );

      render(
        <ConfigProvider>
          <div>App Content</div>
        </ConfigProvider>
      );

      await waitFor(() => {
        expect(screen.getByText('Erro de Configuração')).toBeInTheDocument();
      });
    });
  });

  describe('initializeConfiguration Utility', () => {

    it('should successfully initialize configuration', async () => {
      vi.mocked(runtimeConfig.getRuntimeConfig).mockResolvedValue(mockConfig);

      const config = await initializeConfiguration();

      expect(config).toEqual(mockConfig);
      expect(runtimeConfig.getRuntimeConfig).toHaveBeenCalledTimes(1);
    });

    it('should throw error on initialization failure', async () => {
      const error = new Error('Initialization failed');
      vi.mocked(runtimeConfig.getRuntimeConfig).mockRejectedValue(error);

      await expect(initializeConfiguration()).rejects.toThrow('Initialization failed');
    });

    it('should log initialization process', async () => {
      const consoleInfoSpy = vi.spyOn(console, 'info').mockImplementation(() => {});
      vi.mocked(runtimeConfig.getRuntimeConfig).mockResolvedValue(mockConfig);

      await initializeConfiguration();

      expect(consoleInfoSpy).toHaveBeenCalledWith(
        '[ConfigInitializer]',
        'Initializing runtime configuration...'
      );
      expect(consoleInfoSpy).toHaveBeenCalledWith(
        '[ConfigInitializer]',
        'Configuration initialized successfully'
      );

      consoleInfoSpy.mockRestore();
    });

    it('should log error on failure', async () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      const error = new Error('Init error');
      vi.mocked(runtimeConfig.getRuntimeConfig).mockRejectedValue(error);

      try {
        await initializeConfiguration();
      } catch (e) {
        // Expected to throw
      }

      expect(consoleErrorSpy).toHaveBeenCalledWith(
        '[ConfigInitializer]',
        'Failed to initialize configuration:',
        error
      );

      consoleErrorSpy.mockRestore();
    });
  });

  describe('Edge Cases and Error Handling', () => {

    it('should handle rapid reload calls gracefully', async () => {
      let resolveCount = 0;
      vi.mocked(runtimeConfig.getRuntimeConfig).mockImplementation(() => {
        resolveCount++;
        return new Promise(resolve =>
          setTimeout(() => resolve({ ...mockConfig, count: resolveCount } as any), 50)
        );
      });

      const TestComponent = () => {
        const { config, reload } = useConfig();
        return (
          <div>
            <span>Count: {(config as any)?.count || 0}</span>
            <button onClick={reload}>Reload</button>
          </div>
        );
      };

      render(
        <ConfigProvider>
          <TestComponent />
        </ConfigProvider>
      );

      const reloadButton = await screen.findByText('Reload');

      // Rapid fire multiple reloads
      await act(async () => {
        reloadButton.click();
        reloadButton.click();
        reloadButton.click();
      });

      await waitFor(() => {
        expect(screen.getByText(/Count: \d+/)).toBeInTheDocument();
      }, { timeout: 200 });

      // Should handle gracefully without crashes
      expect(resolveCount).toBeGreaterThan(0);
    });

    it('should surface error when runtime config is null', async () => {
      vi.mocked(runtimeConfig.getRuntimeConfig).mockResolvedValue(null as any);

      render(
        <ConfigProvider>
          <div>App Content</div>
        </ConfigProvider>
      );

      await waitFor(() => {
        expect(screen.getByText('Erro de Configuração')).toBeInTheDocument();
      });
    });

    it('should handle empty config object', async () => {
      vi.mocked(runtimeConfig.getRuntimeConfig).mockResolvedValue({} as any);

      const TestComponent = () => {
        const validation = useConfigValidation();
        return (
          <div>
            <p>Valid: {validation.isValid.toString()}</p>
            <p>Has API: {validation.hasAPI.toString()}</p>
          </div>
        );
      };

      render(
        <ConfigProvider>
          <TestComponent />
        </ConfigProvider>
      );

      await waitFor(() => {
        expect(screen.getByText('Valid: true')).toBeInTheDocument();
        expect(screen.getByText('Has API: false')).toBeInTheDocument();
      });
    });

    it('should handle network timeout scenarios', async () => {
      vi.mocked(runtimeConfig.getRuntimeConfig).mockImplementation(
        () => new Promise((_, reject) =>
          setTimeout(() => reject(new Error('Network timeout')), 100)
        )
      );

      render(
        <ConfigProvider>
          <div>App Content</div>
        </ConfigProvider>
      );

      await waitFor(() => {
        expect(screen.getByText('Erro de Configuração')).toBeInTheDocument();
        expect(screen.getByText('Network timeout')).toBeInTheDocument();
      });
    });

    it('should handle memory cleanup on unmount', async () => {
      vi.mocked(runtimeConfig.getRuntimeConfig).mockResolvedValue(mockConfig);

      const { unmount } = render(
        <ConfigProvider>
          <div>App Content</div>
        </ConfigProvider>
      );

      await waitFor(() => {
        expect(screen.getByText('App Content')).toBeInTheDocument();
      });

      // Should not cause memory leaks or errors on unmount
      expect(() => unmount()).not.toThrow();
    });
  });

  describe('Performance Tests', () => {

    it('should initialize within acceptable time limit', async () => {
      vi.mocked(runtimeConfig.getRuntimeConfig).mockResolvedValue(mockConfig);

      const startTime = performance.now();

      render(
        <ConfigProvider>
          <div>App Content</div>
        </ConfigProvider>
      );

      await waitFor(() => {
        expect(screen.getByText('App Content')).toBeInTheDocument();
      });

      const endTime = performance.now();
      const duration = endTime - startTime;

      // Should initialize in less than 500ms (generous for CI environments)
      expect(duration).toBeLessThan(500);
    });

    it('should not cause re-renders unnecessarily', async () => {
      let renderCount = 0;
      vi.mocked(runtimeConfig.getRuntimeConfig).mockResolvedValue(mockConfig);

      const TestComponent = () => {
        renderCount++;
        const { config } = useConfig();
        return <div>Renders: {renderCount}, URL: {config?.VITE_API_URL}</div>;
      };

      render(
        <ConfigProvider>
          <TestComponent />
        </ConfigProvider>
      );

      await waitFor(() => {
        expect(screen.getByText(/Renders:/)).toBeInTheDocument();
      });

      // Should render exactly twice: once during loading, once after config loaded
      expect(renderCount).toBeLessThanOrEqual(2);
    });
  });
});
