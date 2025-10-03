/**
 * Mock Configuration
 * Centralized configuration for mock mode
 */

/**
 * Check if mock auth is enabled
 */
export function isMockAuthEnabled(): boolean {
  return import.meta.env['VITE_USE_MOCK_AUTH'] === 'true'
}

/**
 * Check if mock API is enabled
 */
export function isMockApiEnabled(): boolean {
  return import.meta.env['VITE_USE_MOCK_API'] === 'true'
}

/**
 * Check if in development mode
 */
export function isDevMode(): boolean {
  return import.meta.env.DEV === true
}

/**
 * Get mock configuration
 */
export function getMockConfig() {
  return {
    auth: {
      enabled: isMockAuthEnabled(),
      showCredentials: isDevMode(),
      defaultPassword: 'senha123'
    },
    api: {
      enabled: isMockApiEnabled(),
      minDelay: 200,
      maxDelay: 600,
      errorRate: 0.05
    },
    ui: {
      showBanner: isDevMode(),
      bannerText: 'Modo de Desenvolvimento - Dados Mock',
      bannerColor: 'orange'
    }
  }
}

export default {
  isMockAuthEnabled,
  isMockApiEnabled,
  isDevMode,
  getMockConfig
}
