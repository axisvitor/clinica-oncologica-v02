import React, { Suspense, ReactElement } from 'react';
import { ResponsiveContainer } from 'recharts';
import { useChartDimensions } from '@/hooks/useChartDimensions';
import { ChartSkeleton } from '@/components/ui/chart-skeleton';

interface SafeChartContainerProps {
    children: ReactElement;
    height: string | number;
    className?: string;
    /** Fallback to show while waiting for valid dimensions */
    fallback?: React.ReactNode;
    /** Minimum width in pixels before rendering chart (default: 50) */
    minWidth?: number;
    /** Minimum height in pixels before rendering chart (default: 50) */
    minHeight?: number;
}

/**
 * A wrapper component that prevents Recharts width(0)/height(0) warnings.
 * It only renders the chart after the container has valid dimensions.
 * 
 * Usage:
 * ```tsx
 * <SafeChartContainer height="300px">
 *   <LineChart data={data}>
 *     <XAxis dataKey="name" />
 *     <Line dataKey="value" />
 *   </LineChart>
 * </SafeChartContainer>
 * ```
 */
export function SafeChartContainer({
    children,
    height,
    className = '',
    fallback,
    minWidth = 50,
    minHeight = 50,
}: SafeChartContainerProps) {
    const { ref, isReady } = useChartDimensions(minWidth, minHeight);

    const heightStyle = typeof height === 'number' ? `${height}px` : height;
    const defaultFallback = <ChartSkeleton height={heightStyle} />;

    return (
        <div
            ref={ref}
            className={`w-full min-w-0 ${className}`}
            style={{ height: heightStyle }}
        >
            {isReady ? (
                <Suspense fallback={fallback || defaultFallback}>
                    <ResponsiveContainer width="100%" height="100%" minWidth={minWidth} minHeight={minHeight}>
                        {children}
                    </ResponsiveContainer>
                </Suspense>
            ) : (
                fallback || defaultFallback
            )}
        </div>
    );
}

export default SafeChartContainer;
