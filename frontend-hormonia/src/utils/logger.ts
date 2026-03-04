/**
 * Production-Safe Logger Utility
 *
 * QUALITY FIX #7: Replace console.log with environment-aware logger
 *
 * This logger:
 * - Automatically disables in production
 * - Provides structured logging
 * - Supports log levels (debug, info, warn, error)
 * - Can send errors to monitoring services (Sentry)
 * - Maintains same API as console for easy migration
 *
 * Usage:
 *   import { logger } from '@/utils/logger';
 *
 *   logger.debug('Debug message', { data: 'value' });
 *   logger.info('Info message');
 *   logger.warn('Warning message');
 *   logger.error('Error message', error);
 */
/* eslint-disable no-console */

type LogLevel = 'debug' | 'info' | 'warn' | 'error'

// Sentry global type
interface SentryGlobal {
  captureException: (error: Error, context?: { extra?: Record<string, unknown> }) => void
  captureMessage: (
    message: string,
    context?: { level?: string; extra?: Record<string, unknown> }
  ) => void
}

interface LoggerConfig {
  enabled: boolean
  minLevel: LogLevel
  sendToSentry: boolean
  prefix?: string
}

class Logger {
  private config: LoggerConfig
  private readonly logLevels: Record<LogLevel, number> = {
    debug: 0,
    info: 1,
    warn: 2,
    error: 3,
  }

  constructor(config?: Partial<LoggerConfig>) {
    const isDevelopment = import.meta.env.MODE === 'development' || import.meta.env.DEV === true

    this.config = {
      enabled: isDevelopment,
      minLevel: isDevelopment ? 'debug' : 'error',
      sendToSentry: !isDevelopment,
      prefix: '',
      ...config,
    }
  }

  /**
   * Check if log level should be logged
   */
  private shouldLog(level: LogLevel): boolean {
    if (!this.config.enabled) {
      return false
    }

    const currentLevelValue = this.logLevels[level]
    const minLevelValue = this.logLevels[this.config.minLevel]

    return currentLevelValue >= minLevelValue
  }

  /**
   * Format log message with timestamp and prefix
   */
  private formatMessage(level: LogLevel, message: string): string {
    const timestamp = new Date().toISOString()
    const prefix = this.config.prefix ? `[${this.config.prefix}]` : ''
    const levelStr = level.toUpperCase().padEnd(5)

    return `${timestamp} ${levelStr} ${prefix} ${message}`
  }

  /**
   * Send error to Sentry (if configured)
   */
  private sendToSentry(error: Error | string, context?: Record<string, unknown>): void {
    if (!this.config.sendToSentry) {
      return
    }

    // Check if Sentry is available
    if (typeof window !== 'undefined' && (window as Window & { Sentry?: SentryGlobal }).Sentry) {
      const Sentry = (window as Window & { Sentry?: SentryGlobal }).Sentry

      if (Sentry) {
        if (error instanceof Error) {
          Sentry.captureException(error, {
            extra: context,
          })
        } else {
          Sentry.captureMessage(error, {
            level: 'error',
            extra: context,
          })
        }
      }
    }
  }

  /**
   * Debug level logging (only in development)
   */
  debug(message: string, ...args: unknown[]): void {
    if (this.shouldLog('debug')) {
      console.debug(this.formatMessage('debug', message), ...args)
    }
  }

  /**
   * Info level logging
   */
  info(message: string, ...args: unknown[]): void {
    if (this.shouldLog('info')) {
      console.info(this.formatMessage('info', message), ...args)
    }
  }

  /**
   * Warning level logging
   */
  warn(message: string, ...args: unknown[]): void {
    if (this.shouldLog('warn')) {
      console.warn(this.formatMessage('warn', message), ...args)
    }
  }

  /**
   * Error level logging (always logged, sent to Sentry in production)
   */
  error(message: string, error?: Error | unknown, context?: Record<string, unknown>): void {
    if (this.shouldLog('error')) {
      console.error(this.formatMessage('error', message), error, context)
    }

    // Send to Sentry in production
    if (error instanceof Error) {
      this.sendToSentry(error, { message, ...context })
    } else if (error) {
      this.sendToSentry(new Error(message), { originalError: error, ...context })
    }
  }

  /**
   * Create child logger with prefix
   */
  child(prefix: string): Logger {
    return new Logger({
      ...this.config,
      prefix: this.config.prefix ? `${this.config.prefix}:${prefix}` : prefix,
    })
  }

  /**
   * Group logs (for component lifecycle, etc.)
   */
  group(label: string, collapsed: boolean = false): void {
    if (this.shouldLog('debug')) {
      if (collapsed) {
        console.groupCollapsed(this.formatMessage('debug', label))
      } else {
        console.group(this.formatMessage('debug', label))
      }
    }
  }

  /**
   * End log group
   */
  groupEnd(): void {
    if (this.shouldLog('debug')) {
      console.groupEnd()
    }
  }

  /**
   * Log table (for arrays/objects)
   */
  table(data: unknown): void {
    if (this.shouldLog('debug')) {
      console.table(data)
    }
  }

  /**
   * Start performance timer
   */
  time(label: string): void {
    if (this.shouldLog('debug')) {
      console.time(label)
    }
  }

  /**
   * End performance timer
   */
  timeEnd(label: string): void {
    if (this.shouldLog('debug')) {
      console.timeEnd(label)
    }
  }

  /**
   * Assert condition
   */
  assert(condition: boolean, message: string): void {
    if (this.shouldLog('error')) {
      console.assert(condition, this.formatMessage('error', message))
    }

    if (!condition) {
      this.sendToSentry(new Error(`Assertion failed: ${message}`))
    }
  }
}

// Export singleton instance
export const logger = new Logger()

// Export class for custom instances
export { Logger }

// Export type for configuration
export type { LoggerConfig, LogLevel }

// Convenience exports for common patterns
export const createLogger = (prefix: string): Logger => {
  return logger.child(prefix)
}

// Development-only logger (never logs in production)
export const devLogger = new Logger({
  enabled: import.meta.env.MODE === 'development',
  minLevel: 'debug',
  sendToSentry: false,
})

// Production-only logger (only errors in production)
export const prodLogger = new Logger({
  enabled: true,
  minLevel: 'error',
  sendToSentry: true,
})
