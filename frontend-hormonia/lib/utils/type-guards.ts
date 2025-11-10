/**
 * Type Guards and Utility Functions for Type Safety
 * 
 * This module provides comprehensive type guards and utility functions
 * to handle unknown and {} types safely throughout the application.
 */

// Basic type guards
export function isString(value: unknown): value is string {
  return typeof value === 'string'
}

export function isNumber(value: unknown): value is number {
  return typeof value === 'number'
}

export function isBoolean(value: unknown): value is boolean {
  return typeof value === 'boolean'
}

export function isArray(value: unknown): value is unknown[] {
  return Array.isArray(value)
}

export function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export function isFunction(value: unknown): value is (...args: unknown[]) => unknown {
  return typeof value === 'function'
}

export function isDate(value: unknown): value is Date {
  return value instanceof Date
}

// Property existence checks
export function hasProperty<T>(obj: unknown, prop: string): obj is T & Record<string, unknown> {
  return typeof obj === 'object' && obj !== null && prop in obj
}

export function hasStringProperty(obj: unknown, prop: string): obj is Record<string, unknown> & { [K in typeof prop]: string } {
  return hasProperty(obj, prop) && isString((obj as Record<string, unknown>)[prop])
}

export function hasNumberProperty(obj: unknown, prop: string): obj is Record<string, unknown> & { [K in typeof prop]: number } {
  return hasProperty(obj, prop) && isNumber((obj as Record<string, unknown>)[prop])
}

// Safe getters with defaults
export function getStringFromUnknown(value: unknown, defaultValue = ''): string {
  return isString(value) ? value : defaultValue
}

export function getNumberFromUnknown(value: unknown, defaultValue = 0): number {
  return isNumber(value) ? value : defaultValue
}

export function getBooleanFromUnknown(value: unknown, defaultValue = false): boolean {
  return isBoolean(value) ? value : defaultValue
}

export function getArrayFromUnknown(value: unknown, defaultValue: unknown[] = []): unknown[] {
  return isArray(value) ? value : defaultValue
}

export function getObjectFromUnknown(value: unknown, defaultValue: Record<string, unknown> = {}): Record<string, unknown> {
  return isObject(value) ? value : defaultValue
}

// Config-specific getters
export function getStringFromConfig(config: Record<string, unknown>, key: string, defaultValue = ''): string {
  const value = config[key]
  return isString(value) ? value : defaultValue
}

export function getNumberFromConfig(config: Record<string, unknown>, key: string, defaultValue = 0): number {
  const value = config[key]
  return isNumber(value) ? value : defaultValue
}

export function getBooleanFromConfig(config: Record<string, unknown>, key: string, defaultValue = false): boolean {
  const value = config[key]
  return isBoolean(value) ? value : defaultValue
}

export function getArrayFromConfig(config: Record<string, unknown>, key: string, defaultValue: unknown[] = []): unknown[] {
  const value = config[key]
  return isArray(value) ? value : defaultValue
}

export function getObjectFromConfig(config: Record<string, unknown>, key: string, defaultValue: Record<string, unknown> = {}): Record<string, unknown> {
  const value = config[key]
  return isObject(value) ? value : defaultValue
}

// Error handling utilities
export function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message
  }
  if (isString(error)) {
    return error
  }
  if (isObject(error) && hasStringProperty(error, 'message')) {
    return error['message'] || 'Unknown error'
  }
  return 'An unknown error occurred'
}

export function getErrorCode(error: unknown): string | number | undefined {
  if (isObject(error)) {
    if (hasStringProperty(error, 'code')) {
      return error['code']
    }
    if (hasNumberProperty(error, 'code')) {
      return error['code']
    }
    if (hasStringProperty(error, 'status')) {
      return error['status']
    }
    if (hasNumberProperty(error, 'status')) {
      return error['status']
    }
  }
  return undefined
}

// API response utilities
export function isApiResponse<T>(value: unknown): value is { data: T; success: boolean } {
  return isObject(value) && hasProperty(value, 'data') && hasBooleanProperty(value, 'success')
}

export function hasBooleanProperty(obj: unknown, prop: string): obj is Record<string, unknown> & { [K in typeof prop]: boolean } {
  return hasProperty(obj, prop) && isBoolean((obj as Record<string, unknown>)[prop])
}

// Form data utilities
export function getFormValue(formData: FormData, key: string): string {
  const value = formData.get(key)
  return isString(value) ? value : ''
}

export function getFormValues(formData: FormData, key: string): string[] {
  const values = formData.getAll(key)
  return values.filter(isString)
}

// Event utilities
export function getInputValue(event: unknown): string {
  if (isObject(event) && hasProperty(event, 'target')) {
    const target = event['target']
    if (isObject(target) && hasStringProperty(target, 'value')) {
      return target['value'] || ''
    }
  }
  return ''
}

export function getSelectValue(event: unknown): string {
  return getInputValue(event)
}

// Validation utilities
export function isValidEmail(value: unknown): value is string {
  if (!isString(value)) return false
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  return emailRegex.test(value)
}

export function isValidUrl(value: unknown): value is string {
  if (!isString(value)) return false
  try {
    new URL(value)
    return true
  } catch {
    return false
  }
}

export function isValidPhoneNumber(value: unknown): value is string {
  if (!isString(value)) return false
  const phoneRegex = /^\+?[1-9]?[0-9]{7,15}$/
  return phoneRegex.test(value.replace(/[\s-()]/g, ''))
}

// Date utilities
export function getDateFromUnknown(value: unknown): Date | null {
  if (isDate(value)) {
    return value
  }
  if (isString(value)) {
    const date = new Date(value)
    return isNaN(date.getTime()) ? null : date
  }
  if (isNumber(value)) {
    const date = new Date(value)
    return isNaN(date.getTime()) ? null : date
  }
  return null
}

// Safe JSON utilities
export function safeJsonParse<T = unknown>(value: unknown): T | null {
  if (!isString(value)) return null
  try {
    return JSON.parse(value) as T
  } catch {
    return null
  }
}

export function safeJsonStringify(value: unknown): string {
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}