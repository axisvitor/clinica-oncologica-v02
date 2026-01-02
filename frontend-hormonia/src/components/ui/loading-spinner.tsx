import React from 'react'
import { Loader2, RefreshCw, CheckCircle, XCircle } from 'lucide-react'
import { cn } from '@/lib/utils'

// Size variants including xs for compact uses
type SpinnerSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl'

// Color variants using design tokens
type SpinnerColor = 'primary' | 'secondary' | 'muted' | 'destructive' | 'success'

// Visual variants for different loading styles
type SpinnerVariant = 'spinner' | 'refresh' | 'pulse' | 'bounce' | 'circle'

// Status for state transitions
type SpinnerStatus = 'loading' | 'success' | 'error'

interface LoadingSpinnerProps {
  size?: SpinnerSize
  className?: string
  text?: string
  overlay?: boolean
  color?: SpinnerColor
  variant?: SpinnerVariant
  status?: SpinnerStatus
  showProgress?: boolean
  progress?: number
  'aria-label'?: string
}

interface LoadingOverlayProps {
  isLoading: boolean
  children: React.ReactNode
  className?: string
  text?: string
  progress?: number
  showProgress?: boolean
  variant?: SpinnerVariant
  backdrop?: 'light' | 'dark' | 'blur'
  size?: SpinnerSize
}

interface LoadingCardProps {
  title?: string
  description?: string
  progress?: number
  showProgress?: boolean
  variant?: SpinnerVariant
  size?: SpinnerSize
  className?: string
}

// Size classes for spinners
const sizeClasses: Record<SpinnerSize, string> = {
  xs: 'h-3 w-3',
  sm: 'h-4 w-4',
  md: 'h-6 w-6',
  lg: 'h-8 w-8',
  xl: 'h-12 w-12'
}

// Text size classes matching spinner sizes
const textSizeClasses: Record<SpinnerSize, string> = {
  xs: 'text-xs',
  sm: 'text-xs',
  md: 'text-sm',
  lg: 'text-base',
  xl: 'text-lg'
}

// Color classes using design tokens (no hardcoded colors)
const colorClasses: Record<SpinnerColor, string> = {
  primary: 'text-primary',
  secondary: 'text-secondary-foreground',
  muted: 'text-muted-foreground',
  destructive: 'text-destructive',
  success: 'text-green-600 dark:text-green-500'
}

// Bounce dot sizes for bounce variant
const bounceDotSizes: Record<SpinnerSize, string> = {
  xs: 'w-1 h-1',
  sm: 'w-1.5 h-1.5',
  md: 'w-2 h-2',
  lg: 'w-3 h-3',
  xl: 'w-4 h-4'
}

export function LoadingSpinner({
  size = 'md',
  className,
  text,
  overlay = false,
  color = 'primary',
  variant = 'circle',
  status = 'loading',
  showProgress = false,
  progress = 0,
  'aria-label': ariaLabel = 'Loading'
}: LoadingSpinnerProps) {
  // Handle status icons (success/error) first
  if (status === 'success') {
    return (
      <div className={cn('flex flex-col items-center justify-center gap-2', className)}>
        <CheckCircle className={cn(sizeClasses[size], 'text-green-600 dark:text-green-500')} />
        {text && <span className={cn('text-muted-foreground', textSizeClasses[size])}>{text}</span>}
      </div>
    )
  }

  if (status === 'error') {
    return (
      <div className={cn('flex flex-col items-center justify-center gap-2', className)}>
        <XCircle className={cn(sizeClasses[size], 'text-destructive')} />
        {text && <span className={cn('text-muted-foreground', textSizeClasses[size])}>{text}</span>}
      </div>
    )
  }

  // Get the appropriate spinner based on variant
  const getSpinnerElement = () => {
    switch (variant) {
      case 'refresh':
        return (
          <RefreshCw
            className={cn(sizeClasses[size], 'animate-spin', colorClasses[color])}
            aria-label={ariaLabel}
          />
        )

      case 'pulse':
        return (
          <div
            className={cn(sizeClasses[size], 'bg-primary rounded-full animate-pulse')}
            role="status"
            aria-label={ariaLabel}
          />
        )

      case 'bounce':
        return (
          <div className="flex space-x-1" role="status" aria-label={ariaLabel}>
            {[...Array(3)].map((_, i) => (
              <div
                key={i}
                className={cn(
                  bounceDotSizes[size],
                  'bg-primary rounded-full animate-bounce'
                )}
                style={{ animationDelay: `${i * 0.1}s` }}
              />
            ))}
          </div>
        )

      case 'spinner':
        return (
          <Loader2
            className={cn(sizeClasses[size], 'animate-spin', colorClasses[color])}
            aria-label={ariaLabel}
          />
        )

      case 'circle':
      default:
        return (
          <svg
            role="status"
            aria-label={ariaLabel}
            className={cn(
              'animate-spin',
              sizeClasses[size],
              colorClasses[color],
              className
            )}
            viewBox="0 0 24 24"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            style={{ willChange: 'transform' }}
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
        )
    }
  }

  const spinnerElement = getSpinnerElement()

  // Progress bar component
  const progressBar = showProgress && (
    <div className="w-full max-w-xs">
      <div className="flex justify-between text-xs text-muted-foreground mb-1">
        <span>Progress</span>
        <span>{Math.round(progress)}%</span>
      </div>
      <div className="w-full bg-muted rounded-full h-2">
        <div
          className="bg-primary h-2 rounded-full transition-all duration-300 ease-out"
          style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
        />
      </div>
    </div>
  )

  // Overlay mode - full screen with backdrop
  if (overlay) {
    return (
      <div className="fixed inset-0 bg-background/80 backdrop-blur-sm z-50 flex items-center justify-center">
        <div className="bg-background rounded-lg p-6 shadow-lg border">
          <div className="flex flex-col items-center gap-3">
            {spinnerElement}
            {text && (
              <span className={cn('font-medium text-foreground', textSizeClasses[size])}>
                {text}
              </span>
            )}
            {progressBar}
          </div>
        </div>
      </div>
    )
  }

  // With text or progress - vertical layout
  if (text || showProgress) {
    return (
      <div className={cn('flex flex-col items-center justify-center gap-2', className)}>
        {spinnerElement}
        {text && (
          <span className={cn('text-muted-foreground text-center', textSizeClasses[size])}>
            {text}
          </span>
        )}
        {progressBar}
      </div>
    )
  }

  // Simple spinner only
  return spinnerElement
}

/**
 * LoadingOverlay - Wraps content with an optional loading overlay
 * Use isLoading to conditionally show the overlay
 */
export function LoadingOverlay({
  isLoading,
  children,
  className,
  text,
  progress,
  showProgress = false,
  variant = 'circle',
  backdrop = 'blur',
  size = 'lg'
}: LoadingOverlayProps) {
  const backdropClasses = {
    light: 'bg-background/80',
    dark: 'bg-background/90',
    blur: 'bg-background/60 backdrop-blur-sm'
  }

  return (
    <div className={cn('relative', className)}>
      {children}
      {isLoading && (
        <div
          className={cn(
            'absolute inset-0 flex items-center justify-center z-10',
            backdropClasses[backdrop]
          )}
        >
          <div className="bg-background rounded-lg shadow-lg p-6 max-w-sm w-full mx-4 border">
            <LoadingSpinner
              size={size}
              variant={variant}
              text={text}
              showProgress={showProgress}
              progress={progress}
            />
          </div>
        </div>
      )}
    </div>
  )
}

/**
 * LoadingCard - A card component with loading state
 */
export function LoadingCard({
  title = 'Processing...',
  description,
  progress = 0,
  showProgress = false,
  variant = 'circle',
  size = 'md',
  className
}: LoadingCardProps) {
  return (
    <div className={cn('bg-background rounded-lg border shadow-sm p-6', className)}>
      <div className="text-center space-y-4">
        <LoadingSpinner
          size={size}
          variant={variant}
          showProgress={showProgress}
          progress={progress}
        />
        <div>
          <h3 className="text-lg font-medium text-foreground">{title}</h3>
          {description && (
            <p className="text-sm text-muted-foreground mt-1">{description}</p>
          )}
        </div>
      </div>
    </div>
  )
}

/**
 * LoadingSkeleton - Base skeleton component for loading states
 */
export function LoadingSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn('animate-pulse bg-muted rounded', className)} />
  )
}

/**
 * LoadingTableRow - Skeleton row for tables
 */
export function LoadingTableRow({ columns = 4 }: { columns?: number }) {
  return (
    <tr>
      {[...Array(columns)].map((_, i) => (
        <td key={i} className="px-6 py-4">
          <LoadingSkeleton className="h-4 w-full" />
        </td>
      ))}
    </tr>
  )
}

/**
 * LoadingCardSkeleton - Skeleton for card content
 */
export function LoadingCardSkeleton() {
  return (
    <div className="bg-background rounded-lg border shadow-sm p-6 space-y-4">
      <LoadingSkeleton className="h-4 w-3/4" />
      <LoadingSkeleton className="h-3 w-full" />
      <LoadingSkeleton className="h-3 w-5/6" />
      <div className="flex space-x-2">
        <LoadingSkeleton className="h-8 w-20" />
        <LoadingSkeleton className="h-8 w-16" />
      </div>
    </div>
  )
}

/**
 * LoadingList - Skeleton list with avatar and text
 */
export function LoadingList({ items = 3 }: { items?: number }) {
  return (
    <div className="space-y-3">
      {[...Array(items)].map((_, i) => (
        <div key={i} className="flex items-center space-x-3 p-3 border rounded-lg">
          <LoadingSkeleton className="h-10 w-10 rounded-full" />
          <div className="flex-1 space-y-2">
            <LoadingSkeleton className="h-4 w-3/4" />
            <LoadingSkeleton className="h-3 w-1/2" />
          </div>
        </div>
      ))}
    </div>
  )
}

// Backward compatibility alias
export const LoadingCard_Skeleton = LoadingCardSkeleton

// Default export for compatibility
export default LoadingSpinner
