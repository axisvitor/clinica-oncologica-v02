import { useState, useEffect, useRef, useCallback } from 'react';

interface ContainerDimensions {
    width: number;
    height: number;
    isReady: boolean;
}

/**
 * Hook that tracks container dimensions and returns isReady when dimensions are valid.
 * This prevents Recharts from showing width(0)/height(0) warnings during initial mount.
 * 
 * Usage:
 * ```tsx
 * const { ref, isReady } = useChartDimensions();
 * return (
 *   <div ref={ref} className="h-[300px] w-full">
 *     {isReady && (
 *       <ResponsiveContainer width="100%" height="100%">
 *         <LineChart data={data}>...</LineChart>
 *       </ResponsiveContainer>
 *     )}
 *   </div>
 * );
 * ```
 */
export function useChartDimensions(minWidth = 50, minHeight = 50): {
    ref: React.RefObject<HTMLDivElement | null>;
    dimensions: ContainerDimensions;
    isReady: boolean;
} {
    const ref = useRef<HTMLDivElement>(null);
    const [dimensions, setDimensions] = useState<ContainerDimensions>({
        width: 0,
        height: 0,
        isReady: false,
    });

    const updateDimensions = useCallback(() => {
        if (ref.current) {
            const { offsetWidth, offsetHeight } = ref.current;
            const isReady = offsetWidth >= minWidth && offsetHeight >= minHeight;
            setDimensions({
                width: offsetWidth,
                height: offsetHeight,
                isReady,
            });
        }
    }, [minWidth, minHeight]);

    useEffect(() => {
        // Double RAF technique: ensures paint is complete before measuring
        // This prevents Recharts from rendering before the container has valid dimensions
        let rafId1: number;
        let rafId2: number;
        let timerId: ReturnType<typeof setTimeout>;

        const measureDimensions = () => {
            rafId1 = requestAnimationFrame(() => {
                rafId2 = requestAnimationFrame(() => {
                    updateDimensions();
                });
            });
        };

        // Initial measurement after mount with small delay
        timerId = setTimeout(measureDimensions, 10);

        // ResizeObserver for subsequent changes
        const resizeObserver = new ResizeObserver(() => {
            updateDimensions();
        });

        if (ref.current) {
            resizeObserver.observe(ref.current);
        }

        return () => {
            clearTimeout(timerId);
            cancelAnimationFrame(rafId1);
            cancelAnimationFrame(rafId2);
            resizeObserver.disconnect();
        };
    }, [updateDimensions]);

    return { ref, dimensions, isReady: dimensions.isReady };
}

export default useChartDimensions;
