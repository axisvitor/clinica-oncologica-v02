# Recharts Quick Reference - Type-Safe Usage

## ✅ Current Setup (Fixed 2025-01-10)

Recharts components are now **directly imported** with full TypeScript support.

## 🔄 Integration with RECHARTS_TYPE_FIX_SUMMARY

This document has been enhanced with insights from the Recharts type safety fixes. All previous lazy loading issues have been resolved through direct re-exports that preserve full TypeScript type information.

### Key Improvements from Type Fix
- ✅ Zero TypeScript build errors (previously 30+ errors)
- ✅ Full type preservation through direct re-exports
- ✅ Automatic code splitting via Vite configuration
- ✅ Same bundle size with better developer experience
- ✅ No need for type casting or `as any` workarounds

### Basic Import

```typescript
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
} from '@/components/charts/LazyRechartsComponents';

// Import types for advanced usage
import type { ValueType, NameType } from 'recharts/types/component/DefaultTooltipContent';
```

### Simple Chart Example

```tsx
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from '@/components/charts/LazyRechartsComponents';

function MyChart({ data }: { data: Array<{ date: string; value: number }> }) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data}>
        <XAxis dataKey="date" />
        <YAxis />
        <Tooltip />
        <Line type="monotone" dataKey="value" stroke="#8884d8" />
      </LineChart>
    </ResponsiveContainer>
  );
}
```

## Common Patterns

### 1. Custom Tooltip Formatter

**✅ Correct Way:**
```typescript
<Tooltip
  formatter={(value: ValueType, name: NameType, item) => {
    const payload = item.payload as { customField: string };
    return [`${value}${payload.customField}`, name];
  }}
/>
```

**❌ Incorrect Way (causes type errors):**
```typescript
// DON'T: This causes type errors
<Tooltip
  formatter={(value, name, props: { payload: { customField: string } }) => [
    `${value}${props.payload.customField}`, name
  ]}
/>
```

### 2. Multiple Lines with Different Colors

```tsx
<ResponsiveContainer width="100%" height={400}>
  <LineChart data={data}>
    <CartesianGrid strokeDasharray="3 3" />
    <XAxis dataKey="date" />
    <YAxis />
    <Tooltip />
    <Legend />
    <Line type="monotone" dataKey="sales" stroke="#8884d8" name="Sales" />
    <Line type="monotone" dataKey="revenue" stroke="#82ca9d" name="Revenue" />
  </LineChart>
</ResponsiveContainer>
```

### 3. Bar Chart with Custom Colors

```tsx
<ResponsiveContainer width="100%" height={300}>
  <BarChart data={data}>
    <CartesianGrid strokeDasharray="3 3" />
    <XAxis dataKey="category" />
    <YAxis />
    <Tooltip />
    <Bar dataKey="value" radius={[4, 4, 0, 0]}>
      {data.map((entry, index) => (
        <Cell key={`cell-${index}`} fill={entry.color} />
      ))}
    </Bar>
  </BarChart>
</ResponsiveContainer>
```

### 4. Pie Chart with Custom Labels

```tsx
<ResponsiveContainer width="100%" height={300}>
  <PieChart>
    <Pie
      data={data}
      cx="50%"
      cy="50%"
      innerRadius={40}
      outerRadius={80}
      paddingAngle={5}
      dataKey="value"
    >
      {data.map((entry, index) => (
        <Cell key={`cell-${index}`} fill={entry.color} />
      ))}
    </Pie>
    <Tooltip />
    <Legend />
  </PieChart>
</ResponsiveContainer>
```

### 5. Area Chart with Gradient

```tsx
<ResponsiveContainer width="100%" height={300}>
  <AreaChart data={data}>
    <defs>
      <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
        <stop offset="5%" stopColor="#8884d8" stopOpacity={0.8}/>
        <stop offset="95%" stopColor="#8884d8" stopOpacity={0.1}/>
      </linearGradient>
    </defs>
    <CartesianGrid strokeDasharray="3 3" />
    <XAxis dataKey="date" />
    <YAxis />
    <Tooltip />
    <Area
      type="monotone"
      dataKey="value"
      stroke="#8884d8"
      fill="url(#colorValue)"
    />
  </AreaChart>
</ResponsiveContainer>
```

## Available Components

### Chart Types
- `LineChart`, `Line`
- `BarChart`, `Bar`
- `AreaChart`, `Area`
- `PieChart`, `Pie`
- `RadarChart`, `Radar`
- `RadialBarChart`, `RadialBar`
- `ComposedChart` (combines multiple chart types)
- `ScatterChart`, `Scatter`

### Axes & Grid
- `XAxis`, `YAxis`
- `CartesianGrid`
- `PolarGrid`, `PolarAngleAxis`, `PolarRadiusAxis`

### Interactive
- `Tooltip`
- `Legend`

### Layout
- `ResponsiveContainer` (always use this for responsive charts)

### Utilities
- `Cell` (for custom colors in Bar/Pie charts)

## TypeScript Tips

### 1. Data Type Definition

```typescript
interface ChartData {
  date: string;
  value: number;
  category?: string;
  color?: string;
}

const data: ChartData[] = [
  { date: '2025-01', value: 100 },
  { date: '2025-02', value: 150 },
];
```

### 2. Custom Payload Types

```typescript
interface CustomPayload {
  unit: string;
  metric: string;
}

<Tooltip
  formatter={(value: ValueType, name: NameType, item) => {
    const payload = item.payload as CustomPayload;
    return [`${value}${payload.unit}`, payload.metric];
  }}
/>
```

### 3. Type-Safe Props

```typescript
import type { TooltipProps } from '@/components/charts/LazyRechartsComponents';

interface MyTooltipProps extends TooltipProps<ValueType, NameType> {
  // Custom props
}
```

## Performance Best Practices

1. **Use ResponsiveContainer** - Handles resizing automatically
2. **Memoize data transformations** - Use `useMemo` for expensive operations
3. **Limit data points** - Aggregate or sample large datasets
4. **Use appropriate chart types** - Line charts for trends, Bar for comparisons
5. **Optimize re-renders** - Use React.memo for chart components

### Example with Optimization

```tsx
const ChartComponent = React.memo(({ data }: { data: ChartData[] }) => {
  const transformedData = useMemo(
    () => data.map(item => ({
      ...item,
      displayValue: formatValue(item.value)
    })),
    [data]
  );

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={transformedData}>
        <XAxis dataKey="date" />
        <YAxis />
        <Tooltip />
        <Line type="monotone" dataKey="value" stroke="#8884d8" />
      </LineChart>
    </ResponsiveContainer>
  );
});
```

## Common Issues & Solutions

### Issue: Chart not responsive
**Solution:** Always wrap in ResponsiveContainer
```tsx
<ResponsiveContainer width="100%" height={400}>
  <LineChart>...</LineChart>
</ResponsiveContainer>
```

### Issue: Tooltip formatter type error
**Solution:** Use correct signature with `item.payload`
```tsx
formatter={(value, name, item) => {
  const payload = item.payload as YourType;
  return [payload.formatted, name];
}}
```

### Issue: Custom colors not showing
**Solution:** Use Cell component for individual styling
```tsx
<Bar dataKey="value">
  {data.map((entry, index) => (
    <Cell key={`cell-${index}`} fill={entry.color} />
  ))}
</Bar>
```

## Migration Notes

**No changes needed!** If you were previously using LazyRechartsComponents, your code will continue to work exactly as before. The only difference is:

- ✅ Better TypeScript support
- ✅ Faster development (no type errors)
- ✅ Same bundle size
- ✅ No Suspense needed (but won't break if present)

## Resources

- [Recharts Documentation](https://recharts.org)
- [Recharts Examples](https://recharts.org/en-US/examples)
- [API Reference](https://recharts.org/en-US/api)

---

**Last Updated:** 2025-01-10
**Status:** ✅ Production Ready
