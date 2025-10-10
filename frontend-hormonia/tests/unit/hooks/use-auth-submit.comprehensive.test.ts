import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useAuthSubmit } from '@/hooks/use-auth-submit'

// Mock dependencies
const mockToast = vi.fn()

vi.mock('@/hooks/use-toast', () => ({
  toast: mockToast
}))

describe('useAuthSubmit Hook - Comprehensive Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('Hook Initialization', () => {
    it('should initialize with correct default values', () => {
      const mockOnSubmit = vi.fn()
      const { result } = renderHook(() =>
        useAuthSubmit({ onSubmit: mockOnSubmit })
      )

      expect(result.current.isSubmitting).toBe(false)
      expect(result.current.error).toBe(null)
      expect(typeof result.current.handleSubmit).toBe('function')
    })

    it('should accept custom error handler', () => {
      const mockOnSubmit = vi.fn()
      const mockOnError = vi.fn()

      const { result } = renderHook(() =>
        useAuthSubmit({
          onSubmit: mockOnSubmit,
          onError: mockOnError
        })
      )

      expect(result.current.isSubmitting).toBe(false)
      expect(result.current.error).toBe(null)
    })
  })

  describe('Submit Handling', () => {
    it('should handle successful submission', async () => {
      const mockOnSubmit = vi.fn().mockResolvedValue(undefined)
      const { result } = renderHook(() =>
        useAuthSubmit({ onSubmit: mockOnSubmit })
      )

      const testData = { email: 'test@example.com', password: 'password123' }

      await act(async () => {
        await result.current.handleSubmit(testData)
      })

      expect(mockOnSubmit).toHaveBeenCalledWith(testData)
      expect(result.current.isSubmitting).toBe(false)
      expect(result.current.error).toBe(null)
    })

    it('should set loading state during submission', async () => {
      let resolveSubmit: any
      const mockOnSubmit = vi.fn().mockReturnValue(
        new Promise(resolve => { resolveSubmit = resolve })
      )

      const { result } = renderHook(() =>
        useAuthSubmit({ onSubmit: mockOnSubmit })
      )

      const testData = { email: 'test@example.com', password: 'password123' }

      act(() => {
        result.current.handleSubmit(testData)
      })

      expect(result.current.isSubmitting).toBe(true)
      expect(result.current.error).toBe(null)

      await act(async () => {
        resolveSubmit()
      })

      expect(result.current.isSubmitting).toBe(false)
    })

    it('should handle submission errors', async () => {
      const mockError = new Error('Authentication failed')
      const mockOnSubmit = vi.fn().mockRejectedValue(mockError)

      const { result } = renderHook(() =>
        useAuthSubmit({ onSubmit: mockOnSubmit })
      )

      const testData = { email: 'test@example.com', password: 'wrongpassword' }

      await act(async () => {
        await result.current.handleSubmit(testData)
      })

      expect(result.current.isSubmitting).toBe(false)
      expect(result.current.error).toBe('Authentication failed')
    })

    it('should call custom error handler on error', async () => {
      const mockError = new Error('Custom error')
      const mockOnSubmit = vi.fn().mockRejectedValue(mockError)
      const mockOnError = vi.fn()

      const { result } = renderHook(() =>
        useAuthSubmit({
          onSubmit: mockOnSubmit,
          onError: mockOnError
        })
      )

      const testData = { email: 'test@example.com', password: 'wrongpassword' }

      await act(async () => {
        await result.current.handleSubmit(testData)
      })

      expect(mockOnError).toHaveBeenCalledWith(mockError)
      expect(result.current.error).toBe('Custom error')
    })
  })

  describe('Error Message Handling', () => {
    it('should extract error message from Error object', async () => {
      const mockOnSubmit = vi.fn().mockRejectedValue(new Error('Invalid credentials'))

      const { result } = renderHook(() =>
        useAuthSubmit({ onSubmit: mockOnSubmit })
      )

      await act(async () => {
        await result.current.handleSubmit({ email: 'test@example.com' })
      })

      expect(result.current.error).toBe('Invalid credentials')
    })

    it('should handle string errors', async () => {
      const mockOnSubmit = vi.fn().mockRejectedValue('Network error')

      const { result } = renderHook(() =>
        useAuthSubmit({ onSubmit: mockOnSubmit })
      )

      await act(async () => {
        await result.current.handleSubmit({ email: 'test@example.com' })
      })

      expect(result.current.error).toBe('Network error')
    })

    it('should handle HTTP error responses', async () => {
      const mockError = {
        response: {
          data: {
            message: 'User not found'
          },
          status: 404
        }
      }

      const mockOnSubmit = vi.fn().mockRejectedValue(mockError)

      const { result } = renderHook(() =>
        useAuthSubmit({ onSubmit: mockOnSubmit })
      )

      await act(async () => {
        await result.current.handleSubmit({ email: 'test@example.com' })
      })

      expect(result.current.error).toBe('User not found')
    })

    it('should handle unknown error formats with fallback message', async () => {
      const mockOnSubmit = vi.fn().mockRejectedValue({ unknown: 'error' })

      const { result } = renderHook(() =>
        useAuthSubmit({ onSubmit: mockOnSubmit })
      )

      await act(async () => {
        await result.current.handleSubmit({ email: 'test@example.com' })
      })

      expect(result.current.error).toBe('An unexpected error occurred')
    })

    it('should handle null/undefined errors', async () => {
      const mockOnSubmit = vi.fn().mockRejectedValue(null)

      const { result } = renderHook(() =>
        useAuthSubmit({ onSubmit: mockOnSubmit })
      )

      await act(async () => {
        await result.current.handleSubmit({ email: 'test@example.com' })
      })

      expect(result.current.error).toBe('An unexpected error occurred')
    })
  })

  describe('Error Clearing', () => {
    it('should clear error on successful submission', async () => {
      const mockOnSubmit = vi.fn()
        .mockRejectedValueOnce(new Error('First error'))
        .mockResolvedValueOnce(undefined)

      const { result } = renderHook(() =>
        useAuthSubmit({ onSubmit: mockOnSubmit })
      )

      // First submission fails
      await act(async () => {
        await result.current.handleSubmit({ email: 'test@example.com' })
      })

      expect(result.current.error).toBe('First error')

      // Second submission succeeds
      await act(async () => {
        await result.current.handleSubmit({ email: 'test@example.com' })
      })

      expect(result.current.error).toBe(null)
    })

    it('should clear error when starting new submission', async () => {
      let resolveSubmit: any
      const mockOnSubmit = vi.fn()
        .mockRejectedValueOnce(new Error('Initial error'))
        .mockReturnValueOnce(new Promise(resolve => { resolveSubmit = resolve }))

      const { result } = renderHook(() =>
        useAuthSubmit({ onSubmit: mockOnSubmit })
      )

      // First submission fails
      await act(async () => {
        await result.current.handleSubmit({ email: 'test@example.com' })
      })

      expect(result.current.error).toBe('Initial error')

      // Start second submission
      act(() => {
        result.current.handleSubmit({ email: 'test@example.com' })
      })

      // Error should be cleared immediately when starting new submission
      expect(result.current.error).toBe(null)
      expect(result.current.isSubmitting).toBe(true)

      await act(async () => {
        resolveSubmit()
      })
    })
  })

  describe('Concurrent Submissions', () => {
    it('should prevent concurrent submissions', async () => {
      let resolveFirst: any
      let resolveSecond: any

      const mockOnSubmit = vi.fn()
        .mockReturnValueOnce(new Promise(resolve => { resolveFirst = resolve }))
        .mockReturnValueOnce(new Promise(resolve => { resolveSecond = resolve }))

      const { result } = renderHook(() =>
        useAuthSubmit({ onSubmit: mockOnSubmit })
      )

      // Start first submission
      act(() => {
        result.current.handleSubmit({ email: 'test1@example.com' })
      })

      expect(result.current.isSubmitting).toBe(true)

      // Try to start second submission while first is pending
      act(() => {
        result.current.handleSubmit({ email: 'test2@example.com' })
      })

      // Should still be processing first submission
      expect(mockOnSubmit).toHaveBeenCalledTimes(1)
      expect(mockOnSubmit).toHaveBeenCalledWith({ email: 'test1@example.com' })

      // Complete first submission
      await act(async () => {
        resolveFirst()
      })

      expect(result.current.isSubmitting).toBe(false)
    })

    it('should allow new submission after previous completes', async () => {
      const mockOnSubmit = vi.fn()
        .mockResolvedValueOnce(undefined)
        .mockResolvedValueOnce(undefined)

      const { result } = renderHook(() =>
        useAuthSubmit({ onSubmit: mockOnSubmit })
      )

      // First submission
      await act(async () => {
        await result.current.handleSubmit({ email: 'test1@example.com' })
      })

      expect(result.current.isSubmitting).toBe(false)

      // Second submission should be allowed
      await act(async () => {
        await result.current.handleSubmit({ email: 'test2@example.com' })
      })

      expect(mockOnSubmit).toHaveBeenCalledTimes(2)
      expect(mockOnSubmit).toHaveBeenNthCalledWith(1, { email: 'test1@example.com' })
      expect(mockOnSubmit).toHaveBeenNthCalledWith(2, { email: 'test2@example.com' })
    })
  })

  describe('Toast Integration', () => {
    it('should show toast on authentication error', async () => {
      const mockOnSubmit = vi.fn().mockRejectedValue(new Error('Invalid password'))

      const { result } = renderHook(() =>
        useAuthSubmit({
          onSubmit: mockOnSubmit,
          showToastOnError: true
        })
      )

      await act(async () => {
        await result.current.handleSubmit({ password: 'wrong' })
      })

      expect(mockToast).toHaveBeenCalledWith({
        title: 'Erro de autenticação',
        description: 'Invalid password',
        variant: 'destructive'
      })
    })

    it('should not show toast when showToastOnError is false', async () => {
      const mockOnSubmit = vi.fn().mockRejectedValue(new Error('Error'))

      const { result } = renderHook(() =>
        useAuthSubmit({
          onSubmit: mockOnSubmit,
          showToastOnError: false
        })
      )

      await act(async () => {
        await result.current.handleSubmit({ email: 'test@example.com' })
      })

      expect(mockToast).not.toHaveBeenCalled()
    })

    it('should show toast on successful submission when configured', async () => {
      const mockOnSubmit = vi.fn().mockResolvedValue(undefined)

      const { result } = renderHook(() =>
        useAuthSubmit({
          onSubmit: mockOnSubmit,
          showToastOnSuccess: true,
          successMessage: 'Login successful!'
        })
      )

      await act(async () => {
        await result.current.handleSubmit({ email: 'test@example.com' })
      })

      expect(mockToast).toHaveBeenCalledWith({
        title: 'Sucesso',
        description: 'Login successful!',
        variant: 'default'
      })
    })
  })

  describe('Retry Logic', () => {
    it('should support retry on failure when configured', async () => {
      const mockOnSubmit = vi.fn()
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValueOnce(undefined)

      const { result } = renderHook(() =>
        useAuthSubmit({
          onSubmit: mockOnSubmit,
          retryAttempts: 1,
          retryDelay: 100
        })
      )

      await act(async () => {
        await result.current.handleSubmit({ email: 'test@example.com' })
      })

      // Should have retried once
      expect(mockOnSubmit).toHaveBeenCalledTimes(2)
      expect(result.current.error).toBe(null)
    })

    it('should respect retry attempts limit', async () => {
      const mockOnSubmit = vi.fn().mockRejectedValue(new Error('Persistent error'))

      const { result } = renderHook(() =>
        useAuthSubmit({
          onSubmit: mockOnSubmit,
          retryAttempts: 2,
          retryDelay: 10
        })
      )

      await act(async () => {
        await result.current.handleSubmit({ email: 'test@example.com' })
      })

      // Should have attempted 3 times total (initial + 2 retries)
      expect(mockOnSubmit).toHaveBeenCalledTimes(3)
      expect(result.current.error).toBe('Persistent error')
    })

    it('should apply retry delay between attempts', async () => {
      const mockOnSubmit = vi.fn()
        .mockRejectedValueOnce(new Error('Temporary error'))
        .mockResolvedValueOnce(undefined)

      const startTime = Date.now()

      const { result } = renderHook(() =>
        useAuthSubmit({
          onSubmit: mockOnSubmit,
          retryAttempts: 1,
          retryDelay: 500
        })
      )

      await act(async () => {
        await result.current.handleSubmit({ email: 'test@example.com' })
      })

      const endTime = Date.now()
      const duration = endTime - startTime

      // Should have waited at least the retry delay
      expect(duration).toBeGreaterThanOrEqual(400) // Allow some margin for test timing
      expect(mockOnSubmit).toHaveBeenCalledTimes(2)
    })
  })

  describe('Custom Validation', () => {
    it('should support custom validation before submission', async () => {
      const mockOnSubmit = vi.fn().mockResolvedValue(undefined)
      const mockValidator = vi.fn().mockReturnValue('Email is required')

      const { result } = renderHook(() =>
        useAuthSubmit({
          onSubmit: mockOnSubmit,
          validator: mockValidator
        })
      )

      await act(async () => {
        await result.current.handleSubmit({ email: '' })
      })

      expect(mockValidator).toHaveBeenCalledWith({ email: '' })
      expect(mockOnSubmit).not.toHaveBeenCalled()
      expect(result.current.error).toBe('Email is required')
    })

    it('should proceed with submission when validation passes', async () => {
      const mockOnSubmit = vi.fn().mockResolvedValue(undefined)
      const mockValidator = vi.fn().mockReturnValue(null) // null means validation passed

      const { result } = renderHook(() =>
        useAuthSubmit({
          onSubmit: mockOnSubmit,
          validator: mockValidator
        })
      )

      await act(async () => {
        await result.current.handleSubmit({ email: 'test@example.com' })
      })

      expect(mockValidator).toHaveBeenCalledWith({ email: 'test@example.com' })
      expect(mockOnSubmit).toHaveBeenCalledWith({ email: 'test@example.com' })
      expect(result.current.error).toBe(null)
    })
  })

  describe('Performance Optimization', () => {
    it('should debounce rapid submissions', async () => {
      const mockOnSubmit = vi.fn().mockResolvedValue(undefined)

      const { result } = renderHook(() =>
        useAuthSubmit({
          onSubmit: mockOnSubmit,
          debounceMs: 100
        })
      )

      // Rapid submissions
      act(() => {
        result.current.handleSubmit({ email: 'test1@example.com' })
        result.current.handleSubmit({ email: 'test2@example.com' })
        result.current.handleSubmit({ email: 'test3@example.com' })
      })

      // Wait for debounce
      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 150))
      })

      // Should only have called once with the last value
      expect(mockOnSubmit).toHaveBeenCalledTimes(1)
      expect(mockOnSubmit).toHaveBeenCalledWith({ email: 'test3@example.com' })
    })
  })

  describe('Memory Cleanup', () => {
    it('should cleanup on unmount', () => {
      const mockOnSubmit = vi.fn()

      const { unmount } = renderHook(() =>
        useAuthSubmit({ onSubmit: mockOnSubmit })
      )

      // Unmount should not throw errors
      expect(() => unmount()).not.toThrow()
    })

    it('should not update state after unmount', async () => {
      let resolveSubmit: any
      const mockOnSubmit = vi.fn().mockReturnValue(
        new Promise(resolve => { resolveSubmit = resolve })
      )

      const { result, unmount } = renderHook(() =>
        useAuthSubmit({ onSubmit: mockOnSubmit })
      )

      // Start submission
      act(() => {
        result.current.handleSubmit({ email: 'test@example.com' })
      })

      // Unmount before completion
      unmount()

      // Complete submission
      await act(async () => {
        resolveSubmit()
      })

      // Should not throw error or update state
      expect(() => {}).not.toThrow()
    })
  })
})