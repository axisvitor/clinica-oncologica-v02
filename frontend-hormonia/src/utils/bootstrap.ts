/**
 * Frontend Bootstrap Utility
 *
 * Handles frontend application bootstrapping:
 * - Initialize configuration
 * - Setup monitoring
 * - Configure error handling
 * - Initialize services
 * - Validate environment
 */

import { createLogger } from '../lib/logger'
import { initializeConfiguration } from '../lib/config-initializer'
import { validateFrontendInit } from './init-validator'

const logger = createLogger('Bootstrap')

export interface BootstrapOptions {
  validateOnStartup?: boolean
  enableMonitoring?: boolean
  enableErrorTracking?: boolean
  logLevel?: 'debug' | 'info' | 'warn' | 'error'
}

export interface BootstrapResult {
  success: boolean
  message: string
  duration: number
  timestamp: string
}

export class FrontendBootstrap {
  private options: Required<BootstrapOptions>
  private startTime: number

  constructor(options: BootstrapOptions = {}) {
    this.options = {
      validateOnStartup: options.validateOnStartup ?? true,
      enableMonitoring: options.enableMonitoring ?? true,
      enableErrorTracking: options.enableErrorTracking ?? true,
      logLevel: options.logLevel ?? 'info',
    }
    this.startTime = Date.now()
  }

  /**
   * Bootstrap the application
   */
  async bootstrap(): Promise<BootstrapResult> {
    logger.info('🚀 Starting frontend bootstrap')

    try {
      // Step 1: Initialize configuration
      await this.initializeConfig()

      // Step 2: Setup monitoring (if enabled)
      if (this.options.enableMonitoring) {
        await this.setupMonitoring()
      }

      // Step 3: Configure error tracking (if enabled)
      if (this.options.enableErrorTracking) {
        await this.setupErrorTracking()
      }

      // Step 4: Validate environment (if enabled)
      if (this.options.validateOnStartup) {
        await this.validateEnvironment()
      }

      // Step 5: Initialize services
      await this.initializeServices()

      const duration = Date.now() - this.startTime

      logger.info(`✅ Bootstrap completed successfully in ${duration}ms`)

      return {
        success: true,
        message: 'Bootstrap completed successfully',
        duration,
        timestamp: new Date().toISOString(),
      }
    } catch (error) {
      const duration = Date.now() - this.startTime
      const message = error instanceof Error ? error.message : 'Unknown error'

      logger.error('❌ Bootstrap failed', { error, duration })

      return {
        success: false,
        message: `Bootstrap failed: ${message}`,
        duration,
        timestamp: new Date().toISOString(),
      }
    }
  }

  /**
   * Initialize configuration
   */
  private async initializeConfig(): Promise<void> {
    logger.info('[1/5] Initializing configuration...')

    try {
      await initializeConfiguration()
      logger.info('✓ Configuration initialized')
    } catch (error) {
      logger.error('✗ Configuration initialization failed', error)
      throw new Error('Failed to initialize configuration')
    }
  }

  /**
   * Setup monitoring
   */
  private async setupMonitoring(): Promise<void> {
    logger.info('[2/5] Setting up monitoring...')

    try {
      if (typeof window !== 'undefined' && 'performance' in window) {
        const navigation = performance.getEntriesByType('navigation')[0]
        logger.debug('Navigation metrics', navigation)
      }

      logger.info('✓ Monitoring configured')
    } catch (error) {
      logger.warn('⚠ Monitoring setup failed (non-critical)', error)
    }
  }

  /**
   * Setup error tracking
   */
  private async setupErrorTracking(): Promise<void> {
    logger.info('[3/5] Setting up error tracking...')

    try {
      // Initialize Sentry (lazy load to avoid import errors)
      await import('../monitoring/sentry')
      // SentryMonitoring.init() is called automatically on module import

      // Setup global error handlers
      window.addEventListener('error', (event) => {
        logger.error('Uncaught error', {
          message: event.message,
          filename: event.filename,
          lineno: event.lineno,
          colno: event.colno,
        })
      })

      window.addEventListener('unhandledrejection', (event) => {
        logger.error('Unhandled promise rejection', {
          reason: event.reason,
        })
      })

      logger.info('✓ Error tracking configured')
    } catch (error) {
      logger.warn('⚠ Error tracking setup failed (non-critical)', error)
    }
  }

  /**
   * Validate environment
   */
  private async validateEnvironment(): Promise<void> {
    logger.info('[4/5] Validating environment...')

    try {
      const results = await validateFrontendInit()

      if (!results.overall) {
        const failures = results.results
          .filter((r) => !r.valid)
          .map((r) => `${r.component}: ${r.message}`)

        logger.warn('⚠ Validation warnings:', { failures })

        // Only fail on critical issues
        const criticalFailures = results.results.filter(
          (r) => !r.valid && ['Environment Variables', 'Configuration'].includes(r.component)
        )

        if (criticalFailures.length > 0) {
          throw new Error('Critical validation failures detected')
        }
      } else {
        logger.info('✓ Environment validation passed')
      }
    } catch (error) {
      logger.error('✗ Environment validation failed', error)
      throw error
    }
  }

  /**
   * Initialize services
   */
  private async initializeServices(): Promise<void> {
    logger.info('[5/5] Initializing services...')

    try {
      // Service initialization happens through React components
      // This is a placeholder for any global service initialization

      logger.info('✓ Services initialized')
    } catch (error) {
      logger.error('✗ Service initialization failed', error)
      throw error
    }
  }
}

/**
 * Bootstrap the application with default options
 */
export async function bootstrapApp(options?: BootstrapOptions): Promise<BootstrapResult> {
  const bootstrap = new FrontendBootstrap(options)
  return await bootstrap.bootstrap()
}

/**
 * Bootstrap the application and throw on failure
 */
export async function ensureBootstrap(options?: BootstrapOptions): Promise<void> {
  const result = await bootstrapApp(options)

  if (!result.success) {
    throw new Error(result.message)
  }
}
