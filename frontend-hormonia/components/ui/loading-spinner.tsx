import React from 'react'
import { cn } from '@/lib/utils'

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg' | 'xl'
  className?: string
  text?: string
  overlay?: boolean
  color?: 'primary' | 'secondary' | 'muted'
  'aria-label'?: string
}

interface LoadingOverlayProps {
  isLoading: boolean
  children: React.ReactNode
  className?: string
}

export function LoadingSpinner({
  size = 'md',
  className,
  text,
  overlay = false,
  color = 'muted',
  'aria-label': ariaLabel = 'Loading'
}: LoadingSpinnerProps) {
  const sizeClasses = {
    sm: 'h-4 w-4',
    md: 'h-6 w-6',
    lg: 'h-8 w-8',
    xl: 'h-12 w-12'
  }

  const colorClasses = {
    primary: 'text-primary',
    secondary: 'text-secondary',
    muted: 'text-muted-foreground'
  }

  const spinner = (
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
    >
      <circle
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="2"
        strokeDasharray="31.416"
        strokeDashoffset="31.416"
        fill="none"
        strokeLinecap="round"
        className="opacity-25"
      />
      <path
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
        className="opacity-75"
      />
    </svg>
  )

  if (overlay) {
    return (
      <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center">
        <div className="bg-background rounded-lg p-6 shadow-lg">
          {text ? (
            <div className="flex items-center gap-3">
              {spinner}
              <span className="text-sm font-medium">{text}</span>
            </div>
          ) : (
            spinner
          )}
        </div>
      </div>
    )
  }

  if (text) {
    return (
      <div className="flex items-center gap-2">
        {spinner}
        <span className="text-sm font-medium">{text}</span>
      </div>
    )
  }

  return spinner
}

export function LoadingOverlay({ isLoading, children, className }: LoadingOverlayProps) {
  return (
    <div className={cn('relative', className)}>
      {children}
      {isLoading && (
        <div className="absolute inset-0 bg-background/80 backdrop-blur-sm flex items-center justify-center z-10">
          <LoadingSpinner size="lg" />
        </div>
      )}
    </div>
  )
}

// Default export for compatibility
export default LoadingSpinner