import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'

/**
 * Skeleton loading component for the Alerts page.
 * Mirrors the page structure: Header + Stats + Filters + Alerts List
 */
export function AlertsSkeleton() {
    return (
        <div className="space-y-4 md:space-y-6">
            {/* Header */}
            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                <div>
                    <Skeleton className="h-8 w-32 mb-2" />
                    <Skeleton className="h-4 w-64" />
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                    <Skeleton className="h-9 w-24" />
                    <Skeleton className="h-9 w-24" />
                    <Skeleton className="h-6 w-32" />
                </div>
            </div>

            {/* Stats Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-6">
                {Array.from({ length: 4 }).map((_, i) => (
                    <Card key={i}>
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <Skeleton className="h-4 w-24" />
                            <Skeleton className="h-4 w-4" />
                        </CardHeader>
                        <CardContent>
                            <Skeleton className="h-8 w-12 mb-1" />
                            <Skeleton className="h-3 w-24" />
                        </CardContent>
                    </Card>
                ))}
            </div>

            {/* Filters Card */}
            <Card>
                <CardContent className="pt-4 md:pt-6 px-4 md:px-6">
                    <div className="space-y-4">
                        <div className="flex flex-col lg:flex-row items-stretch lg:items-center gap-3">
                            <Skeleton className="h-10 flex-1" />
                            <div className="flex gap-2">
                                <Skeleton className="h-9 w-24" />
                                <Skeleton className="h-9 w-20" />
                            </div>
                        </div>
                        {/* Filters Row */}
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 p-4 bg-gray-50 rounded-lg">
                            {Array.from({ length: 3 }).map((_, i) => (
                                <div key={i} className="space-y-2">
                                    <Skeleton className="h-4 w-20" />
                                    <Skeleton className="h-10 w-full" />
                                </div>
                            ))}
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Alerts List */}
            <div className="space-y-3">
                <div className="flex items-center gap-3 px-2">
                    <Skeleton className="h-4 w-4" />
                    <Skeleton className="h-4 w-32" />
                </div>
                {Array.from({ length: 5 }).map((_, i) => (
                    <div key={i} className="flex items-start gap-3">
                        <div className="pt-6">
                            <Skeleton className="h-4 w-4" />
                        </div>
                        <Card className="flex-1">
                            <CardContent className="pt-4">
                                <div className="flex items-start justify-between">
                                    <div className="flex-1">
                                        <div className="flex items-center gap-2 mb-2">
                                            <Skeleton className="h-5 w-5 rounded-full" />
                                            <Skeleton className="h-5 w-40" />
                                            <Skeleton className="h-5 w-16" />
                                        </div>
                                        <Skeleton className="h-4 w-full mb-2" />
                                        <Skeleton className="h-4 w-3/4" />
                                        <div className="flex items-center gap-4 mt-3">
                                            <Skeleton className="h-4 w-24" />
                                            <Skeleton className="h-4 w-20" />
                                        </div>
                                    </div>
                                    <div className="flex gap-2">
                                        <Skeleton className="h-8 w-24" />
                                        <Skeleton className="h-8 w-20" />
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    </div>
                ))}
            </div>
        </div>
    )
}
