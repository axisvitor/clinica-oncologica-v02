/**
 * Type guard utilities for runtime type checking and validation
 * Enhanced version with comprehensive type guards for the application
 */

import React from 'react'

// ============================================
// Basic Type Guards
// ============================================

export function isString(value: unknown): value is string {
  return typeof value === 'string'
}

export function isNumber(value: unknown): value is number {
  return typeof value === 'number' && !isNaN(value)
}

export function isBoolean(value: unknown): value is boolean {
  return typeof value === 'boolean'
}

export function isNull(value: unknown): value is null {
  return value === null
}

export function isUndefined(value: unknown): value is undefined {
  return value === undefined
}

export function isNullish(value: unknown): value is null | undefined {
  return value === null || value === undefined
}

export function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export function isArray(value: unknown): value is unknown[] {
  return Array.isArray(value)
}

export function isFunction(value: unknown): value is (...args: unknown[]) => unknown {
  return typeof value === 'function'
}

// ============================================
// Property Guards
// ============================================

export function hasProperty<K extends string>(obj: unknown, key: K): obj is Record<K, unknown> {
  return isObject(obj) && key in obj
}

export function hasStringProperty<K extends string>(
  obj: unknown,
  key: K
): obj is Record<K, string> {
  return hasProperty(obj, key) && isString(obj[key])
}

export function hasNumberProperty<K extends string>(
  obj: unknown,
  key: K
): obj is Record<K, number> {
  return hasProperty(obj, key) && isNumber(obj[key])
}

export function hasBooleanProperty<K extends string>(
  obj: unknown,
  key: K
): obj is Record<K, boolean> {
  return hasProperty(obj, key) && isBoolean(obj[key])
}

// ============================================
// Error Type Guards
// ============================================

export interface ApiError {
  message: string
  code?: string
  status?: number
  details?: unknown
}

export function isApiError(error: unknown): error is ApiError {
  return isObject(error) && hasStringProperty(error, 'message')
}

export function isError(error: unknown): error is Error {
  return error instanceof Error
}

export function isErrorWithMessage(error: unknown): error is { message: string } {
  return hasStringProperty(error, 'message')
}

export function getErrorMessage(error: unknown): string {
  if (isErrorWithMessage(error)) {
    return error.message
  }
  if (isString(error)) {
    return error
  }
  return 'An unknown error occurred'
}

// ============================================
// React Event Type Guards
// ============================================

export function isReactChangeEvent(
  event: unknown
): event is React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement> {
  return (
    isObject(event) &&
    hasProperty(event, 'target') &&
    isObject(event['target']) &&
    hasProperty(event['target'], 'value')
  )
}

export function isReactMouseEvent(event: unknown): event is React.MouseEvent {
  return isObject(event) && hasProperty(event, 'clientX') && hasProperty(event, 'clientY')
}

// ============================================
// Validation Helpers
// ============================================

export function getStringFromUnknown(value: unknown, defaultValue: string = ''): string {
  return isString(value) ? value : defaultValue
}

export function getNumberFromUnknown(value: unknown, defaultValue: number = 0): number {
  return isNumber(value) ? value : defaultValue
}

export function getBooleanFromUnknown(value: unknown, defaultValue: boolean = false): boolean {
  return isBoolean(value) ? value : defaultValue
}

export function getArrayFromUnknown<T>(value: unknown, defaultValue: T[] = []): T[] {
  return isArray(value) ? (value as T[]) : defaultValue
}

// ============================================
// Generic Type Validator
// ============================================

export function validateType<T>(
  value: unknown,
  validator: (val: unknown) => val is T,
  errorMessage?: string
): T {
  if (validator(value)) {
    return value
  }
  throw new TypeError(errorMessage || 'Type validation failed')
}

export function validateTypeOrDefault<T>(
  value: unknown,
  validator: (val: unknown) => val is T,
  defaultValue: T
): T {
  return validator(value) ? value : defaultValue
}

// ============================================
// Complex Type Guards
// ============================================

export interface RecordWithId {
  id: string | number
}

export function hasId(value: unknown): value is RecordWithId {
  return (
    isObject(value) && hasProperty(value, 'id') && (isString(value['id']) || isNumber(value['id']))
  )
}

export function isArrayOfObjects(value: unknown): value is Record<string, unknown>[] {
  return isArray(value) && value.every(isObject)
}

export function isStringArray(value: unknown): value is string[] {
  return isArray(value) && value.every(isString)
}

export function isNumberArray(value: unknown): value is number[] {
  return isArray(value) && value.every(isNumber)
}

// ============================================
// Null/Undefined Filtering
// ============================================

export function isDefined<T>(value: T | null | undefined): value is T {
  return value !== null && value !== undefined
}

export function filterDefined<T>(array: (T | null | undefined)[]): T[] {
  return array.filter(isDefined)
}

// ============================================
// Type Assertion Utilities
// ============================================

export function assertIsDefined<T>(
  value: T | null | undefined,
  message?: string
): asserts value is T {
  if (value === null || value === undefined) {
    throw new Error(message || 'Value is null or undefined')
  }
}

export function assertIsString(value: unknown, message?: string): asserts value is string {
  if (!isString(value)) {
    throw new TypeError(message || 'Value is not a string')
  }
}

export function assertIsNumber(value: unknown, message?: string): asserts value is number {
  if (!isNumber(value)) {
    throw new TypeError(message || 'Value is not a number')
  }
}

// ============================================
// React Type Guards
// ============================================

/**
 * Type guard to validate if a value can be safely used as React.ReactNode
 * @param value - Value to check
 * @returns true if the value is a valid ReactNode
 */
export function isValidReactNode(value: unknown): value is React.ReactNode {
  // null and undefined are valid React children
  if (value == null) {
    return true
  }

  // Primitives that React can render
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return true
  }

  // Valid React element
  if (React.isValidElement(value)) {
    return true
  }

  // Arrays are valid if all elements are valid ReactNodes
  if (Array.isArray(value)) {
    return value.every(isValidReactNode)
  }

  // Fragments and other React-specific types
  return false
}

/**
 * Safely converts an unknown value to a ReactNode, with fallback
 * @param value - Value to convert
 * @param fallback - Fallback value if conversion fails (default: null)
 * @returns A valid ReactNode
 */
export function toReactNode(value: unknown, fallback: React.ReactNode = null): React.ReactNode {
  if (isValidReactNode(value)) {
    return value
  }

  // Try to convert to string if it's an object
  if (isObject(value)) {
    return fallback
  }

  return fallback
}

/**
 * Safely converts an unknown value to a string for React rendering
 * @param value - Value to convert
 * @param fallback - Fallback string (default: empty string)
 * @returns A string safe for React rendering
 */
export function toReactString(value: unknown, fallback: string = ''): string {
  if (value == null) {
    return fallback
  }

  if (typeof value === 'string') {
    return value
  }

  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value)
  }

  // For objects, try to get a meaningful string representation
  if (isObject(value)) {
    if ('toString' in value && typeof value.toString === 'function') {
      const result = value.toString()
      if (result !== '[object Object]') {
        return result
      }
    }
  }

  return fallback
}
