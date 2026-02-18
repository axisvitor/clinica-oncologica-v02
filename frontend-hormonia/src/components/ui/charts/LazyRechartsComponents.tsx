/**
 * Recharts Lazy-Loaded Components
 *
 * LAZY LOADING STRATEGY (Updated 2025-01-25):
 * This module implements proper lazy loading for Recharts components to reduce
 * initial bundle size by ~100KB on pages that don't use charts.
 *
 * Why Lazy Loading:
 * 1. Performance: Reduces initial page load by ~100KB for non-chart pages
 * 2. Type Safety: Preserves full TypeScript types through ComponentProps
 * 3. User Experience: Shows skeleton while charts load
 * 4. Code Splitting: Browser loads charts only when needed
 *
 * Implementation Details:
 * - Heavy chart components (LineChart, BarChart, etc.) are lazy-loaded
 * - Lightweight components (XAxis, YAxis, etc.) use direct imports
 * - Full TypeScript support maintained via ComponentProps<typeof Component>
 * - ChartSkeleton provides loading feedback
 */

import React, { lazy, Suspense, ComponentProps } from 'react';

// ============================================================================
// TYPE DEFINITIONS (Using ComponentProps pattern)
// ============================================================================

/**
 * Extract component types using ComponentProps instead of direct imports
 * This avoids the "Module has no exported member" TypeScript errors
 */
type LineChartProps = ComponentProps<typeof import('recharts').LineChart>;
type AreaChartProps = ComponentProps<typeof import('recharts').AreaChart>;
type BarChartProps = ComponentProps<typeof import('recharts').BarChart>;
type PieChartProps = ComponentProps<typeof import('recharts').PieChart>;
type RadarChartProps = ComponentProps<typeof import('recharts').RadarChart>;
type RadialBarChartProps = ComponentProps<typeof import('recharts').RadialBarChart>;
type ScatterChartProps = ComponentProps<typeof import('recharts').ScatterChart>;
type ComposedChartProps = ComponentProps<typeof import('recharts').ComposedChart>;
type FunnelChartProps = ComponentProps<typeof import('recharts').FunnelChart>;
type TreemapProps = ComponentProps<typeof import('recharts').Treemap>;
type SankeyProps = ComponentProps<typeof import('recharts').Sankey>;

// ============================================================================
// TYPE-SAFE LAZY WRAPPER
// ============================================================================

/**
 * Type-safe lazy wrapper for Recharts components
 * Uses the ComponentProps-derived types for full type safety
 */
function createLazyChart<P extends object>(
  componentName: string
): React.LazyExoticComponent<React.ComponentType<P>> {
  return lazy(() =>
    import('recharts').then((module) => ({
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      default: (module as unknown as Record<string, React.ComponentType<any>>)[componentName] as React.ComponentType<P>
    }))
  );
}

// ============================================================================
// LAZY-LOADED CHART COMPONENTS (Heavy Components)
// ============================================================================

/**
 * Lazy-loaded LineChart component
 * Use with LazyChartWrapper to show loading skeleton
 */
export const LineChart = createLazyChart<LineChartProps>('LineChart');

/**
 * Lazy-loaded AreaChart component
 * Use with LazyChartWrapper to show loading skeleton
 */
export const AreaChart = createLazyChart<AreaChartProps>('AreaChart');

/**
 * Lazy-loaded BarChart component
 * Use with LazyChartWrapper to show loading skeleton
 */
export const BarChart = createLazyChart<BarChartProps>('BarChart');

/**
 * Lazy-loaded PieChart component
 * Use with LazyChartWrapper to show loading skeleton
 */
export const PieChart = createLazyChart<PieChartProps>('PieChart');

/**
 * Lazy-loaded RadarChart component
 * Use with LazyChartWrapper to show loading skeleton
 */
export const RadarChart = createLazyChart<RadarChartProps>('RadarChart');

/**
 * Lazy-loaded RadialBarChart component
 * Use with LazyChartWrapper to show loading skeleton
 */
export const RadialBarChart = createLazyChart<RadialBarChartProps>('RadialBarChart');

/**
 * Lazy-loaded ScatterChart component
 * Use with LazyChartWrapper to show loading skeleton
 */
export const ScatterChart = createLazyChart<ScatterChartProps>('ScatterChart');

/**
 * Lazy-loaded ComposedChart component
 * Use with LazyChartWrapper to show loading skeleton
 */
export const ComposedChart = createLazyChart<ComposedChartProps>('ComposedChart');

/**
 * Lazy-loaded FunnelChart component
 * Use with LazyChartWrapper to show loading skeleton
 */
export const FunnelChart = createLazyChart<FunnelChartProps>('FunnelChart');

/**
 * Lazy-loaded Treemap component
 * Use with LazyChartWrapper to show loading skeleton
 */
export const Treemap = createLazyChart<TreemapProps>('Treemap');

/**
 * Lazy-loaded Sankey component
 * Use with LazyChartWrapper to show loading skeleton
 */
export const Sankey = createLazyChart<SankeyProps>('Sankey');

// ============================================================================
// LOADING SKELETON AND SUSPENSE WRAPPER
// ============================================================================

/**
 * Loading skeleton displayed while chart components are being loaded
 *
 * @param height - Height of the skeleton (default: 300px)
 */
export const ChartSkeleton: React.FC<{ height?: number }> = ({ height = 300 }) => (
  <div
    className="animate-pulse bg-muted rounded-lg flex items-center justify-center"
    style={{ height }}
    role="status"
    aria-label="Carregando gráfico..."
  >
    <span className="text-muted-foreground text-sm">Carregando gráfico...</span>
  </div>
);

/**
 * Suspense wrapper for lazy-loaded chart components
 *
 * Automatically shows ChartSkeleton while the chart is loading.
 * Use this wrapper around any lazy-loaded chart component.
 *
 * @example
 * ```tsx
 * <LazyChartWrapper height={400}>
 *   <LineChart data={data} width={600} height={400}>
 *     <XAxis dataKey="name" />
 *     <YAxis />
 *     <Line type="monotone" dataKey="value" stroke="#8884d8" />
 *   </LineChart>
 * </LazyChartWrapper>
 * ```
 */
export const LazyChartWrapper: React.FC<{
  children: React.ReactNode;
  height?: number;
}> = ({ children, height }) => (
  <Suspense fallback={<ChartSkeleton height={height} />}>
    {children}
  </Suspense>
);

/**
 * ============================================================================
 * USAGE GUIDE
 * ============================================================================
 *
 * 1. BASIC USAGE (with lazy loading):
 *
 * ```tsx
 * import { LineChart, LazyChartWrapper } from '@/components/ui/charts/LazyRechartsComponents';
 * import { Line, XAxis, YAxis } from '@/components/ui/charts/RechartsPrimitives';
 *
 * function MyChart() {
 *   return (
 *     <LazyChartWrapper height={300}>
 *       <LineChart data={data} width={500} height={300}>
 *         <XAxis dataKey="name" />
 *         <YAxis />
 *         <Line type="monotone" dataKey="value" stroke="#8884d8" />
 *       </LineChart>
 *     </LazyChartWrapper>
 *   );
 * }
 * ```
 *
 * 2. MULTIPLE CHARTS:
 *
 * ```tsx
 * <div className="grid grid-cols-2 gap-4">
 *   <LazyChartWrapper height={300}>
 *     <BarChart data={data1} width={400} height={300}>
 *       <Bar dataKey="value" fill="#8884d8" />
 *     </BarChart>
 *   </LazyChartWrapper>
 *
 *   <LazyChartWrapper height={300}>
 *     <PieChart width={400} height={300}>
 *       <Pie data={data2} dataKey="value" />
 *     </PieChart>
 *   </LazyChartWrapper>
 * </div>
 * ```
 *
 * 3. CUSTOM LOADING STATE:
 *
 * ```tsx
 * <Suspense fallback={<CustomLoader />}>
 *   <LineChart data={data} width={500} height={300}>
 *     <Line type="monotone" dataKey="value" />
 *   </LineChart>
 * </Suspense>
 * ```
 *
 * ============================================================================
 * PERFORMANCE BENEFITS
 * ============================================================================
 *
 * - Initial bundle size reduction: ~100KB on pages without charts
 * - Charts load on-demand when first rendered
 * - Browser caches loaded charts for subsequent use
 * - Full TypeScript type checking maintained via ComponentProps
 * - Smooth loading experience with skeleton UI
 *
 * ============================================================================
 * TYPESCRIPT SUPPORT
 * ============================================================================
 *
 * All components maintain full type safety through ComponentProps pattern:
 *
 * ```tsx
 * // Props are fully typed via type inference
 * <LineChart
 *   data={typedData}           // ✓ Type checked
 *   width={500}                // ✓ Type checked
 *   height={300}               // ✓ Type checked
 * >
 *   <Line
 *     type="monotone"          // ✓ Type checked (literal types)
 *     dataKey="value"          // ✓ Type checked
 *     stroke="#8884d8"         // ✓ Type checked
 *   />
 * </LineChart>
 * ```
 *
 * ============================================================================
 * MIGRATION NOTES
 * ============================================================================
 *
 * If you previously used direct imports, you now need to wrap charts in
 * LazyChartWrapper or Suspense:
 *
 * Before:
 * ```tsx
 * <LineChart data={data}>...</LineChart>
 * ```
 *
 * After:
 * ```tsx
 * <LazyChartWrapper>
 *   <LineChart data={data}>...</LineChart>
 * </LazyChartWrapper>
 * ```
 *
 * Small components (Line, XAxis, YAxis, Tooltip, etc.) don't need wrapping
 * as they are imported directly for optimal performance.
 */
