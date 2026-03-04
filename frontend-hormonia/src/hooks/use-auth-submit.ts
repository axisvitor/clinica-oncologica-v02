import { useState, useCallback } from 'react'
import { createLogger } from '@/lib/logger'
import { getErrorMessage } from '@/lib/utils/type-guards'

const logger = createLogger('useAuthSubmit')

interface AuthSubmitOptions<T> {
  onSubmit: (data: T) => Promise<void>
  onSuccess?: () => void
  onError?: (error: Error) => void
}

export function useAuthSubmit<T>({ onSubmit, onSuccess, onError }: AuthSubmitOptions<T>) {
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = useCallback(
    async (data: T) => {
      setIsSubmitting(true)
      setError(null)
      try {
        await onSubmit(data)
        if (onSuccess) {
          onSuccess()
        }
      } catch (err: unknown) {
        logger.error('Authentication error', { error: getErrorMessage(err) })
        const errorMessage =
          getErrorMessage(err) || 'An unexpected error occurred. Please try again.'
        setError(errorMessage)
        if (onError) {
          onError(err instanceof Error ? err : new Error(getErrorMessage(err)))
        }
      } finally {
        setIsSubmitting(false)
      }
    },
    [onSubmit, onSuccess, onError]
  )

  return {
    isSubmitting,
    error,
    handleSubmit,
  }
}
