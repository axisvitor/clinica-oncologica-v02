/**
 * Lazy-loaded Recharts Components
 *
 * This module provides lazy-loaded versions of all Recharts components
 * to reduce initial bundle size by ~250KB
 */

// Re-export all Recharts components directly
// Lazy loading will happen at the route level via code splitting
export {
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
  XAxis,
  YAxis,
  CartesianGrid,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell
} from 'recharts';
