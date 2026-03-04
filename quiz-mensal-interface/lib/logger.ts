/**
 * Conditional Logger Utility
 * Only logs in development mode, silent in production
 */

const isDevelopment = process.env.NODE_ENV === 'development'
const isTest = process.env.NODE_ENV === 'test'

type LogLevel = 'debug' | 'info' | 'warn' | 'error'

interface LoggerOptions {
  prefix?: string
  enabled?: boolean
}

class Logger {
  private prefix: string
  private enabled: boolean

  constructor(options: LoggerOptions = {}) {
    this.prefix = options.prefix || '[Quiz]'
    this.enabled = options.enabled ?? (isDevelopment && !isTest)
  }

  private formatMessage(level: LogLevel, message: string): string {
    const timestamp = new Date().toISOString()
    return `${timestamp} ${this.prefix} [${level.toUpperCase()}] ${message}`
  }

  debug(message: string, ...args: unknown[]): void {
    if (this.enabled) {
      console.debug(this.formatMessage('debug', message), ...args)
    }
  }

  info(message: string, ...args: unknown[]): void {
    if (this.enabled) {
      console.info(this.formatMessage('info', message), ...args)
    }
  }

  warn(message: string, ...args: unknown[]): void {
    if (this.enabled) {
      console.warn(this.formatMessage('warn', message), ...args)
    }
  }

  error(message: string, ...args: unknown[]): void {
    // Errors are always logged, even in production
    console.error(this.formatMessage('error', message), ...args)
  }

  /**
   * Log only in development mode
   */
  log(message: string, ...args: unknown[]): void {
    if (this.enabled) {
      console.log(this.formatMessage('info', message), ...args)
    }
  }

  /**
   * Create a child logger with a different prefix
   */
  child(prefix: string): Logger {
    return new Logger({
      prefix: `${this.prefix}${prefix}`,
      enabled: this.enabled,
    })
  }
}

// Default logger instance
export const logger = new Logger()

// Named loggers for different modules
export const apiLogger = new Logger({ prefix: '[API]' })
export const authLogger = new Logger({ prefix: '[Auth]' })
export const quizLogger = new Logger({ prefix: '[Quiz]' })
export const securityLogger = new Logger({ prefix: '[Security]' })
export const storageLogger = new Logger({ prefix: '[Storage]' })

export default logger
