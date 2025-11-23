import React from 'react';

// Re-export Recharts components directly for now to fix build
// In a real lazy loading scenario, we would use React.lazy
export {
    LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
    ResponsiveContainer, AreaChart, Area, BarChart, Bar, RadialBarChart, RadialBar,
    ComposedChart, ScatterChart, Scatter, Cell, PieChart, Pie, Sector
} from 'recharts';
