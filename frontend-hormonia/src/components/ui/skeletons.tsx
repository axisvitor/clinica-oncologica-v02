/**
 * Comprehensive Loading Skeleton Library
 *
 * Provides optimized skeleton components for better UX during loading states
 * with React 19 compatibility and performance optimizations
 */

import React, { memo } from 'react'
import { cn } from '@/lib/utils'
import { Skeleton } from '@/components/ui/skeleton'

// Base skeleton variants
interface SkeletonProps {
  className?: string
  animation?: 'pulse' | 'wave' | 'none'
  variant?: 'rounded' | 'circular' | 'rectangular'
  height?: number | string
  width?: number | string
}

const BaseSkeleton = memo<SkeletonProps>(({
  className,
  animation = 'pulse',
  variant = 'rounded',
  height,
  width,
  ...props
}) => {
  const baseClasses = 'bg-muted animate-pulse'
  const variantClasses = {
    rounded: 'rounded-md',
    circular: 'rounded-full',
    rectangular: 'rounded-none'
  }

  const animationClasses = {
    pulse: 'animate-pulse',
    wave: 'animate-pulse', // Can be enhanced with custom wave animation
    none: ''
  }

  return (
    <div
      className={cn(
        baseClasses,
        variantClasses[variant],
        animationClasses[animation],
        className
      )}
      style={{ height, width }}
      {...props}
    />
  )
})

BaseSkeleton.displayName = 'BaseSkeleton'

// Card skeleton
const CardSkeleton = memo<{ className?: string }>(({ className }) => (
  <div className={cn('border rounded-lg p-6 space-y-4', className)}>
    <div className="flex items-center space-x-4">
      <Skeleton className="h-12 w-12 rounded-full" />
      <div className="space-y-2 flex-1">
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-4 w-1/2" />
      </div>
    </div>
    <div className="space-y-2">
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-3/4" />
    </div>
    <div className="flex space-x-2">
      <Skeleton className="h-9 w-20" />
      <Skeleton className="h-9 w-20" />
    </div>
  </div>
))

CardSkeleton.displayName = 'CardSkeleton'

// Table skeleton
const TableSkeleton = memo<{
  rows?: number
  columns?: number
  className?: string
}>(({ rows = 5, columns = 4, className }) => (
  <div className={cn('space-y-4', className)}>
    {/* Table header */}
    <div className="flex space-x-4">
      {Array.from({ length: columns }, (_, i) => (
        <Skeleton key={`header-${i}`} className="h-10 flex-1" />
      ))}
    </div>

    {/* Table rows */}
    {Array.from({ length: rows }, (_, rowIndex) => (
      <div key={`row-${rowIndex}`} className="flex space-x-4">
        {Array.from({ length: columns }, (_, colIndex) => (
          <Skeleton
            key={`cell-${rowIndex}-${colIndex}`}
            className="h-12 flex-1"
          />
        ))}
      </div>
    ))}
  </div>
))

TableSkeleton.displayName = 'TableSkeleton'

// List skeleton
const ListSkeleton = memo<{
  items?: number
  showAvatar?: boolean
  className?: string
}>(({ items = 5, showAvatar = true, className }) => (
  <div className={cn('space-y-4', className)}>
    {Array.from({ length: items }, (_, i) => (
      <div key={`list-item-${i}`} className="flex items-center space-x-4">
        {showAvatar && <Skeleton className="h-10 w-10 rounded-full" />}
        <div className="space-y-2 flex-1">
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-3 w-1/2" />
        </div>
      </div>
    ))}
  </div>
))

ListSkeleton.displayName = 'ListSkeleton'

// Form skeleton
const FormSkeleton = memo<{
  fields?: number
  className?: string
}>(({ fields = 4, className }) => (
  <div className={cn('space-y-6', className)}>
    {Array.from({ length: fields }, (_, i) => (
      <div key={`field-${i}`} className="space-y-2">
        <Skeleton className="h-4 w-24" /> {/* Label */}
        <Skeleton className="h-10 w-full" /> {/* Input */}
      </div>
    ))}
    <div className="flex space-x-4">
      <Skeleton className="h-10 w-20" /> {/* Cancel button */}
      <Skeleton className="h-10 w-20" /> {/* Submit button */}
    </div>
  </div>
))

FormSkeleton.displayName = 'FormSkeleton'

// Dashboard stats skeleton
const StatsSkeleton = memo<{
  stats?: number
  className?: string
}>(({ stats = 4, className }) => (
  <div className={cn('grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4', className)}>
    {Array.from({ length: stats }, (_, i) => (
      <div key={`stat-${i}`} className="border rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-5 w-5" />
        </div>
        <Skeleton className="h-8 w-16 mb-2" />
        <div className="flex items-center justify-between">
          <Skeleton className="h-3 w-20" />
          <Skeleton className="h-3 w-12" />
        </div>
      </div>
    ))}
  </div>
))

StatsSkeleton.displayName = 'StatsSkeleton'

// Chart skeleton
const ChartSkeleton = memo<{
  height?: number | string
  className?: string
}>(({ height = 300, className }) => (
  <div className={cn('border rounded-lg p-6', className)}>
    <div className="flex items-center justify-between mb-6">
      <Skeleton className="h-6 w-32" /> {/* Title */}
      <Skeleton className="h-8 w-24" /> {/* Filter/Options */}
    </div>

    {/* Chart area */}
    <div className="relative" style={{ height }}>
      <Skeleton className="h-full w-full rounded" />

      {/* Chart elements overlay */}
      <div className="absolute inset-0 flex items-end justify-around p-4">
        {Array.from({ length: 6 }, (_, i) => (
          <Skeleton
            key={`bar-${i}`}
            className="w-8"
            style={{ height: `${Math.random() * 60 + 20}%` }}
          />
        ))}
      </div>
    </div>

    {/* Legend */}
    <div className="flex justify-center space-x-6 mt-4">
      <div className="flex items-center space-x-2">
        <Skeleton className="h-3 w-3 rounded-full" />
        <Skeleton className="h-3 w-16" />
      </div>
      <div className="flex items-center space-x-2">
        <Skeleton className="h-3 w-3 rounded-full" />
        <Skeleton className="h-3 w-16" />
      </div>
    </div>
  </div>
))

ChartSkeleton.displayName = 'ChartSkeleton'

// Navigation skeleton
const NavigationSkeleton = memo<{ className?: string }>(({ className }) => (
  <div className={cn('space-y-2', className)}>
    {Array.from({ length: 6 }, (_, i) => (
      <div key={`nav-${i}`} className="flex items-center space-x-3 p-2">
        <Skeleton className="h-5 w-5" /> {/* Icon */}
        <Skeleton className="h-4 w-24" /> {/* Label */}
      </div>
    ))}
  </div>
))

NavigationSkeleton.displayName = 'NavigationSkeleton'

// Header skeleton
const HeaderSkeleton = memo<{ className?: string }>(({ className }) => (
  <div className={cn('flex items-center justify-between p-4 border-b', className)}>
    <div className="flex items-center space-x-4">
      <Skeleton className="h-8 w-8" /> {/* Logo */}
      <Skeleton className="h-6 w-32" /> {/* Title */}
    </div>
    <div className="flex items-center space-x-4">
      <Skeleton className="h-9 w-9 rounded-full" /> {/* Notification */}
      <Skeleton className="h-9 w-9 rounded-full" /> {/* Settings */}
      <Skeleton className="h-8 w-8 rounded-full" /> {/* Avatar */}
    </div>
  </div>
))

HeaderSkeleton.displayName = 'HeaderSkeleton'

// Patient card skeleton (specific to oncology app)
const PatientCardSkeleton = memo<{ className?: string }>(({ className }) => (
  <div className={cn('border rounded-lg p-4 space-y-4', className)}>
    <div className="flex items-start justify-between">
      <div className="flex items-center space-x-3">
        <Skeleton className="h-12 w-12 rounded-full" /> {/* Avatar */}
        <div className="space-y-2">
          <Skeleton className="h-5 w-32" /> {/* Name */}
          <Skeleton className="h-3 w-24" /> {/* ID */}
        </div>
      </div>
      <Skeleton className="h-6 w-16 rounded-full" /> {/* Status badge */}
    </div>

    <div className="grid grid-cols-2 gap-4">
      <div className="space-y-1">
        <Skeleton className="h-3 w-16" /> {/* Label */}
        <Skeleton className="h-4 w-20" /> {/* Value */}
      </div>
      <div className="space-y-1">
        <Skeleton className="h-3 w-20" /> {/* Label */}
        <Skeleton className="h-4 w-24" /> {/* Value */}
      </div>
    </div>

    <div className="flex justify-between items-center pt-2 border-t">
      <Skeleton className="h-8 w-16" /> {/* Action button */}
      <Skeleton className="h-3 w-28" /> {/* Last update */}
    </div>
  </div>
))

PatientCardSkeleton.displayName = 'PatientCardSkeleton'

// Quiz skeleton (specific to oncology app)
const QuizSkeleton = memo<{ className?: string }>(({ className }) => (
  <div className={cn('border rounded-lg p-6 space-y-6', className)}>
    <div className="space-y-2">
      <Skeleton className="h-6 w-3/4" /> {/* Question */}
      <Skeleton className="h-4 w-1/2" /> {/* Description */}
    </div>

    <div className="space-y-3">
      {Array.from({ length: 4 }, (_, i) => (
        <div key={`option-${i}`} className="flex items-center space-x-3">
          <Skeleton className="h-4 w-4 rounded-full" /> {/* Radio */}
          <Skeleton className="h-4 w-48" /> {/* Option text */}
        </div>
      ))}
    </div>

    <div className="flex justify-between">
      <Skeleton className="h-9 w-20" /> {/* Previous button */}
      <Skeleton className="h-9 w-20" /> {/* Next button */}
    </div>
  </div>
))

QuizSkeleton.displayName = 'QuizSkeleton'

// Page skeleton wrapper
const PageSkeleton = memo<{
  children?: React.ReactNode
  className?: string
  showHeader?: boolean
  showNavigation?: boolean
}>(({ children, className, showHeader = true, showNavigation = false }) => (
  <div className={cn('min-h-screen bg-background', className)}>
    {showHeader && <HeaderSkeleton />}
    <div className="flex">
      {showNavigation && (
        <div className="w-64 border-r p-4">
          <NavigationSkeleton />
        </div>
      )}
      <div className="flex-1 p-6">
        {children}
      </div>
    </div>
  </div>
))

PageSkeleton.displayName = 'PageSkeleton'

// Export all skeletons
export {
  BaseSkeleton,
  CardSkeleton,
  TableSkeleton,
  ListSkeleton,
  FormSkeleton,
  StatsSkeleton,
  ChartSkeleton,
  NavigationSkeleton,
  HeaderSkeleton,
  PatientCardSkeleton,
  QuizSkeleton,
  PageSkeleton
}

// Utility for creating custom skeletons
export const createSkeleton = (config: {
  rows?: number
  columns?: number
  height?: number | string
  spacing?: string
}) => {
  const CustomSkeleton = memo<{ className?: string }>(({ className }) => (
    <div className={cn('space-y-4', className)}>
      {Array.from({ length: config.rows || 3 }, (_, rowIndex) => (
        <div key={rowIndex} className={cn('flex space-x-4', config.spacing)}>
          {Array.from({ length: config.columns || 1 }, (_, colIndex) => (
            <Skeleton
              key={colIndex}
              className="flex-1"
              style={{ height: config.height }}
            />
          ))}
        </div>
      ))}
    </div>
  ))

  CustomSkeleton.displayName = 'CustomSkeleton'
  return CustomSkeleton
}