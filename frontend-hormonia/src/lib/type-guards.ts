/**
 * Type Guards and Error Handling Utilities
 *
 * This module provides type-safe error handling utilities and type guards
 * for working with unknown error types in TypeScript.
 */

/**
 * Type guard to check if error has a message property
 *
 * @param error - Unknown error object to check
 * @returns True if error is an object with a string message property
 *
 * @example
 * ```typescript
 * try {
 *   throw new Error('Something went wrong');
 * } catch (error) {
 *   if (isErrorWithMessage(error)) {
 *     console.log(error.message); // Type-safe access to message
 *   }
 * }
 * ```
 */
export function isErrorWithMessage(
  error: unknown
): error is { message: string } {
  return (
    typeof error === 'object' &&
    error !== null &&
    'message' in error &&
    typeof (error as { message: unknown }).message === 'string'
  );
}

/**
 * Extract error message from unknown error type
 *
 * This function safely extracts a string message from various error types,
 * providing a fallback for unknown error formats.
 *
 * @param error - Unknown error object
 * @returns String error message
 *
 * @example
 * ```typescript
 * try {
 *   await riskyOperation();
 * } catch (error) {
 *   const message = getErrorMessage(error);
 *   console.error(message);
 * }
 * ```
 */
export function getErrorMessage(error: unknown): string {
  if (isErrorWithMessage(error)) {
    return error.message;
  }

  if (typeof error === 'string') {
    return error;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return 'An unknown error occurred';
}

/**
 * Type guard for API errors with status codes
 *
 * @param error - Unknown error object to check
 * @returns True if error is an object with message and status properties
 *
 * @example
 * ```typescript
 * try {
 *   await apiCall();
 * } catch (error) {
 *   if (isApiError(error)) {
 *     console.log(`${error.status}: ${error.message}`);
 *   }
 * }
 * ```
 */
export function isApiError(
  error: unknown
): error is { message: string; status: number } {
  return (
    isErrorWithMessage(error) &&
    'status' in error &&
    typeof (error as { status: unknown }).status === 'number'
  );
}

/**
 * Type guard to check if value is a non-null object
 *
 * @param value - Value to check
 * @returns True if value is a non-null object
 */
export function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

/**
 * Type guard to check if error has a code property
 *
 * @param error - Unknown error object to check
 * @returns True if error is an object with a string code property
 */
export function isErrorWithCode(
  error: unknown
): error is { code: string; message?: string } {
  return (
    isObject(error) &&
    'code' in error &&
    typeof (error as { code: unknown }).code === 'string'
  );
}
