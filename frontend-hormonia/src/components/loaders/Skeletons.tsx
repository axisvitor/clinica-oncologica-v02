/**
 * Skeleton Components for Suspense Fallbacks
 *
 * Provides loading skeletons for different component types.
 * Optimized for performance and accessibility.
 *
 * Features:
 * - Semantic HTML with proper ARIA labels
 * - CSS-based animations (no JS)
 * - Responsive designs
 * - Dark mode support
 * - Reduced motion support
 *
 * Usage:
 * ```tsx
 * <Suspense fallback={<PageSkeleton />}>
 *   <LazyPage />
 * </Suspense>
 * ```
 */

import { cn } from '@/lib/utils'

interface SkeletonProps {
  className?: string
  'aria-label'?: string
}

/**
 * Base Skeleton Component
 */
export function Skeleton({ className, 'aria-label': ariaLabel, ...props }: SkeletonProps) {
  return (
    <div
      role="status"
      aria-label={ariaLabel || 'Carregando...'}
      className={cn(
        'animate-pulse rounded-md bg-muted',
        'motion-reduce:animate-none', // Respect reduced motion preference
        className
      )}
      {...props}
    />
  )
}

/**
 * Page-level Loading Skeleton
 * Full-screen centered spinner
 */
export function PageSkeleton() {
  return (
    <div
      role="status"
      aria-label="Carregando página..."
      className="min-h-screen flex items-center justify-center bg-background"
    >
      <div className="flex flex-col items-center gap-4">
        <div className="h-12 w-12 rounded-full border-4 border-primary border-t-transparent animate-spin" />
        <p className="text-sm text-muted-foreground">Carregando...</p>
      </div>
    </div>
  )
}

/**
 * Card Skeleton
 * For dashboard cards, stat cards, etc.
 */
export function CardSkeleton({ className }: SkeletonProps) {
  return (
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
  )
}

/**
 * Table Skeleton
 * For data tables and lists
 */
export function TableSkeleton({ rows = 5, columns = 4 }: { rows?: number; columns?: number }) {
  return (
    <div role="status" aria-label="Carregando tabela..." className="space-y-3">
      {/* Table header */}
      <div className="flex gap-4 pb-3 border-b">
        {Array.from({ length: columns }).map((_, i) => (
          <Skeleton key={`header-${i}`} className="h-4 flex-1" />
        ))}
      </div>

      {/* Table rows */}
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <div key={`row-${rowIndex}`} className="flex gap-4 py-2">
          {Array.from({ length: columns }).map((_, colIndex) => (
            <Skeleton key={`cell-${rowIndex}-${colIndex}`} className="h-4 flex-1" />
          ))}
        </div>
      ))}
    </div>
  )
}

/**
 * Chart Skeleton
 * For data visualization components
 */
export function ChartSkeleton({ className }: SkeletonProps) {
  return (
    <div
      role="status"
      aria-label="Carregando gráfico..."
      className={cn('space-y-4', className)}
    >
      {/* Chart title */}
      <Skeleton className="h-6 w-48" />

      {/* Chart area */}
      <div className="relative w-full h-64 bg-muted/50 rounded-lg overflow-hidden">
        {/* Simulated chart bars */}
        <div className="absolute bottom-0 left-0 right-0 flex items-end justify-around gap-2 p-4">
          <Skeleton className="h-32 w-12" />
          <Skeleton className="h-40 w-12" />
          <Skeleton className="h-24 w-12" />
          <Skeleton className="h-48 w-12" />
          <Skeleton className="h-36 w-12" />
          <Skeleton className="h-44 w-12" />
        </div>
      </div>

      {/* Chart legend */}
      <div className="flex gap-4 justify-center">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-4 w-24" />
      </div>
    </div>
  )
}

/**
 * List Skeleton
 * For patient lists, message lists, etc.
 */
export function ListSkeleton({ items = 6 }: { items?: number }) {
  return (
    <div role="status" aria-label="Carregando lista..." className="space-y-3">
      {Array.from({ length: items }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 p-4 border rounded-lg">
          <Skeleton className="h-12 w-12 rounded-full" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-3 w-1/2" />
          </div>
          <Skeleton className="h-8 w-20" />
        </div>
      ))}
    </div>
  )
}

/**
 * Form Skeleton
 * For forms and input-heavy pages
 */
export function FormSkeleton({ fields = 4 }: { fields?: number }) {
  return (
    <div role="status" aria-label="Carregando formulário..." className="space-y-6">
      {Array.from({ length: fields }).map((_, i) => (
        <div key={i} className="space-y-2">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-10 w-full" />
        </div>
      ))}
      <div className="flex gap-4 pt-4">
        <Skeleton className="h-10 w-24" />
        <Skeleton className="h-10 w-24" />
      </div>
    </div>
  )
}

/**
 * Dashboard Skeleton
 * Complete dashboard layout skeleton
 */
export function DashboardSkeleton() {
  return (
    <div role="status" aria-label="Carregando dashboard..." className="space-y-6 p-6">
      {/* Page title */}
      <Skeleton className="h-8 w-48" />

      {/* Stats cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <CardSkeleton />
        <CardSkeleton />
        <CardSkeleton />
        <CardSkeleton />
      </div>

      {/* Charts section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="border rounded-lg p-6">
          <ChartSkeleton />
        </div>
        <div className="border rounded-lg p-6">
          <ChartSkeleton />
        </div>
      </div>

      {/* Recent activity table */}
      <div className="border rounded-lg p-6">
        <Skeleton className="h-6 w-48 mb-4" />
        <TableSkeleton rows={5} columns={4} />
      </div>
    </div>
  )
}

/**
 * Patient Detail Skeleton
 * For patient detail pages with tabs
 */
export function PatientDetailSkeleton() {
  return (
    <div role="status" aria-label="Carregando paciente..." className="space-y-6 p-6">
      {/* Patient header */}
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

      {/* Tabs */}
      <div className="flex gap-4 border-b">
        <Skeleton className="h-10 w-32" />
        <Skeleton className="h-10 w-32" />
        <Skeleton className="h-10 w-32" />
        <Skeleton className="h-10 w-32" />
      </div>

      {/* Tab content */}
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
  )
}

/**
 * Dialog/Modal Skeleton
 * For lazy-loaded dialogs
 */
export function DialogSkeleton() {
  return (
    <div role="status" aria-label="Carregando..." className="p-6 space-y-4">
      <Skeleton className="h-6 w-48 mb-4" />
      <FormSkeleton fields={3} />
    </div>
  )
}

/**
 * Sidebar Skeleton
 * For navigation sidebars
 */
export function SidebarSkeleton() {
  return (
    <div role="status" aria-label="Carregando menu..." className="space-y-4 p-4">
      {/* Logo */}
      <Skeleton className="h-12 w-32 mb-6" />

      {/* Menu items */}
      {Array.from({ length: 8 }).map((_, i) => (
        <div key={i} className="flex items-center gap-3">
          <Skeleton className="h-5 w-5" />
          <Skeleton className="h-4 flex-1" />
        </div>
      ))}
    </div>
  )
}

/**
 * Message Thread Skeleton
 * For chat/message interfaces
 */
export function MessageThreadSkeleton({ messages = 5 }: { messages?: number }) {
  return (
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
  )
}

/**
 * Calendar Skeleton
 * For calendar/scheduling components
 */
export function CalendarSkeleton() {
  return (
    <div role="status" aria-label="Carregando calendário..." className="space-y-4 p-4">
      {/* Calendar header */}
      <div className="flex justify-between items-center mb-4">
        <Skeleton className="h-8 w-48" />
        <div className="flex gap-2">
          <Skeleton className="h-8 w-8" />
          <Skeleton className="h-8 w-8" />
        </div>
      </div>

      {/* Days of week */}
      <div className="grid grid-cols-7 gap-2 mb-2">
        {Array.from({ length: 7 }).map((_, i) => (
          <Skeleton key={i} className="h-8 w-full" />
        ))}
      </div>

      {/* Calendar days */}
      <div className="grid grid-cols-7 gap-2">
        {Array.from({ length: 35 }).map((_, i) => (
          <Skeleton key={i} className="h-16 w-full" />
        ))}
      </div>
    </div>
  )
}

/**
 * Settings Page Skeleton
 */
export function SettingsSkeleton() {
  return (
    <div role="status" aria-label="Carregando configurações..." className="space-y-6 p-6">
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
  )
}

/**
 * Export all skeletons for easy importing
 */
export const Skeletons = {
  Base: Skeleton,
  Page: PageSkeleton,
  Card: CardSkeleton,
  Table: TableSkeleton,
  Chart: ChartSkeleton,
  List: ListSkeleton,
  Form: FormSkeleton,
  Dashboard: DashboardSkeleton,
  PatientDetail: PatientDetailSkeleton,
  Dialog: DialogSkeleton,
  Sidebar: SidebarSkeleton,
  MessageThread: MessageThreadSkeleton,
  Calendar: CalendarSkeleton,
  Settings: SettingsSkeleton,
}
