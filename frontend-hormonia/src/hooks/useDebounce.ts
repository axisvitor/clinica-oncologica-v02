import { useState, useEffect, useRef, useCallback } from 'react'

/**
 * Custom hook that debounces a value
 * @param value - The value to debounce
 * @param delay - The debounce delay in milliseconds
 * @returns The debounced value
 */
export function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value)

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value)
    }, delay)

    return () => {
      clearTimeout(handler)
    }
  }, [value, delay])

  return debouncedValue
}

/**
 * Custom hook that debounces a callback function
 * Uses useRef to avoid re-renders when callback reference changes
 * @param callback - The callback function to debounce
 * @param delay - The debounce delay in milliseconds
 * @param deps - Additional dependencies for the debounced function
 * @returns The debounced callback function
 */
export function useDebouncedCallback<T extends (...args: unknown[]) => unknown>(
  callback: T,
  delay: number,
  deps: React.DependencyList = []
): T {
  // Store the latest callback in a ref to avoid stale closures
  const callbackRef = useRef<T>(callback)
  const timeoutRef = useRef<NodeJS.Timeout | null>(null)

  // Update ref when callback changes
  useEffect(() => {
    callbackRef.current = callback
  }, [callback])

  // Create stable debounced function
  const debouncedFn = useCallback(
    (...args: Parameters<T>) => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }

      timeoutRef.current = setTimeout(() => {
        callbackRef.current(...args)
      }, delay)
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps -- spread deps is intentional for dynamic dependency injection
    [delay, ...deps]
  ) as T

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
      }
    }
  }, [])

  return debouncedFn
}

/**
 * Custom hook that throttles a callback function
 * @param callback - The callback function to throttle
 * @param delay - The throttle delay in milliseconds
 * @returns The throttled callback function
 */
export function useThrottledCallback<T extends (...args: unknown[]) => unknown>(
  callback: T,
  delay: number
): T {
  const lastRunRef = useRef<number>(0)
  const callbackRef = useRef<T>(callback)

  useEffect(() => {
    callbackRef.current = callback
  }, [callback])

  return useCallback(
    (...args: Parameters<T>) => {
      const now = Date.now()
      if (now - lastRunRef.current >= delay) {
        lastRunRef.current = now
        callbackRef.current(...args)
      }
    },
    [delay]
  ) as T
}

export default useDebounce
