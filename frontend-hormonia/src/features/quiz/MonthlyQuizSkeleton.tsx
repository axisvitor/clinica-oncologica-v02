import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'

/**
 * Skeleton loading component for the Monthly Quiz Dashboard page.
 * Mirrors the page structure: Header + Stats + Completion Rate + Links Table
 */
export function MonthlyQuizSkeleton() {
    return (
        <div className="space-y-4 sm:space-y-6 px-3 sm:px-4 lg:px-6 py-4 sm:py-6">
            {/* Header */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
                <div>
                    <Skeleton className="h-8 w-40 mb-2" />
                    <Skeleton className="h-4 w-64" />
                </div>
            </div>

            {/* Metrics Cards */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-6">
                {Array.from({ length: 4 }).map((_, i) => (
                    <Card key={i}>
                        <CardContent className="p-4 sm:pt-6 sm:px-6">
                            <div className="flex flex-col sm:flex-row items-start sm:items-center sm:justify-between gap-3">
                                <div className="flex-1">
                                    <Skeleton className="h-4 w-24 mb-2" />
                                    <Skeleton className="h-8 w-16" />
                                </div>
                                <Skeleton className="h-10 w-10 sm:h-12 sm:w-12 rounded-lg" />
                            </div>
                        </CardContent>
                    </Card>
                ))}
            </div>

            {/* Completion Rate Card */}
            <Card>
                <CardHeader className="px-4 sm:px-6">
                    <div className="flex items-center">
                        <Skeleton className="h-5 w-5 mr-2" />
                        <Skeleton className="h-5 w-40" />
                    </div>
                </CardHeader>
                <CardContent className="px-4 sm:px-6">
                    <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
                        <Skeleton className="h-10 w-20" />
                        <div className="flex-1 w-full">
                            <Skeleton className="h-4 w-full rounded-full" />
                            <Skeleton className="h-3 w-48 mt-2" />
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Active Links Card */}
            <Card>
                <CardHeader className="px-4 sm:px-6">
                    <Skeleton className="h-5 w-28 mb-1" />
                    <Skeleton className="h-4 w-56" />
                </CardHeader>
                <CardContent className="px-0 sm:px-6">
                    {/* Table Header */}
                    <div className="flex items-center gap-4 py-3 px-4 border-b bg-gray-50">
                        <Skeleton className="h-4 w-32" />
                        <Skeleton className="h-4 w-24 hidden sm:block" />
                        <Skeleton className="h-4 w-20 hidden md:block" />
                        <Skeleton className="h-4 w-20 hidden lg:block" />
                        <Skeleton className="h-4 w-16" />
                        <Skeleton className="h-4 w-16 ml-auto" />
                    </div>
                    {/* Table Rows */}
                    {Array.from({ length: 5 }).map((_, i) => (
                        <div key={i} className="flex items-center gap-4 py-4 px-4 border-b last:border-0">
                            <div className="flex-1 min-w-[150px]">
                                <Skeleton className="h-4 w-32 mb-1" />
                                <Skeleton className="h-3 w-20 sm:hidden" />
                            </div>
                            <Skeleton className="h-5 w-20 hidden sm:block" />
                            <Skeleton className="h-4 w-20 hidden md:block" />
                            <Skeleton className="h-4 w-20 hidden lg:block" />
                            <Skeleton className="h-6 w-16" />
                            <Skeleton className="h-8 w-20" />
                        </div>
                    ))}
                </CardContent>
            </Card>
        </div>
    )
}
