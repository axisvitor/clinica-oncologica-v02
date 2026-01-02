import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'

/**
 * Skeleton loading component for the Physician Dashboard page.
 * Mirrors the page structure: Header + Risk Cards + Alerts + Tabs + Table
 */
export function PhysicianDashboardSkeleton() {
    return (
        <div className="space-y-6 p-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <div className="flex items-center gap-2">
                        <Skeleton className="h-8 w-8" />
                        <Skeleton className="h-8 w-56" />
                    </div>
                    <Skeleton className="h-4 w-72 mt-2" />
                </div>
                <div className="flex items-center gap-3">
                    <Skeleton className="h-9 w-24" />
                    <Skeleton className="h-9 w-24" />
                    <Skeleton className="h-9 w-24" />
                </div>
            </div>

            {/* Risk Summary Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {Array.from({ length: 4 }).map((_, i) => (
                    <Card key={i}>
                        <CardContent className="pt-6">
                            <div className="flex items-center justify-between">
                                <div>
                                    <Skeleton className="h-4 w-20 mb-2" />
                                    <Skeleton className="h-8 w-12" />
                                </div>
                                <Skeleton className="h-10 w-10 rounded-lg" />
                            </div>
                        </CardContent>
                    </Card>
                ))}
            </div>

            {/* Tabs */}
            <div className="space-y-4">
                <div className="flex gap-2">
                    {['Pacientes', 'Insights IA', 'Analytics'].map((tab) => (
                        <Skeleton key={tab} className="h-9 w-24" />
                    ))}
                </div>

                {/* Search and Filters */}
                <Card>
                    <CardContent className="p-4">
                        <div className="flex flex-col sm:flex-row gap-4">
                            <Skeleton className="h-10 flex-1 max-w-md" />
                            <Skeleton className="h-10 w-44" />
                            <Skeleton className="h-9 w-32" />
                        </div>
                    </CardContent>
                </Card>

                {/* Patient Risk Table */}
                <Card>
                    <CardHeader>
                        <Skeleton className="h-5 w-40 mb-1" />
                        <Skeleton className="h-4 w-64" />
                    </CardHeader>
                    <CardContent>
                        {/* Table Header */}
                        <div className="flex items-center gap-4 py-3 border-b bg-gray-50 px-4">
                            <Skeleton className="h-4 w-40" />
                            <Skeleton className="h-4 w-24" />
                            <Skeleton className="h-4 w-20" />
                            <Skeleton className="h-4 w-24" />
                            <Skeleton className="h-4 w-16 ml-auto" />
                        </div>
                        {/* Table Rows */}
                        {Array.from({ length: 6 }).map((_, i) => (
                            <div key={i} className="flex items-center gap-4 py-4 px-4 border-b last:border-0">
                                <div className="flex items-center gap-3 flex-1">
                                    <Skeleton className="h-10 w-10 rounded-full" />
                                    <div>
                                        <Skeleton className="h-4 w-32 mb-1" />
                                        <Skeleton className="h-3 w-24" />
                                    </div>
                                </div>
                                <Skeleton className="h-6 w-16" />
                                <Skeleton className="h-4 w-12" />
                                <Skeleton className="h-4 w-32" />
                                <Skeleton className="h-8 w-20" />
                            </div>
                        ))}
                        {/* Pagination */}
                        <div className="flex items-center justify-between mt-4 px-4">
                            <Skeleton className="h-4 w-40" />
                            <div className="flex gap-2">
                                <Skeleton className="h-8 w-20" />
                                <Skeleton className="h-8 w-20" />
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    )
}
