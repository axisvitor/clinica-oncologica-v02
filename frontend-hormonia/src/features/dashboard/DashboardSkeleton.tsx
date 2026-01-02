import { memo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

/**
 * DashboardSkeleton - Skeleton UI for instant perceived loading
 * Shows the full dashboard structure with placeholder content
 */
export const DashboardSkeleton = memo(() => {
    return (
        <div className="space-y-4 md:space-y-6 animate-in fade-in duration-300">
            {/* Header Skeleton */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                    <div className="flex items-center gap-3">
                        <Skeleton className="h-8 w-40" />
                        <Skeleton className="h-6 w-20 hidden sm:block" />
                    </div>
                    <Skeleton className="h-4 w-56 mt-2" />
                </div>
                <div className="flex items-center gap-2">
                    <Skeleton className="h-6 w-28" />
                    <Skeleton className="h-9 w-20 hidden sm:block" />
                </div>
            </div>

            {/* Quick Stats Skeleton */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {Array.from({ length: 4 }, (_, i) => (
                    <Card key={i}>
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <Skeleton className="h-4 w-24" />
                            <Skeleton className="h-4 w-4 rounded" />
                        </CardHeader>
                        <CardContent>
                            <Skeleton className="h-8 w-16 mb-2" />
                            <div className="flex items-center justify-between">
                                <Skeleton className="h-3 w-20" />
                                <Skeleton className="h-3 w-12" />
                            </div>
                        </CardContent>
                    </Card>
                ))}
            </div>

            {/* Tabs Skeleton */}
            <div className="space-y-4">
                <div className="flex gap-2">
                    {['Visão Geral', 'Pacientes', 'Engajamento', 'Alertas'].map((tab) => (
                        <Skeleton key={tab} className="h-10 w-28" />
                    ))}
                </div>

                {/* Metrics Grid Skeleton */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 md:gap-6">
                    {Array.from({ length: 4 }, (_, i) => (
                        <Card key={i}>
                            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                                <Skeleton className="h-4 w-28" />
                                <Skeleton className="h-5 w-5 rounded" />
                            </CardHeader>
                            <CardContent>
                                <Skeleton className="h-10 w-20 mb-1" />
                                <Skeleton className="h-3 w-24" />
                            </CardContent>
                        </Card>
                    ))}
                </div>

                {/* Charts Skeleton */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 md:gap-6">
                    {/* Engagement Chart Skeleton */}
                    <Card>
                        <CardHeader>
                            <Skeleton className="h-5 w-40" />
                            <Skeleton className="h-4 w-60" />
                        </CardHeader>
                        <CardContent>
                            <Skeleton className="h-64 w-full" />
                        </CardContent>
                    </Card>

                    {/* Recent Activity Skeleton */}
                    <Card>
                        <CardHeader>
                            <Skeleton className="h-5 w-36" />
                        </CardHeader>
                        <CardContent className="space-y-4">
                            {Array.from({ length: 5 }, (_, i) => (
                                <div key={i} className="flex items-start gap-3">
                                    <Skeleton className="h-8 w-8 rounded-full" />
                                    <div className="flex-1 space-y-2">
                                        <Skeleton className="h-4 w-3/4" />
                                        <Skeleton className="h-3 w-1/2" />
                                    </div>
                                </div>
                            ))}
                        </CardContent>
                    </Card>
                </div>
            </div>
        </div>
    );
});

DashboardSkeleton.displayName = 'DashboardSkeleton';

export default DashboardSkeleton;
