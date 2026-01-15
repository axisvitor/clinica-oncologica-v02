/// <reference types="vite/client" />
/* eslint-disable no-console */

/**
 * Development logger utility
 *
 * Provides console logging that only works in development mode.
 * In production, all log statements are no-ops to prevent information leakage
 * and performance overhead.
 *
 * Usage:
 *   import { logger } from '@/lib/logger'
 *   logger.debug('Debug info')
 *   logger.info('General info')
 *   logger.warn('Warning message')
 *   logger.error('Error occurred', error)
 */

const isDevelopment = import.meta.env.DEV || import.meta.env.MODE === 'development'

/**
 * Logger interface matching console API
 */
export interface Logger {
  debug(...args: unknown[]): void
  info(...args: unknown[]): void
  log(...args: unknown[]): void
  warn(...args: unknown[]): void
  error(...args: unknown[]): void
  group(label?: string): void
  groupEnd(): void
  time(label?: string): void
  timeEnd(label?: string): void
}

/**
 * No-op logger for production (all methods do nothing)
 */
const productionLogger: Logger = {
  debug: () => {},
  info: () => {},
  log: () => {},
  warn: () => {},
  error: () => {},
  group: () => {},
  groupEnd: () => {},
  time: () => {},
  timeEnd: () => {},
}

/**
 * Development logger (proxies to console)
 */
const developmentLogger: Logger = {
  debug: (...args: unknown[]) => console.debug(...args),
  info: (...args: unknown[]) => console.info(...args),
  log: (...args: unknown[]) => console.log(...args),
  warn: (...args: unknown[]) => console.warn(...args),
  error: (...args: unknown[]) => console.error(...args),
  group: (label?: string) => console.group(label),
  groupEnd: () => console.groupEnd(),
  time: (label?: string) => console.time(label),
  timeEnd: (label?: string) => console.timeEnd(label),
}

/**
 * Main logger instance
 * Automatically switches between dev/prod based on environment
 */
export const logger: Logger = isDevelopment ? developmentLogger : productionLogger

/**
 * Conditional logger that respects environment
 * Use this for backwards compatibility with existing console.log calls
 */
export const devLog = (...args: unknown[]): void => {
  if (isDevelopment) {
    console.log(...args)
  }
}

export const devWarn = (...args: unknown[]): void => {
  if (isDevelopment) {
    console.warn(...args)
  }
}

export const devError = (...args: unknown[]): void => {
  if (isDevelopment) {
    console.error(...args)
  }
}

/**
 * Create a namespaced logger for a specific module
 * Example: const log = createLogger('FirebaseClient')
 */
export const createLogger = (namespace: string): Logger => {
  if (!isDevelopment) {
    return productionLogger
  }

  return {
    debug: (...args: unknown[]) => console.debug(`[${namespace}]`, ...args),
    info: (...args: unknown[]) => console.info(`[${namespace}]`, ...args),
    log: (...args: unknown[]) => console.log(`[${namespace}]`, ...args),
    warn: (...args: unknown[]) => console.warn(`[${namespace}]`, ...args),
    error: (...args: unknown[]) => console.error(`[${namespace}]`, ...args),
    group: (label?: string) => console.group(`[${namespace}] ${label || ''}`),
    groupEnd: () => console.groupEnd(),
    time: (label?: string) => console.time(`[${namespace}] ${label || ''}`),
    timeEnd: (label?: string) => console.timeEnd(`[${namespace}] ${label || ''}`),
  }
}

/**
 * Performance logger for measuring execution time
 */
export class PerformanceLogger {
  private startTimes: Map<string, number> = new Map()

  start(label: string): void {
    if (isDevelopment) {
      this.startTimes.set(label, performance.now())
    }
  }

  end(label: string): void {
    if (isDevelopment) {
      const startTime = this.startTimes.get(label)
      if (startTime !== undefined) {
        const duration = performance.now() - startTime
        console.log(`[Performance] ${label}: ${duration.toFixed(2)}ms`)
        this.startTimes.delete(label)
      }
    }
  }

  measure(label: string, fn: () => void): void {
    this.start(label)
    fn()
    this.end(label)
  }

  async measureAsync<T>(label: string, fn: () => Promise<T>): Promise<T> {
    this.start(label)
    try {
      return await fn()
    } finally {
      this.end(label)
    }
  }
}

export const performanceLogger = new PerformanceLogger()

// Default export
export default logger
