import React from 'react'
import { Loader2, RefreshCw, CheckCircle, XCircle } from 'lucide-react'
import { cn } from '../../lib/utils'

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg' | 'xl'
  variant?: 'spinner' | 'refresh' | 'pulse' | 'bounce'
  status?: 'loading' | 'success' | 'error'
  text?: string
  className?: string
  showProgress?: boolean
  progress?: number
}

export function LoadingSpinner({
  size = 'md',
  variant = 'spinner',
  status = 'loading',
  text,
  className,
  showProgress = false,
  progress = 0
}: LoadingSpinnerProps) {
  const sizeClasses = {
    sm: 'w-4 h-4',
    md: 'w-6 h-6',
    lg: 'w-8 h-8',
    xl: 'w-12 h-12'
  }

  const textSizeClasses = {
    sm: 'text-xs',
    md: 'text-sm',
    lg: 'text-base',
    xl: 'text-lg'
  }

  const getIcon = () => {
    if (status === 'success') {
      return <CheckCircle className={cn(sizeClasses[size], 'text-green-500')} />
    }

    if (status === 'error') {
      return <XCircle className={cn(sizeClasses[size], 'text-red-500')} />
    }

    switch (variant) {
      case 'refresh':
        return <RefreshCw className={cn(sizeClasses[size], 'animate-spin text-blue-500')} />
      case 'pulse':
        return (
          <div className={cn(
            sizeClasses[size],
            'bg-blue-500 rounded-full animate-pulse'
          )} />
        )
      case 'bounce':
        return (
          <div className="flex space-x-1">
            {[...Array(3)].map((_, i) => (
              <div
                key={i}
                className={cn(
                  'w-2 h-2 bg-blue-500 rounded-full animate-bounce',
                  size === 'sm' && 'w-1.5 h-1.5',
                  size === 'lg' && 'w-3 h-3',
                  size === 'xl' && 'w-4 h-4'
                )}
                style={{
                  animationDelay: `${i * 0.1}s`
                }}
              />
            ))}
          </div>
        )
      default:
        return <Loader2 className={cn(sizeClasses[size], 'animate-spin text-blue-500')} />
    }
  }

  return (
    <div className={cn('flex flex-col items-center justify-center space-y-2', className)}>
      {getIcon()}

      {text && (
        <p className={cn(
          'text-gray-600 text-center',
          textSizeClasses[size]
        )}>
          {text}
        </p>
      )}

      {showProgress && status === 'loading' && (
        <div className="w-full max-w-xs">
          <div className="flex justify-between text-xs text-gray-500 mb-1">
            <span>Progresso</span>
            <span>{Math.round(progress)}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-blue-500 h-2 rounded-full transition-all duration-300 ease-out"
              style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
            />
          </div>
        </div>
      )}
    </div>
  )
}

interface LoadingOverlayProps {
  isVisible: boolean
  text?: string
  progress?: number
  showProgress?: boolean
  variant?: LoadingSpinnerProps['variant']
  backdrop?: 'light' | 'dark' | 'blur'
  size?: LoadingSpinnerProps['size']
}

export function LoadingOverlay({
  isVisible,
  text = 'Carregando...',
  progress = 0,
  showProgress = false,
  variant = 'spinner',
  backdrop = 'light',
  size = 'lg'
}: LoadingOverlayProps) {
  if (!isVisible) return null

  const backdropClasses = {
    light: 'bg-white/80',
    dark: 'bg-black/60',
    blur: 'bg-white/60 backdrop-blur-sm'
  }

  return (
    <div className={cn(
      'fixed inset-0 z-50 flex items-center justify-center',
      backdropClasses[backdrop]
    )}>
      <div className="bg-white rounded-lg shadow-lg p-6 max-w-sm w-full mx-4">
        <LoadingSpinner
          size={size}
          variant={variant}
          text={text}
          showProgress={showProgress}
          progress={progress}
        />
      </div>
    </div>
  )
}

interface LoadingCardProps {
  title?: string
  description?: string
  progress?: number
  showProgress?: boolean
  variant?: LoadingSpinnerProps['variant']
  size?: LoadingSpinnerProps['size']
  className?: string
}

export function LoadingCard({
  title = 'Processando...',
  description,
  progress = 0,
  showProgress = false,
  variant = 'spinner',
  size = 'md',
  className
}: LoadingCardProps) {
  return (
    <div className={cn(
      'bg-white rounded-lg border shadow-sm p-6',
      className
    )}>
      <div className="text-center space-y-4">
        <LoadingSpinner
          size={size}
          variant={variant}
          showProgress={showProgress}
          progress={progress}
        />

        <div>
          <h3 className="text-lg font-medium text-gray-900">{title}</h3>
          {description && (
            <p className="text-sm text-gray-600 mt-1">{description}</p>
          )}
        </div>
      </div>
    </div>
  )
}

// Skeleton loading components for different content types
export function LoadingSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn('animate-pulse bg-gray-200 rounded', className)} />
  )
}

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

export function LoadingCard_Skeleton() {
  return (
    <div className="bg-white rounded-lg border shadow-sm p-6 space-y-4">
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