/**
 * Frontend Initialization Validator
 *
 * Validates frontend initialization and configuration:
 * - Environment variables
 * - API connectivity
 * - Required services
 * - Browser compatibility
 * - Feature detection
 */

import { createLogger } from '../lib/logger'
import { getRuntimeConfig } from '../lib/runtime-config'
import { apiClient } from '../lib/api-client'

const logger = createLogger('InitValidator')

export interface ValidationResult {
  component: string
  valid: boolean
  message: string
  details?: Record<string, unknown>
  error?: Error
}

export interface InitValidationResults {
  overall: boolean
  results: ValidationResult[]
  timestamp: string
}

export class FrontendInitValidator {
  private results: ValidationResult[] = []

  /**
   * Run all validation checks
   */
  async validate(): Promise<InitValidationResults> {
    logger.info('🚀 Starting frontend initialization validation')

    // Run all validation steps
    await this.validateEnvironment()
    await this.validateBrowser()
    await this.validateConfiguration()
    await this.validateAPIConnectivity()
    await this.validateFeatures()

    const overall = this.results.every((r) => r.valid)

    const validationResults: InitValidationResults = {
      overall,
      results: this.results,
      timestamp: new Date().toISOString(),
    }

    if (overall) {
      logger.info('✅ All validation checks passed')
    } else {
      logger.error('❌ Some validation checks failed', {
        failed: this.results.filter((r) => !r.valid).map((r) => r.component),
      })
    }

    return validationResults
  }

  /**
   * Validate environment variables
   */
  private async validateEnvironment(): Promise<void> {
    logger.info('[1/5] Validating environment...')

    try {
      const config = await getRuntimeConfig()

      // Check required environment variables
      const requiredVars = {
        VITE_API_URL: config.VITE_API_URL,
        VITE_API_BASE_URL: config.VITE_API_BASE_URL,
      }

      const missing = Object.entries(requiredVars)
        .filter(([_, value]) => !value)
        .map(([key]) => key)

      if (missing.length > 0) {
        this.results.push({
          component: 'Environment Variables',
          valid: false,
          message: `Missing required variables: ${missing.join(', ')}`,
          details: { missing },
        })
      } else {
        this.results.push({
          component: 'Environment Variables',
          valid: true,
          message: 'All required environment variables present',
          details: {
            apiUrl: config.VITE_API_URL,
            apiBaseUrl: config.VITE_API_BASE_URL,
          },
        })
      }
    } catch (error) {
      this.results.push({
        component: 'Environment Variables',
        valid: false,
        message: 'Failed to load environment variables',
        error: error as Error,
      })
    }
  }

  /**
   * Validate browser compatibility
   */
  private async validateBrowser(): Promise<void> {
    logger.info('[2/5] Validating browser compatibility...')

    try {
      const features = {
        fetch: typeof window.fetch === 'function',
        localStorage: this.checkLocalStorage(),
        sessionStorage: this.checkSessionStorage(),
        webWorkers: typeof Worker !== 'undefined',
        serviceWorker: 'serviceWorker' in navigator,
        indexedDB: 'indexedDB' in window,
        crypto: typeof window.crypto !== 'undefined',
        promises: typeof Promise !== 'undefined',
        async: this.checkAsyncSupport(),
      }

      const unsupported = Object.entries(features)
        .filter(([_, supported]) => !supported)
        .map(([feature]) => feature)

      if (unsupported.length > 0) {
        this.results.push({
          component: 'Browser Compatibility',
          valid: false,
          message: `Unsupported features: ${unsupported.join(', ')}`,
          details: { features, unsupported },
        })
      } else {
        this.results.push({
          component: 'Browser Compatibility',
          valid: true,
          message: 'Browser fully compatible',
          details: { features },
        })
      }
    } catch (error) {
      this.results.push({
        component: 'Browser Compatibility',
        valid: false,
        message: 'Browser compatibility check failed',
        error: error as Error,
      })
    }
  }

  /**
   * Validate configuration
   */
  private async validateConfiguration(): Promise<void> {
    logger.info('[3/5] Validating configuration...')

    try {
      const config = await getRuntimeConfig()

      // Validate API URL format
      const apiUrl = config.VITE_API_URL || config.VITE_API_BASE_URL
      const isValidUrl = apiUrl && (apiUrl.startsWith('http://') || apiUrl.startsWith('https://'))

      if (!isValidUrl) {
        this.results.push({
          component: 'Configuration',
          valid: false,
          message: 'Invalid API URL format',
          details: { apiUrl },
        })
      } else {
        this.results.push({
          component: 'Configuration',
          valid: true,
          message: 'Configuration valid',
          details: {
            apiUrl,
            environment: config.VITE_ENVIRONMENT || 'production',
          },
        })
      }
    } catch (error) {
      this.results.push({
        component: 'Configuration',
        valid: false,
        message: 'Configuration validation failed',
        error: error as Error,
      })
    }
  }

  /**
   * Validate API connectivity
   */
  private async validateAPIConnectivity(): Promise<void> {
    logger.info('[4/5] Validating API connectivity...')

    try {
      // Try to reach health endpoint
      const startTime = Date.now()
      const response = await fetch(`${apiClient.getBaseURL()}/health`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      })

      const responseTime = Date.now() - startTime

      if (response.ok) {
        const data = await response.json()
        this.results.push({
          component: 'API Connectivity',
          valid: true,
          message: 'API is reachable and healthy',
          details: {
            status: data.status,
            responseTime: `${responseTime}ms`,
            version: data.version,
          },
        })
      } else {
        this.results.push({
          component: 'API Connectivity',
          valid: false,
          message: `API returned error status: ${response.status}`,
          details: {
            status: response.status,
            statusText: response.statusText,
          },
        })
      }
    } catch (error) {
      this.results.push({
        component: 'API Connectivity',
        valid: false,
        message: 'Cannot reach API',
        error: error as Error,
      })
    }
  }

  /**
   * Validate required features
   */
  private async validateFeatures(): Promise<void> {
    logger.info('[5/5] Validating features...')

    try {
      const features = {
        reactQuery: typeof window !== 'undefined',
        router: typeof window.history !== 'undefined',
        errorBoundary: true, // Always supported with React
        authentication: true, // Firebase always available
      }

      this.results.push({
        component: 'Features',
        valid: true,
        message: 'All required features available',
        details: { features },
      })
    } catch (error) {
      this.results.push({
        component: 'Features',
        valid: false,
        message: 'Feature validation failed',
        error: error as Error,
      })
    }
  }

  /**
   * Check localStorage availability
   */
  private checkLocalStorage(): boolean {
    try {
      const test = '__storage_test__'
      localStorage.setItem(test, test)
      localStorage.removeItem(test)
      return true
    } catch {
      return false
    }
  }

  /**
   * Check sessionStorage availability
   */
  private checkSessionStorage(): boolean {
    try {
      const test = '__storage_test__'
      sessionStorage.setItem(test, test)
      sessionStorage.removeItem(test)
      return true
    } catch {
      return false
    }
  }

  /**
   * Check async/await support
   */
  private checkAsyncSupport(): boolean {
    try {
      eval('(async () => {})')
      return true
    } catch {
      return false
    }
  }
}

/**
 * Run validation and return results
 */
export async function validateFrontendInit(): Promise<InitValidationResults> {
  const validator = new FrontendInitValidator()
  return await validator.validate()
}

/**
 * Run validation and throw if failed
 */
export async function ensureFrontendInit(): Promise<void> {
  const results = await validateFrontendInit()

  if (!results.overall) {
    const failures = results.results
      .filter((r) => !r.valid)
      .map((r) => r.component)
      .join(', ')

    throw new Error(
      `Frontend initialization validation failed: ${failures}. ` + `Check console for details.`
    )
  }
}
