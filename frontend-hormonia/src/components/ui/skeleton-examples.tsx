import React from 'react'
import {
  Skeleton,
  TextSkeleton,
  AvatarSkeleton,
  ButtonSkeleton,
  BadgeSkeleton,
  PatientCardSkeleton,
  TableSkeleton,
  ListSkeleton,
  PatientListSkeleton,
  MetricCardSkeleton
} from './skeleton'

/**
 * Skeleton Components Usage Examples
 *
 * This file demonstrates how to use the enhanced skeleton system
 * for the oncology clinic application.
 */

export function SkeletonExamples() {
  return (
    <div className="space-y-8 p-6">
      {/* Basic Skeleton Variants */}
      <section>
        <h2 className="text-xl font-semibold mb-4">Basic Skeleton Variants</h2>
        <div className="space-y-4">
          <div>
            <h3 className="text-sm font-medium mb-2">Sizes</h3>
            <div className="space-y-2">
              <Skeleton size="sm" className="w-32" />
              <Skeleton size="md" className="w-32" />
              <Skeleton size="lg" className="w-32" />
              <Skeleton size="xl" className="w-32" />
            </div>
          </div>

          <div>
            <h3 className="text-sm font-medium mb-2">Shapes</h3>
            <div className="flex space-x-4">
              <Skeleton shape="rectangular" className="w-16 h-16" />
              <Skeleton shape="rounded" className="w-16 h-16" />
              <Skeleton shape="circular" className="w-16 h-16" />
            </div>
          </div>

          <div>
            <h3 className="text-sm font-medium mb-2">Animations</h3>
            <div className="space-y-2">
              <Skeleton animation="pulse" className="w-48 h-4" />
              <Skeleton animation="wave" className="w-48 h-4" />
              <Skeleton animation="shimmer" className="w-48 h-4" />
            </div>
          </div>
        </div>
      </section>

      {/* Text Skeletons */}
      <section>
        <h2 className="text-xl font-semibold mb-4">Text Skeletons</h2>
        <div className="space-y-4">
          <div>
            <h3 className="text-sm font-medium mb-2">Single Line</h3>
            <TextSkeleton />
          </div>
          <div>
            <h3 className="text-sm font-medium mb-2">Multiple Lines</h3>
            <TextSkeleton lines={3} />
          </div>
          <div>
            <h3 className="text-sm font-medium mb-2">Different Sizes</h3>
            <div className="space-y-2">
              <TextSkeleton size="sm" />
              <TextSkeleton size="md" />
              <TextSkeleton size="lg" />
            </div>
          </div>
        </div>
      </section>

      {/* Component Skeletons */}
      <section>
        <h2 className="text-xl font-semibold mb-4">Component Skeletons</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <h3 className="text-sm font-medium mb-2">Avatar</h3>
            <div className="flex space-x-2">
              <AvatarSkeleton size="sm" />
              <AvatarSkeleton size="md" />
              <AvatarSkeleton size="lg" />
              <AvatarSkeleton size="xl" />
            </div>
          </div>
          <div>
            <h3 className="text-sm font-medium mb-2">Buttons</h3>
            <div className="space-y-2">
              <ButtonSkeleton size="sm" />
              <ButtonSkeleton size="md" />
              <ButtonSkeleton size="lg" />
            </div>
          </div>
          <div>
            <h3 className="text-sm font-medium mb-2">Badges</h3>
            <div className="space-y-2">
              <BadgeSkeleton />
              <BadgeSkeleton className="w-20" />
              <BadgeSkeleton className="w-24" />
            </div>
          </div>
          <div>
            <h3 className="text-sm font-medium mb-2">Metric Card</h3>
            <MetricCardSkeleton />
          </div>
        </div>
      </section>

      {/* Patient-Specific Skeletons */}
      <section>
        <h2 className="text-xl font-semibold mb-4">Patient-Specific Skeletons</h2>

        {/* Patient Card */}
        <div className="mb-6">
          <h3 className="text-lg font-medium mb-2">Patient Card</h3>
          <div className="max-w-md">
            <PatientCardSkeleton />
          </div>
        </div>

        {/* Patient List */}
        <div className="mb-6">
          <h3 className="text-lg font-medium mb-2">Patient List Grid</h3>
          <PatientListSkeleton items={6} />
        </div>
      </section>

      {/* Table Skeleton */}
      <section>
        <h2 className="text-xl font-semibold mb-4">Table Skeleton</h2>
        <div className="space-y-4">
          <div>
            <h3 className="text-sm font-medium mb-2">Patient Table</h3>
            <TableSkeleton rows={5} columns={7} />
          </div>
          <div>
            <h3 className="text-sm font-medium mb-2">Simple Table (No Header)</h3>
            <TableSkeleton rows={3} columns={4} showHeader={false} />
          </div>
        </div>
      </section>

      {/* List Skeleton */}
      <section>
        <h2 className="text-xl font-semibold mb-4">List Skeletons</h2>
        <div className="space-y-4">
          <div>
            <h3 className="text-sm font-medium mb-2">Simple List</h3>
            <ListSkeleton items={3} showAvatar={true} showBadge={false} />
          </div>
          <div>
            <h3 className="text-sm font-medium mb-2">List with Badges</h3>
            <ListSkeleton items={3} showAvatar={true} showBadge={true} />
          </div>
          <div>
            <h3 className="text-sm font-medium mb-2">List without Avatars</h3>
            <ListSkeleton items={3} showAvatar={false} showBadge={false} />
          </div>
        </div>
      </section>
    </div>
  )
}

/**
 * Usage Examples in Real Components
 */

// Loading state for PatientsPage
export function PatientsPageSkeleton() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <TextSkeleton className="w-48" size="lg" />
        <ButtonSkeleton />
      </div>

      {/* Filters */}
      <div className="flex space-x-4">
        <Skeleton className="h-10 w-48" shape="rounded" />
        <Skeleton className="h-10 w-32" shape="rounded" />
        <Skeleton className="h-10 w-24" shape="rounded" />
      </div>

      {/* Content */}
      <PatientListSkeleton items={9} />
    </div>
  )
}

// Loading state for PatientDetail
export function PatientDetailSkeleton() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center space-x-4">
        <AvatarSkeleton size="xl" />
        <div className="space-y-2">
          <TextSkeleton className="w-64" size="lg" />
          <TextSkeleton className="w-48" size="md" />
        </div>
        <div className="ml-auto">
          <BadgeSkeleton />
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <MetricCardSkeleton />
        <MetricCardSkeleton />
        <MetricCardSkeleton />
      </div>

      {/* Timeline */}
      <div className="space-y-4">
        <TextSkeleton className="w-32" />
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex space-x-4 p-4 border rounded-lg">
              <Skeleton className="w-2 h-16" shape="rounded" />
              <div className="flex-1 space-y-2">
                <TextSkeleton lines={2} />
                <TextSkeleton className="w-24" size="sm" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// Loading state for Dashboard
export function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      {/* Welcome message */}
      <div className="space-y-2">
        <TextSkeleton className="w-80" size="lg" />
        <TextSkeleton className="w-64" />
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCardSkeleton />
        <MetricCardSkeleton />
        <MetricCardSkeleton />
        <MetricCardSkeleton />
      </div>

      {/* Charts and tables */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-4">
          <TextSkeleton className="w-32" />
          <Skeleton className="h-64 w-full" shape="rounded" />
        </div>
        <div className="space-y-4">
          <TextSkeleton className="w-40" />
          <TableSkeleton rows={5} columns={3} />
        </div>
      </div>
    </div>
  )
}

export default SkeletonExamples