import React, { useState } from 'react'
import { Button } from './button'
import {
  PatientCardSkeleton,
  TableSkeleton,
  PatientListSkeleton,
  MetricCardSkeleton,
  ListSkeleton,
  TextSkeleton,
  AvatarSkeleton,
  BadgeSkeleton
} from './skeleton'

/**
 * Demo component to showcase the enhanced skeleton system
 * This demonstrates how to use skeletons for loading states
 */

export function SkeletonDemo() {
  const [loading, setLoading] = useState(false)
  const [demoType, setDemoType] = useState<string>('patient-cards')

  const simulateLoading = () => {
    setLoading(true)
    setTimeout(() => setLoading(false), 3000) // 3 second demo
  }

  const demoTypes = [
    { key: 'patient-cards', label: 'Patient Cards' },
    { key: 'patient-table', label: 'Patient Table' },
    { key: 'dashboard', label: 'Dashboard' },
    { key: 'patient-list', label: 'Patient List' },
    { key: 'metrics', label: 'Metrics Cards' },
    { key: 'mixed', label: 'Mixed Components' }
  ]

  const renderSkeletonDemo = () => {
    if (!loading) {
      return (
        <div className="text-center py-12">
          <p className="text-gray-500 mb-4">Click "Start Loading Demo" to see the skeletons in action</p>
          <Button onClick={simulateLoading}>Start Loading Demo</Button>
        </div>
      )
    }

    switch (demoType) {
      case 'patient-cards':
        return (
          <div className="space-y-4">
            <h3 className="text-lg font-semibold">Patient Cards Loading...</h3>
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
              <PatientCardSkeleton />
              <PatientCardSkeleton />
              <PatientCardSkeleton />
              <PatientCardSkeleton />
              <PatientCardSkeleton />
              <PatientCardSkeleton />
            </div>
          </div>
        )

      case 'patient-table':
        return (
          <div className="space-y-4">
            <h3 className="text-lg font-semibold">Patient Table Loading...</h3>
            <TableSkeleton rows={8} columns={7} />
          </div>
        )

      case 'dashboard':
        return (
          <div className="space-y-6">
            <div className="space-y-2">
              <TextSkeleton className="w-80" size="lg" />
              <TextSkeleton className="w-64" />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <MetricCardSkeleton />
              <MetricCardSkeleton />
              <MetricCardSkeleton />
              <MetricCardSkeleton />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="space-y-4">
                <TextSkeleton className="w-32" />
                <div className="h-64 bg-muted rounded-lg animate-pulse" />
              </div>
              <div className="space-y-4">
                <TextSkeleton className="w-40" />
                <TableSkeleton rows={5} columns={3} />
              </div>
            </div>
          </div>
        )

      case 'patient-list':
        return (
          <div className="space-y-4">
            <h3 className="text-lg font-semibold">Patient List Loading...</h3>
            <PatientListSkeleton items={9} />
          </div>
        )

      case 'metrics':
        return (
          <div className="space-y-4">
            <h3 className="text-lg font-semibold">Metrics Dashboard Loading...</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <MetricCardSkeleton />
              <MetricCardSkeleton />
              <MetricCardSkeleton />
              <MetricCardSkeleton />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
              <MetricCardSkeleton />
              <MetricCardSkeleton />
            </div>
          </div>
        )

      case 'mixed':
        return (
          <div className="space-y-6">
            <div className="flex items-center space-x-4">
              <AvatarSkeleton size="xl" />
              <div className="space-y-2">
                <TextSkeleton className="w-64" size="lg" />
                <TextSkeleton className="w-48" />
              </div>
              <div className="ml-auto">
                <BadgeSkeleton />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <MetricCardSkeleton />
              <MetricCardSkeleton />
              <MetricCardSkeleton />
            </div>

            <ListSkeleton items={4} showAvatar={true} showBadge={true} />
          </div>
        )

      default:
        return null
    }
  }

  return (
    <div className="p-6 space-y-6">
      <div className="space-y-4">
        <h2 className="text-2xl font-bold">Enhanced Skeleton System Demo</h2>
        <p className="text-gray-600">
          This demo showcases the various skeleton components with different animations and variants.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        {demoTypes.map((demo) => (
          <Button
            key={demo.key}
            variant={demoType === demo.key ? 'default' : 'outline'}
            size="sm"
            onClick={() => setDemoType(demo.key)}
            disabled={loading}
          >
            {demo.label}
          </Button>
        ))}
      </div>

      {loading && (
        <div className="flex items-center justify-between bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-center space-x-2">
            <div className="w-4 h-4 bg-blue-600 rounded-full animate-pulse" />
            <span className="text-blue-800 font-medium">Loading simulation in progress...</span>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setLoading(false)}
          >
            Stop Demo
          </Button>
        </div>
      )}

      <div className="border rounded-lg p-6 min-h-[400px]">
        {renderSkeletonDemo()}
      </div>

      <div className="bg-gray-50 rounded-lg p-4 space-y-2">
        <h4 className="font-semibold">Features Demonstrated:</h4>
        <ul className="text-sm text-gray-600 space-y-1">
          <li>• <strong>Multiple Animation Types:</strong> Pulse, Wave, and Shimmer animations</li>
          <li>• <strong>Various Shapes:</strong> Rectangular, Rounded, and Circular skeletons</li>
          <li>• <strong>Size Variants:</strong> Small, Medium, Large, and Extra Large options</li>
          <li>• <strong>Specialized Components:</strong> Patient Cards, Tables, Lists, and Metrics</li>
          <li>• <strong>Responsive Design:</strong> Grid layouts that adapt to screen size</li>
          <li>• <strong>Design System Integration:</strong> Follows the existing UI component patterns</li>
        </ul>
      </div>
    </div>
  )
}

export default SkeletonDemo