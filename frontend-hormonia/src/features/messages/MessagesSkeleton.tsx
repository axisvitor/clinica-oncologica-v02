import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'

/**
 * Skeleton loading component for the Messages page.
 * Mirrors the page structure: Header + 2-column layout (Patients + Messages)
 */
export function MessagesSkeleton() {
  return (
    <div className="space-y-4 md:space-y-6">
      {/* Header */}
      <div>
        <Skeleton className="h-8 w-40 mb-2" />
        <Skeleton className="h-4 w-56" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 md:gap-6 min-h-[calc(100dvh-10rem)] md:min-h-[calc(100dvh-12rem)]">
        {/* Patients List Sidebar */}
        <Card className="lg:col-span-1 flex flex-col max-h-[calc(100dvh-10rem)]">
          <CardHeader>
            <Skeleton className="h-5 w-24 mb-1" />
            <Skeleton className="h-4 w-52" />
          </CardHeader>
          <CardContent className="p-0">
            {/* Search */}
            <div className="p-4 border-b">
              <Skeleton className="h-10 w-full" />
            </div>
            {/* Patient List Items */}
            <div className="space-y-1 p-2">
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="flex items-center space-x-3 p-3 rounded-lg">
                  <Skeleton className="h-12 w-12 rounded-full flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1">
                      <Skeleton className="h-4 w-32" />
                      <Skeleton className="h-3 w-12" />
                    </div>
                    <Skeleton className="h-3 w-24 mb-1" />
                    <div className="flex items-center justify-between">
                      <Skeleton className="h-5 w-16" />
                      <Skeleton className="h-5 w-6" />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Messages Area */}
        <div className="lg:col-span-2 space-y-6">
          <Card className="h-full">
            <CardContent className="h-full flex items-center justify-center py-12">
              <div className="text-center">
                <Skeleton className="h-12 w-12 rounded-full mx-auto mb-4" />
                <Skeleton className="h-5 w-48 mx-auto mb-2" />
                <Skeleton className="h-4 w-64 mx-auto" />
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
