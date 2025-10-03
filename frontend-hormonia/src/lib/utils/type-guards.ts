/**
 * Type guard utilities for runtime type checking
 */

export function isString(value: unknown): value is string {
  return typeof value === 'string'
}

export function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

export function hasProperty<K extends string>(
  obj: unknown,
  key: K
): obj is Record<K, unknown> {
  return isObject(obj) && key in obj
}

export function hasStringProperty<K extends string>(
  obj: unknown,
  key: K
): obj is Record<K, string> {
  return hasProperty(obj, key) && isString(obj[key])
}

export function getStringFromUnknown(value: unknown, defaultValue: string = ''): string {
  return isString(value) ? value : defaultValue
}