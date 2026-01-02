/**
 * Comprehensive Skeleton Component Library
 *
 * Consolidated skeleton components for loading states with:
 * - Base Skeleton with variants (pulse, wave, shimmer)
 * - Domain-specific skeletons (Patient, Quiz, Dashboard)
 * - Layout skeletons (Page, Table, List, Form)
 * - Accessibility support (ARIA labels, reduced motion)
 *
 * Usage:
 * ```tsx
 * import { Skeleton, TableSkeleton, PatientCardSkeleton } from '@/components/ui/skeleton'
 *
 * <Suspense fallback={<PageSkeleton />}>
 *   <LazyPage />
 * </Suspense>
 * ```
 */

import * as React from "react"
import { memo } from "react"
import { cn } from "@/lib/utils"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"

// ============================================================================
// Base Skeleton Component
// ============================================================================

interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'card' | 'table' | 'list' | 'form' | 'chart'
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl' | '2xl'
  shape?: 'rectangular' | 'circular' | 'rounded' | 'pill'
  animation?: 'pulse' | 'wave' | 'shimmer' | 'breathing' | 'none'
  intensity?: 'subtle' | 'normal' | 'strong'
  'aria-label'?: string
}

function Skeleton({
  className,
  variant: _variant = 'default',
  size = 'md',
  shape = 'rectangular',
  animation = 'pulse',
  intensity = 'normal',
  'aria-label': ariaLabel,
  ...props
}: SkeletonProps) {
  const baseClasses = "bg-muted"

  const sizeClasses = {
    xs: "h-3",
    sm: "h-4",
    md: "h-6",
    lg: "h-8",
    xl: "h-12",
    "2xl": "h-16"
  }

  const shapeClasses = {
    rectangular: "rounded-none",
    circular: "rounded-full",
    rounded: "rounded-md",
    pill: "rounded-full"
  }

  const animationClasses = {
    pulse: "animate-pulse motion-reduce:animate-none",
    wave: "animate-skeleton-wave motion-reduce:animate-none relative overflow-hidden bg-gradient-to-r from-muted via-muted/50 to-muted bg-[length:200%_100%]",
    shimmer: "animate-shimmer motion-reduce:animate-none bg-gradient-to-r from-muted via-muted/50 to-muted bg-[length:200%_100%]",
    breathing: "animate-breathing motion-reduce:animate-none",
    none: ""
  }

  const intensityClasses = {
    subtle: "opacity-60",
    normal: "opacity-80",
    strong: "opacity-100"
  }

  return (
    <div
      role="status"
      aria-label={ariaLabel || 'Carregando...'}
      className={cn(
        baseClasses,
        sizeClasses[size],
        shapeClasses[shape],
        animationClasses[animation],
        intensityClasses[intensity],
        className
      )}
      {...props}
    />
  )
}

// ============================================================================
// Text & Typography Skeletons
// ============================================================================

interface TextSkeletonProps {
  lines?: number
  className?: string
  size?: 'sm' | 'md' | 'lg'
  animation?: 'pulse' | 'wave' | 'shimmer'
}

function TextSkeleton({
  lines = 1,
  className,
  size = 'md',
  animation = 'shimmer'
}: TextSkeletonProps) {
  const heights = {
    sm: 'h-3',
    md: 'h-4',
    lg: 'h-5'
  }

  const widths = ['w-full', 'w-5/6', 'w-4/5', 'w-3/4', 'w-2/3']

  return (
    <div className={cn("space-y-2", className)}>
      {Array.from({ length: lines }).map((_, index) => (
        <Skeleton
          key={index}
          className={cn(
            heights[size],
            index === lines - 1 && lines > 1 ? widths[index % widths.length] : 'w-full'
          )}
          animation={animation}
          shape="rounded"
        />
      ))}
    </div>
  )
}

// ============================================================================
// UI Element Skeletons
// ============================================================================

function AvatarSkeleton({
  size = 'md',
  className
}: {
  size?: 'sm' | 'md' | 'lg' | 'xl'
  className?: string
}) {
  const sizes = {
    sm: 'h-6 w-6',
    md: 'h-8 w-8',
    lg: 'h-12 w-12',
    xl: 'h-16 w-16'
  }

  return (
    <Skeleton
      className={cn(sizes[size], className)}
      shape="circular"
      animation="shimmer"
    />
  )
}

function ButtonSkeleton({
  size = 'md',
  variant = 'default',
  className
}: {
  size?: 'sm' | 'md' | 'lg'
  variant?: 'default' | 'outline' | 'ghost'
  className?: string
}) {
  const sizes = {
    sm: 'h-8 w-16',
    md: 'h-10 w-20',
    lg: 'h-12 w-24'
  }

  const variants = {
    default: 'bg-muted',
    outline: 'bg-muted border border-muted-foreground/20',
    ghost: 'bg-muted/50'
  }

  return (
    <div
      className={cn(
        'rounded-md',
        sizes[size],
        variants[variant],
        'animate-pulse',
        className
      )}
    />
  )
}

function BadgeSkeleton({ className }: { className?: string }) {
  return (
    <Skeleton
      className={cn("h-5 w-16 rounded-full", className)}
      animation="shimmer"
    />
  )
}

// ============================================================================
// Card Skeletons
// ============================================================================

const CardSkeleton = memo<{ className?: string }>(({ className }) => (
  <div
    role="status"
    aria-label="Carregando card..."
    className={cn('p-6 border rounded-lg space-y-4 bg-card', className)}
  >
    <Skeleton className="h-4 w-3/4" />
    <Skeleton className="h-4 w-1/2" />
    <Skeleton className="h-8 w-full" />
    <div className="flex gap-2">
      <Skeleton className="h-6 w-20" />
      <Skeleton className="h-6 w-20" />
    </div>
  </div>
))

CardSkeleton.displayName = 'CardSkeleton'

function MetricCardSkeleton({ className }: { className?: string }) {
  return (
    <Card className={className}>
      <CardContent className="p-6">
        <div className="flex items-center justify-between">
          <div className="space-y-2">
            <Skeleton className="h-4 w-24" shape="rounded" animation="shimmer" />
            <Skeleton className="h-8 w-16" shape="rounded" animation="shimmer" />
          </div>
          <Skeleton className="h-8 w-8" shape="rounded" />
        </div>
        <div className="mt-4">
          <Skeleton className="h-3 w-32" shape="rounded" animation="shimmer" />
        </div>
      </CardContent>
    </Card>
  )
}

// ============================================================================
// Domain-Specific Skeletons
// ============================================================================

function PatientCardSkeleton({ className }: { className?: string }) {
  return (
    <Card className={cn("hover:shadow-md transition-shadow", className)}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center space-x-3">
            <AvatarSkeleton size="lg" />
            <div className="space-y-2">
              <Skeleton className="h-5 w-32" animation="shimmer" shape="rounded" />
              <Skeleton className="h-4 w-24" animation="shimmer" shape="rounded" />
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <BadgeSkeleton />
            <Skeleton className="h-8 w-8" shape="rounded" animation="pulse" />
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-center space-x-2">
          <Skeleton className="h-3 w-3" shape="rounded" />
          <Skeleton className="h-4 w-40" shape="rounded" animation="shimmer" />
        </div>
        <div className="flex items-center space-x-2">
          <Skeleton className="h-3 w-3" shape="rounded" />
          <Skeleton className="h-4 w-28" shape="rounded" animation="shimmer" />
        </div>
        <div className="flex items-center justify-between">
          <Skeleton className="h-4 w-20" shape="rounded" />
          <Skeleton className="h-4 w-8" shape="rounded" animation="shimmer" />
        </div>
        <div className="flex items-center justify-between">
          <Skeleton className="h-4 w-24" shape="rounded" />
          <Skeleton className="h-4 w-16" shape="rounded" animation="shimmer" />
        </div>
        <div className="flex space-x-2 pt-2">
          <ButtonSkeleton size="sm" className="flex-1" />
          <ButtonSkeleton size="sm" className="flex-1" />
        </div>
      </CardContent>
    </Card>
  )
}

function PatientListSkeleton({
  items = 8,
  className
}: {
  items?: number
  className?: string
}) {
  return (
    <div className={cn("grid gap-6 md:grid-cols-2 lg:grid-cols-3", className)}>
      {Array.from({ length: items }).map((_, index) => (
        <PatientCardSkeleton key={index} />
      ))}
    </div>
  )
}

const PatientDetailSkeleton = memo(() => (
  <div role="status" aria-label="Carregando paciente..." className="space-y-6 p-6">
    <div className="flex items-center gap-4 pb-6 border-b">
      <Skeleton className="h-20 w-20 rounded-full" />
      <div className="flex-1 space-y-2">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-48" />
        <div className="flex gap-2">
          <Skeleton className="h-6 w-24" />
          <Skeleton className="h-6 w-24" />
        </div>
      </div>
    </div>
    <div className="flex gap-4 border-b">
      <Skeleton className="h-10 w-32" />
      <Skeleton className="h-10 w-32" />
      <Skeleton className="h-10 w-32" />
      <Skeleton className="h-10 w-32" />
    </div>
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-2 space-y-6">
        <CardSkeleton />
        <CardSkeleton />
        <ListSkeleton items={4} />
      </div>
      <div className="space-y-6">
        <CardSkeleton />
        <CardSkeleton />
      </div>
    </div>
  </div>
))

PatientDetailSkeleton.displayName = 'PatientDetailSkeleton'

const QuizSkeleton = memo<{ className?: string }>(({ className }) => (
  <div className={cn('border rounded-lg p-6 space-y-6', className)}>
    <div className="space-y-2">
      <Skeleton className="h-6 w-3/4" />
      <Skeleton className="h-4 w-1/2" />
    </div>
    <div className="space-y-3">
      {Array.from({ length: 4 }, (_, i) => (
        <div key={`option-${i}`} className="flex items-center space-x-3">
          <Skeleton className="h-4 w-4 rounded-full" />
          <Skeleton className="h-4 w-48" />
        </div>
      ))}
    </div>
    <div className="flex justify-between">
      <Skeleton className="h-9 w-20" />
      <Skeleton className="h-9 w-20" />
    </div>
  </div>
))

QuizSkeleton.displayName = 'QuizSkeleton'

const TemplateCardSkeleton = memo(() => (
  <Card>
    <CardHeader>
      <div className="flex items-start justify-between">
        <div className="space-y-2">
          <Skeleton className="h-5 w-32" />
          <Skeleton className="h-4 w-24" />
        </div>
        <div className="flex gap-2">
          <Skeleton className="h-5 w-16" />
        </div>
      </div>
    </CardHeader>
    <CardContent>
      <div className="space-y-4">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-3/4" />
        <div className="space-y-2">
          <Skeleton className="h-3 w-20" />
          <Skeleton className="h-3 w-16" />
        </div>
        <div className="flex gap-2">
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
        </div>
      </div>
    </CardContent>
  </Card>
))

TemplateCardSkeleton.displayName = 'TemplateCardSkeleton'

// ============================================================================
// Table Skeletons
// ============================================================================

interface TableSkeletonProps {
  rows?: number
  columns?: number
  showHeader?: boolean
  className?: string
}

function TableSkeleton({
  rows = 5,
  columns = 6,
  showHeader = true,
  className
}: TableSkeletonProps) {
  const columnWidths = ['w-48', 'w-32', 'w-24', 'w-20', 'w-28', 'w-16']

  return (
    <div role="status" aria-label="Carregando tabela..." className={cn("space-y-4", className)}>
      <Table>
        {showHeader && (
          <TableHeader>
            <TableRow>
              {Array.from({ length: columns }).map((_, index) => (
                <TableHead key={index}>
                  <Skeleton
                    className="h-4 w-20"
                    shape="rounded"
                    animation="shimmer"
                  />
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
        )}
        <TableBody>
          {Array.from({ length: rows }).map((_, rowIndex) => (
            <TableRow key={rowIndex}>
              {Array.from({ length: columns }).map((_, colIndex) => (
                <TableCell key={colIndex}>
                  {colIndex === 0 ? (
                    <div className="flex items-center space-x-3">
                      <AvatarSkeleton size="sm" />
                      <div className="space-y-1">
                        <Skeleton className="h-4 w-32" shape="rounded" animation="shimmer" />
                        <Skeleton className="h-3 w-24" shape="rounded" animation="shimmer" />
                      </div>
                    </div>
                  ) : colIndex === columns - 1 ? (
                    <Skeleton className="h-8 w-8" shape="rounded" />
                  ) : colIndex === 3 ? (
                    <BadgeSkeleton />
                  ) : (
                    <Skeleton
                      className={cn(
                        "h-4",
                        columnWidths[colIndex] || "w-20"
                      )}
                      shape="rounded"
                      animation="shimmer"
                    />
                  )}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

// Simple table skeleton (for simpler use cases)
const SimpleTableSkeleton = memo<{ rows?: number; columns?: number }>(({ rows = 5, columns = 4 }) => (
  <div role="status" aria-label="Carregando tabela..." className="space-y-3">
    <div className="flex gap-4 pb-3 border-b">
      {Array.from({ length: columns }).map((_, i) => (
        <Skeleton key={`header-${i}`} className="h-4 flex-1" />
      ))}
    </div>
    {Array.from({ length: rows }).map((_, rowIndex) => (
      <div key={`row-${rowIndex}`} className="flex gap-4 py-2">
        {Array.from({ length: columns }).map((_, colIndex) => (
          <Skeleton key={`cell-${rowIndex}-${colIndex}`} className="h-4 flex-1" />
        ))}
      </div>
    ))}
  </div>
))

SimpleTableSkeleton.displayName = 'SimpleTableSkeleton'

// ============================================================================
// List Skeletons
// ============================================================================

interface ListSkeletonProps {
  items?: number
  showAvatar?: boolean
  showBadge?: boolean
  className?: string
}

function ListSkeleton({
  items = 5,
  showAvatar = true,
  showBadge = false,
  className
}: ListSkeletonProps) {
  return (
    <div role="status" aria-label="Carregando lista..." className={cn("space-y-4", className)}>
      {Array.from({ length: items }).map((_, index) => (
        <div key={index} className="flex items-center space-x-4 p-4 rounded-lg border">
          {showAvatar && <AvatarSkeleton size="md" />}
          <div className="flex-1 space-y-2">
            <div className="flex items-center justify-between">
              <Skeleton className="h-5 w-48" shape="rounded" animation="shimmer" />
              {showBadge && <BadgeSkeleton />}
            </div>
            <Skeleton className="h-4 w-64" shape="rounded" animation="shimmer" />
            <Skeleton className="h-3 w-32" shape="rounded" animation="shimmer" />
          </div>
          <div className="flex space-x-2">
            <ButtonSkeleton size="sm" />
            <Skeleton className="h-8 w-8" shape="rounded" />
          </div>
        </div>
      ))}
    </div>
  )
}

// ============================================================================
// Form Skeletons
// ============================================================================

const FormSkeleton = memo<{ fields?: number; className?: string }>(({ fields = 4, className }) => (
  <div role="status" aria-label="Carregando formulario..." className={cn('space-y-6', className)}>
    {Array.from({ length: fields }).map((_, i) => (
      <div key={`field-${i}`} className="space-y-2">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-10 w-full" />
      </div>
    ))}
    <div className="flex space-x-4">
      <Skeleton className="h-10 w-20" />
      <Skeleton className="h-10 w-20" />
    </div>
  </div>
))

FormSkeleton.displayName = 'FormSkeleton'

// ============================================================================
// Chart Skeletons
// ============================================================================

const ChartSkeleton = memo<{ className?: string; height?: number | string }>(({ className, height = 300 }) => (
  <div
    role="status"
    aria-label="Carregando grafico..."
    className={cn('space-y-4', className)}
  >
    <Skeleton className="h-6 w-48" />
    <div className="relative w-full h-64 bg-muted/50 rounded-lg overflow-hidden" style={{ height }}>
      <div className="absolute bottom-0 left-0 right-0 flex items-end justify-around gap-2 p-4">
        <Skeleton className="h-32 w-12" />
        <Skeleton className="h-40 w-12" />
        <Skeleton className="h-24 w-12" />
        <Skeleton className="h-48 w-12" />
        <Skeleton className="h-36 w-12" />
        <Skeleton className="h-44 w-12" />
      </div>
    </div>
    <div className="flex gap-4 justify-center">
      <Skeleton className="h-4 w-24" />
      <Skeleton className="h-4 w-24" />
      <Skeleton className="h-4 w-24" />
    </div>
  </div>
))

ChartSkeleton.displayName = 'ChartSkeleton'

// ============================================================================
// Dashboard Skeletons
// ============================================================================

const StatsSkeleton = memo<{ stats?: number; className?: string }>(({ stats = 4, className }) => (
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

const DashboardSkeleton = memo(() => (
  <div role="status" aria-label="Carregando dashboard..." className="space-y-6 p-6">
    <Skeleton className="h-8 w-48" />
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      <CardSkeleton />
      <CardSkeleton />
      <CardSkeleton />
      <CardSkeleton />
    </div>
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div className="border rounded-lg p-6">
        <ChartSkeleton />
      </div>
      <div className="border rounded-lg p-6">
        <ChartSkeleton />
      </div>
    </div>
    <div className="border rounded-lg p-6">
      <Skeleton className="h-6 w-48 mb-4" />
      <SimpleTableSkeleton rows={5} columns={4} />
    </div>
  </div>
))

DashboardSkeleton.displayName = 'DashboardSkeleton'

// ============================================================================
// Navigation Skeletons
// ============================================================================

const NavigationSkeleton = memo<{ className?: string }>(({ className }) => (
  <div className={cn('space-y-2', className)}>
    {Array.from({ length: 6 }, (_, i) => (
      <div key={`nav-${i}`} className="flex items-center space-x-3 p-2">
        <Skeleton className="h-5 w-5" />
        <Skeleton className="h-4 w-24" />
      </div>
    ))}
  </div>
))

NavigationSkeleton.displayName = 'NavigationSkeleton'

const HeaderSkeleton = memo<{ className?: string }>(({ className }) => (
  <div className={cn('flex items-center justify-between p-4 border-b', className)}>
    <div className="flex items-center space-x-4">
      <Skeleton className="h-8 w-8" />
      <Skeleton className="h-6 w-32" />
    </div>
    <div className="flex items-center space-x-4">
      <Skeleton className="h-9 w-9 rounded-full" />
      <Skeleton className="h-9 w-9 rounded-full" />
      <Skeleton className="h-8 w-8 rounded-full" />
    </div>
  </div>
))

HeaderSkeleton.displayName = 'HeaderSkeleton'

const SidebarSkeleton = memo(() => (
  <div role="status" aria-label="Carregando menu..." className="space-y-4 p-4">
    <Skeleton className="h-12 w-32 mb-6" />
    {Array.from({ length: 8 }).map((_, i) => (
      <div key={i} className="flex items-center gap-3">
        <Skeleton className="h-5 w-5" />
        <Skeleton className="h-4 flex-1" />
      </div>
    ))}
  </div>
))

SidebarSkeleton.displayName = 'SidebarSkeleton'

// ============================================================================
// Page-Level Skeletons
// ============================================================================

const PageSkeleton = memo<{
  children?: React.ReactNode
  className?: string
  showHeader?: boolean
  showNavigation?: boolean
}>(({ children, className, showHeader = true, showNavigation = false }) => (
  <div
    role="status"
    aria-label="Carregando pagina..."
    className={cn('min-h-screen bg-background', className)}
  >
    {showHeader && <HeaderSkeleton />}
    <div className="flex">
      {showNavigation && (
        <div className="w-64 border-r p-4">
          <NavigationSkeleton />
        </div>
      )}
      <div className="flex-1 p-6">
        {children || (
          <div className="space-y-6">
            <Skeleton className="h-8 w-48" />
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {Array.from({ length: 4 }, (_, i) => (
                <div key={i} className="h-32 bg-muted rounded-lg animate-pulse" />
              ))}
            </div>
            <div className="h-64 bg-muted rounded-lg animate-pulse" />
          </div>
        )}
      </div>
    </div>
  </div>
))

PageSkeleton.displayName = 'PageSkeleton'

// ============================================================================
// Communication Skeletons
// ============================================================================

const MessageThreadSkeleton = memo<{ messages?: number }>(({ messages = 5 }) => (
  <div role="status" aria-label="Carregando mensagens..." className="space-y-4 p-4">
    {Array.from({ length: messages }).map((_, i) => {
      const isRight = i % 2 === 0
      return (
        <div
          key={i}
          className={cn('flex gap-2', isRight ? 'justify-end' : 'justify-start')}
        >
          {!isRight && <Skeleton className="h-8 w-8 rounded-full flex-shrink-0" />}
          <div className={cn('space-y-2 max-w-[70%]', isRight && 'items-end')}>
            <Skeleton className="h-4 w-32" />
            <Skeleton className={cn('h-16 rounded-lg', isRight ? 'w-48' : 'w-64')} />
          </div>
          {isRight && <Skeleton className="h-8 w-8 rounded-full flex-shrink-0" />}
        </div>
      )
    })}
  </div>
))

MessageThreadSkeleton.displayName = 'MessageThreadSkeleton'

// ============================================================================
// Calendar Skeleton
// ============================================================================

const CalendarSkeleton = memo(() => (
  <div role="status" aria-label="Carregando calendario..." className="space-y-4 p-4">
    <div className="flex justify-between items-center mb-4">
      <Skeleton className="h-8 w-48" />
      <div className="flex gap-2">
        <Skeleton className="h-8 w-8" />
        <Skeleton className="h-8 w-8" />
      </div>
    </div>
    <div className="grid grid-cols-7 gap-2 mb-2">
      {Array.from({ length: 7 }).map((_, i) => (
        <Skeleton key={i} className="h-8 w-full" />
      ))}
    </div>
    <div className="grid grid-cols-7 gap-2">
      {Array.from({ length: 35 }).map((_, i) => (
        <Skeleton key={i} className="h-16 w-full" />
      ))}
    </div>
  </div>
))

CalendarSkeleton.displayName = 'CalendarSkeleton'

// ============================================================================
// Settings Skeleton
// ============================================================================

const SettingsSkeleton = memo(() => (
  <div role="status" aria-label="Carregando configuracoes..." className="space-y-6 p-6">
    <Skeleton className="h-8 w-48" />
    <div className="space-y-6">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="border rounded-lg p-6 space-y-4">
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-4 w-full max-w-2xl" />
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-6 w-12" />
            </div>
            <div className="flex items-center justify-between">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-6 w-12" />
            </div>
          </div>
        </div>
      ))}
    </div>
  </div>
))

SettingsSkeleton.displayName = 'SettingsSkeleton'

// ============================================================================
// Dialog Skeleton
// ============================================================================

const DialogSkeleton = memo(() => (
  <div role="status" aria-label="Carregando..." className="p-6 space-y-4">
    <Skeleton className="h-6 w-48 mb-4" />
    <FormSkeleton fields={3} />
  </div>
))

DialogSkeleton.displayName = 'DialogSkeleton'

// ============================================================================
// Utility for creating custom skeletons
// ============================================================================

// eslint-disable-next-line react-refresh/only-export-components
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

// ============================================================================
// Grouped Export for Named Imports
// ============================================================================

// eslint-disable-next-line react-refresh/only-export-components
export const Skeletons = {
  Base: Skeleton,
  Page: PageSkeleton,
  Card: CardSkeleton,
  Table: TableSkeleton,
  SimpleTable: SimpleTableSkeleton,
  Chart: ChartSkeleton,
  List: ListSkeleton,
  Form: FormSkeleton,
  Dashboard: DashboardSkeleton,
  PatientCard: PatientCardSkeleton,
  PatientDetail: PatientDetailSkeleton,
  PatientList: PatientListSkeleton,
  Quiz: QuizSkeleton,
  TemplateCard: TemplateCardSkeleton,
  Dialog: DialogSkeleton,
  Sidebar: SidebarSkeleton,
  MessageThread: MessageThreadSkeleton,
  Calendar: CalendarSkeleton,
  Settings: SettingsSkeleton,
  Navigation: NavigationSkeleton,
  Header: HeaderSkeleton,
  Stats: StatsSkeleton,
  Metric: MetricCardSkeleton,
  Avatar: AvatarSkeleton,
  Button: ButtonSkeleton,
  Badge: BadgeSkeleton,
  Text: TextSkeleton,
}

// ============================================================================
// Named Exports
// ============================================================================

export {
  Skeleton,
  TextSkeleton,
  AvatarSkeleton,
  ButtonSkeleton,
  BadgeSkeleton,
  CardSkeleton,
  MetricCardSkeleton,
  PatientCardSkeleton,
  PatientListSkeleton,
  PatientDetailSkeleton,
  QuizSkeleton,
  TemplateCardSkeleton,
  TableSkeleton,
  SimpleTableSkeleton,
  ListSkeleton,
  FormSkeleton,
  ChartSkeleton,
  StatsSkeleton,
  DashboardSkeleton,
  NavigationSkeleton,
  HeaderSkeleton,
  SidebarSkeleton,
  PageSkeleton,
  MessageThreadSkeleton,
  CalendarSkeleton,
  SettingsSkeleton,
  DialogSkeleton,
}
