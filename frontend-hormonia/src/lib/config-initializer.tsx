/**
 * Configuration Initializer Component for React App
 *
 * This component ensures that runtime configuration is loaded before the app starts.
 * It provides a loading screen while configuration is being fetched and handles
 * configuration errors gracefully.
 */

import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { getRuntimeConfig, type RuntimeConfig } from './runtime-config';
import { apiClient } from './api-client';
import { createLogger } from './logger';

const logger = createLogger('ConfigInitializer');

// Configuration context
interface ConfigContextType {
  config: RuntimeConfig | null;
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
}

const ConfigContext = createContext<ConfigContextType | null>(null);

// Configuration provider component
interface ConfigProviderProps {
  children: ReactNode;
  fallbackComponent?: React.ComponentType<{ error: string; reload: () => void }>;
  loadingComponent?: React.ComponentType;
}

export function ConfigProvider({
  children,
  fallbackComponent: FallbackComponent,
  loadingComponent: LoadingComponent
}: ConfigProviderProps) {
  const [config, setConfig] = useState<RuntimeConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadConfiguration = async () => {
    try {
      setLoading(true);
      setError(null);

      logger.info('Loading runtime configuration...');

      // Load config directly without timeout race condition
      // getRuntimeConfig already has internal timeout handling
      const runtimeConfig = await getRuntimeConfig();
      logger.info('Configuration loaded successfully');

      // Initialize API client with runtime config
      // Use VITE_API_BASE_URL (without /api/v1) to avoid path duplication
      // If only VITE_API_URL is available, sanitize it by removing /api/v1 suffix
      const FALLBACK_PROD_API = 'http://localhost:8000';
      const apiBaseUrl = runtimeConfig.VITE_API_BASE_URL ||
                         runtimeConfig.VITE_API_URL?.replace(/\/api\/v1$/, '') ||
                         FALLBACK_PROD_API;
      logger.info('Initializing API client with base URL:', apiBaseUrl);
      apiClient.setBaseURL(apiBaseUrl);

      // Fetch CSRF token for session security
      logger.info('Fetching CSRF token...');
      await apiClient.fetchCsrfToken();

      // Supabase removed - using Firebase exclusively
      logger.info('Using Firebase for authentication and backend API for data');

      setConfig(runtimeConfig);
      logger.info('Configuration initialization complete');
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load configuration';
      logger.error('Configuration loading failed:', err);
      setError(errorMessage);
    } finally {
      // CRITICAL: Always set loading to false, no matter what happens
      logger.info('Setting loading state to false');
      setLoading(false);
    }
  };

  useEffect(() => {
    loadConfiguration();
  }, []);

  // Loading state
  if (loading) {
    if (LoadingComponent) {
      return <LoadingComponent />;
    }
    return <DefaultLoadingComponent />;
  }

  // Error state
  if (error) {
    if (FallbackComponent) {
      return <FallbackComponent error={error} reload={loadConfiguration} />;
    }
    return <DefaultErrorComponent error={error} reload={loadConfiguration} />;
  }

  // Success state
  const contextValue: ConfigContextType = {
    config,
    loading,
    error,
    reload: loadConfiguration
  };

  return (
    <ConfigContext.Provider value={contextValue}>
      {children}
    </ConfigContext.Provider>
  );
}

// Hook to access configuration
export function useConfig(): ConfigContextType {
  const context = useContext(ConfigContext);
  if (!context) {
    throw new Error('useConfig must be used within a ConfigProvider');
  }
  return context;
}

// Hook to get configuration values safely
export function useConfigValue<K extends keyof RuntimeConfig>(
  key: K,
  fallback?: RuntimeConfig[K]
): RuntimeConfig[K] | undefined {
  const { config } = useConfig();
  return config?.[key] || fallback;
}

// Default loading component
function DefaultLoadingComponent() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="text-center space-y-4">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
        <div className="space-y-2">
          <h2 className="text-xl font-semibold">Carregando Configuração</h2>
          <p className="text-muted-foreground">
            Preparando o sistema Hormonia...
          </p>
        </div>
      </div>
    </div>
  );
}

// Default error component
interface DefaultErrorComponentProps {
  error: string;
  reload: () => void;
}

function DefaultErrorComponent({ error, reload }: DefaultErrorComponentProps) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="text-center space-y-6 max-w-md mx-auto p-6">
        <div className="text-destructive">
          <svg
            className="h-16 w-16 mx-auto mb-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z"
            />
          </svg>
        </div>

        <div className="space-y-2">
          <h2 className="text-xl font-semibold text-destructive">
            Erro de Configuração
          </h2>
          <p className="text-muted-foreground">
            Não foi possível carregar a configuração do sistema.
          </p>
          <details className="text-sm text-left">
            <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
              Detalhes do erro
            </summary>
            <pre className="mt-2 p-2 bg-muted rounded text-xs overflow-auto">
              {error}
            </pre>
          </details>
        </div>

        <div className="space-y-3">
          <button
            onClick={reload}
            className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 transition-colors"
          >
            Tentar Novamente
          </button>

          <div className="text-xs text-muted-foreground">
            <p>Se o problema persistir:</p>
            <ul className="mt-1 space-y-1">
              <li>• Verifique sua conexão com a internet</li>
              <li>• Recarregue a página (F5)</li>
              <li>• Contate o suporte técnico</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}

// Utility function to initialize config outside of React
export async function initializeConfiguration(): Promise<RuntimeConfig> {
  try {
    logger.info('Initializing runtime configuration...');
    const config = await getRuntimeConfig();
    logger.info('Configuration initialized successfully');
    return config;
  } catch (error) {
    logger.error('Failed to initialize configuration:', error);
    throw error;
  }
}

// Configuration validation hook
export function useConfigValidation() {
  const { config, error } = useConfig();

  return {
    isValid: !!config && !error,
    hasAPI: !!(config?.VITE_API_BASE_URL || config?.VITE_API_URL),
    hasWebSocket: !!(config?.VITE_WS_BASE_URL || config?.VITE_WS_URL),
    config,
    error
  };
}
