'use client'

import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'

/**
 * Skeleton Loading UI for Quiz Interface
 *
 * Displays a structural preview of the quiz while content loads.
 * Improves perceived performance by showing the layout immediately.
 */
export function QuizSkeleton() {
  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-2xl mx-auto space-y-6">
        {/* Header Skeleton */}
        <div className="text-center space-y-2">
          <Skeleton className="h-8 w-48 mx-auto" />
          <Skeleton className="h-4 w-64 mx-auto" />
        </div>

        {/* Progress Bar Skeleton */}
        <div className="space-y-2">
          <div className="flex justify-between">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-4 w-16" />
          </div>
          <Skeleton className="h-2 w-full rounded-full" />
        </div>

        {/* Question Card Skeleton */}
        <Card className="p-6 space-y-6">
          <div className="space-y-4">
            {/* Question number and text */}
            <div className="flex items-start gap-3">
              <Skeleton className="w-8 h-8 rounded-full flex-shrink-0" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-5 w-full" />
                <Skeleton className="h-5 w-3/4" />
              </div>
            </div>

            {/* Answer options */}
            <div className="pl-11 space-y-3">
              {[1, 2, 3, 4].map((i) => (
                <Skeleton key={i} className="h-14 w-full rounded-xl" />
              ))}
            </div>
          </div>

          {/* Navigation buttons */}
          <div className="flex justify-between pt-4">
            <Skeleton className="h-10 w-24" />
            <Skeleton className="h-10 w-32" />
          </div>
        </Card>

        {/* Footer text */}
        <div className="text-center space-y-1">
          <Skeleton className="h-4 w-56 mx-auto" />
          <Skeleton className="h-3 w-40 mx-auto" />
        </div>
      </div>
    </div>
  )
}

export default QuizSkeleton
