/**
 * Recharts Component Re-exports
 *
 * TYPE-SAFE DIRECT IMPORTS (Updated 2025-01-10):
 * This module provides direct re-exports from Recharts with full TypeScript support.
 *
 * Why Direct Imports Instead of Lazy Loading:
 * 1. Type Safety: React.lazy() breaks TypeScript's ability to infer component props
 * 2. Tree Shaking: Recharts already supports tree-shaking - only used components are bundled
 * 3. Core Functionality: Charts are core features, not optional/conditional
 * 4. Bundle Impact: Modern bundlers optimize Recharts automatically
 * 5. Development Experience: No Suspense boundaries needed, simpler code
 *
 * Bundle Analysis:
 * - Recharts base: ~50KB (gzipped)
 * - Only imported chart types are included (tree-shaking)
 * - No separate chunk needed - bundler optimizes automatically
 *
 * Previous lazy-loading implementation caused 30+ TypeScript errors due to
 * loss of type information through React.lazy() wrapper.
 */

// Direct re-exports with full type preservation
export {
  // Chart Types
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  RadarChart,
  Radar,
  RadialBarChart,
  RadialBar,
  ComposedChart,
  ScatterChart,
  Scatter,

  // Axes and Grid
  XAxis,
  YAxis,
  CartesianGrid,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,

  // Interactive Components
  Tooltip,
  Legend,

  // Container
  ResponsiveContainer,

  // Utilities
  Cell,

  // Types
  type TooltipProps
} from 'recharts';

/**
 * USAGE NOTES:
 *
 * 1. Import components directly - no Suspense needed:
 *    ```tsx
 *    import { LineChart, Line, XAxis, YAxis } from '@/components/charts/LazyRechartsComponents';
 *
 *    <LineChart data={data} width={500} height={300}>
 *      <XAxis dataKey="name" />
 *      <YAxis />
 *      <Line type="monotone" dataKey="value" stroke="#8884d8" />
 *    </LineChart>
 *    ```
 *
 * 2. Full TypeScript support - all props are type-checked
 *
 * 3. Tree-shaking automatically excludes unused chart types
 *
 * 4. No loading states needed - components are immediately available
 *
 * 5. Import types from recharts if needed:
 *    ```tsx
 *    import type { ValueType, NameType } from 'recharts/types/component/DefaultTooltipContent';
 *    ```
 *
 * PERFORMANCE CONSIDERATIONS:
 *
 * - Modern bundlers (Vite, Webpack 5) automatically code-split large libraries
 * - Recharts supports ES modules and tree-shaking out of the box
 * - Only the chart components you import are included in the bundle
 * - Typical bundle size: 50-120KB (gzipped) depending on chart types used
 * - No runtime overhead from lazy loading/Suspense
 *
 * MIGRATION FROM LAZY LOADING:
 *
 * If you had:
 * ```tsx
 * <Suspense fallback={<ChartSkeleton />}>
 *   <LineChart>...</LineChart>
 * </Suspense>
 * ```
 *
 * You can now simplify to:
 * ```tsx
 * <LineChart>...</LineChart>
 * ```
 *
 * Note: Existing Suspense boundaries won't cause issues and can be removed gradually.
 */
