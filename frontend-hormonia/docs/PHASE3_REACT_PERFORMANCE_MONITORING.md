# Phase 3: React Performance Monitoring & Measurement Guide

## Overview

This guide provides comprehensive tools and techniques for measuring React performance before and after optimization, setting up continuous monitoring, and integrating performance budgets into CI/CD pipelines.

---

## Table of Contents

1. [React DevTools Profiler](#react-devtools-profiler)
2. [Performance Measurement Hooks](#performance-measurement-hooks)
3. [Benchmarking Approach](#benchmarking-approach)
4. [CI/CD Integration](#cicd-integration)
5. [Performance Budgets](#performance-budgets)
6. [Monitoring Dashboard](#monitoring-dashboard)
7. [Regression Detection](#regression-detection)

---

## React DevTools Profiler

### Installation

```bash
# Chrome Extension
https://chrome.google.com/webstore/detail/react-developer-tools/fmkadmapgofadopljbjfkapdkoienihi

# Firefox Add-on
https://addons.mozilla.org/en-US/firefox/addon/react-devtools/

# Edge Extension
https://microsoftedge.microsoft.com/addons/detail/react-developer-tools/gpphkfbcpidddadnkolkpfckpihlkkil
```

### Using the Profiler

#### Step 1: Open DevTools
1. Press `F12` or `Ctrl+Shift+I` (Windows/Linux) / `Cmd+Option+I` (Mac)
2. Click on "⚛️ Profiler" tab
3. Click the blue record button

#### Step 2: Record a Session
```typescript
// Typical workflow:
1. Click "Record" button (blue circle)
2. Perform user action (e.g., open dashboard)
3. Wait for components to render
4. Click "Stop" button
5. Analyze the flame graph
```

#### Step 3: Analyze Results

**Flame Graph Colors:**
- 🟨 **Yellow**: Component re-rendered (took time)
- ⬜ **Gray**: Component memoized (didn't render)
- 🟥 **Red**: Component took very long to render (bottleneck!)

**Bar Width:**
- Wider bars = longer render time
- Hover to see exact milliseconds

**Ranked Chart:**
- Shows components sorted by render time
- Identify slowest components first

### Interpreting Results

#### Before Optimization Example
```
QuizCompletionChart        ████████████████████ 450ms (15 renders)
├─ ResponsiveContainer     ████████ 120ms
├─ AreaChart               ██████ 95ms
├─ BarChart                ████ 78ms
└─ PieChart                ███ 65ms
```

#### After Optimization Example
```
QuizCompletionChart        ████ 180ms (2 renders) ✅ 60% faster
├─ ResponsiveContainer     ██ 45ms (memoized)
├─ AreaChart               ██ 38ms (memoized)
├─ BarChart                █ 22ms (memoized)
└─ PieChart                █ 18ms (memoized)
```

---

## Performance Measurement Hooks

### 1. Render Count Hook

```typescript
// /src/hooks/useRenderCount.ts
import { useEffect, useRef } from 'react'

export function useRenderCount(componentName: string, enabled = true) {
  const renderCount = useRef(0)

  useEffect(() => {
    if (!enabled) return

    renderCount.current += 1
    console.log(`[${componentName}] Render #${renderCount.current}`)
  })

  return renderCount.current
}

// Usage in component
function MyComponent() {
  useRenderCount('MyComponent', process.env.NODE_ENV === 'development')
  // Rest of component...
}
```

### 2. Render Time Hook

```typescript
// /src/hooks/useRenderTime.ts
import { useEffect, useRef } from 'react'

export function useRenderTime(componentName: string, enabled = true) {
  const renderCount = useRef(0)
  const startTime = useRef(performance.now())
  const timings = useRef<number[]>([])

  useEffect(() => {
    if (!enabled) return

    const duration = performance.now() - startTime.current
    renderCount.current += 1
    timings.current.push(duration)

    const avgTime = timings.current.reduce((a, b) => a + b, 0) / timings.current.length

    console.log(
      `[${componentName}] ` +
      `Render #${renderCount.current} ` +
      `Duration: ${duration.toFixed(2)}ms ` +
      `Avg: ${avgTime.toFixed(2)}ms`
    )

    startTime.current = performance.now()
  })

  return {
    renderCount: renderCount.current,
    averageTime: timings.current.reduce((a, b) => a + b, 0) / timings.current.length || 0,
    timings: timings.current
  }
}

// Usage
function MyComponent() {
  const { renderCount, averageTime } = useRenderTime('MyComponent')
  // Rest of component...
}
```

### 3. Why Did You Render Hook

```typescript
// /src/hooks/useWhyDidYouUpdate.ts
import { useEffect, useRef } from 'react'

export function useWhyDidYouUpdate(name: string, props: Record<string, any>) {
  const previousProps = useRef<Record<string, any>>()

  useEffect(() => {
    if (previousProps.current) {
      const allKeys = Object.keys({ ...previousProps.current, ...props })
      const changedProps: Record<string, { from: any; to: any }> = {}

      allKeys.forEach(key => {
        if (previousProps.current![key] !== props[key]) {
          changedProps[key] = {
            from: previousProps.current![key],
            to: props[key]
          }
        }
      })

      if (Object.keys(changedProps).length > 0) {
        console.log('[why-did-you-update]', name, changedProps)
      }
    }

    previousProps.current = props
  })
}

// Usage
function MyComponent({ data, filter, sortBy }: Props) {
  useWhyDidYouUpdate('MyComponent', { data, filter, sortBy })
  // Rest of component...
}
```

### 4. Performance Wrapper HOC

```typescript
// /src/utils/withPerformanceTracking.tsx
import React, { useEffect, useRef } from 'react'

interface PerformanceMetrics {
  renderCount: number
  averageRenderTime: number
  totalRenderTime: number
  maxRenderTime: number
}

export function withPerformanceTracking<P extends object>(
  Component: React.ComponentType<P>,
  componentName: string,
  options: {
    enabled?: boolean
    logToConsole?: boolean
    reportThreshold?: number // ms
  } = {}
) {
  const { enabled = true, logToConsole = true, reportThreshold = 50 } = options

  return function PerformanceTracked(props: P) {
    const renderCount = useRef(0)
    const startTime = useRef(performance.now())
    const timings = useRef<number[]>([])
    const metricsRef = useRef<PerformanceMetrics>({
      renderCount: 0,
      averageRenderTime: 0,
      totalRenderTime: 0,
      maxRenderTime: 0
    })

    useEffect(() => {
      if (!enabled) return

      const duration = performance.now() - startTime.current
      renderCount.current += 1
      timings.current.push(duration)

      const totalTime = timings.current.reduce((a, b) => a + b, 0)
      const avgTime = totalTime / timings.current.length
      const maxTime = Math.max(...timings.current)

      metricsRef.current = {
        renderCount: renderCount.current,
        averageRenderTime: avgTime,
        totalRenderTime: totalTime,
        maxRenderTime: maxTime
      }

      if (logToConsole && duration > reportThreshold) {
        console.warn(
          `[Performance Warning] ${componentName} took ${duration.toFixed(2)}ms ` +
          `(threshold: ${reportThreshold}ms)`
        )
      }

      startTime.current = performance.now()
    })

    return <Component {...props} />
  }
}

// Usage
const OptimizedQuizChart = withPerformanceTracking(
  QuizCompletionChart,
  'QuizCompletionChart',
  { reportThreshold: 100 }
)
```

---

## Benchmarking Approach

### 1. Baseline Measurement Script

```typescript
// /scripts/measure-performance.ts
import { performance } from 'perf_hooks'
import puppeteer from 'puppeteer'

interface PerformanceMetrics {
  component: string
  fcp: number // First Contentful Paint
  lcp: number // Largest Contentful Paint
  tti: number // Time to Interactive
  tbt: number // Total Blocking Time
  cls: number // Cumulative Layout Shift
  renderCount: number
  avgRenderTime: number
}

async function measureComponentPerformance(
  url: string,
  componentSelector: string
): Promise<PerformanceMetrics> {
  const browser = await puppeteer.launch()
  const page = await browser.newPage()

  // Enable performance monitoring
  await page.evaluateOnNewDocument(() => {
    window.performance.mark('navigationStart')
  })

  await page.goto(url, { waitUntil: 'networkidle2' })

  // Get Web Vitals
  const metrics = await page.evaluate(() => {
    return new Promise<PerformanceMetrics>((resolve) => {
      const perfData = performance.getEntriesByType('navigation')[0] as any
      const paintEntries = performance.getEntriesByType('paint')

      const fcp = paintEntries.find(e => e.name === 'first-contentful-paint')?.startTime || 0
      const lcp = (performance as any).getLargestContentfulPaint?.()?.renderTime || 0

      resolve({
        component: '',
        fcp,
        lcp,
        tti: perfData.domInteractive,
        tbt: perfData.domContentLoadedEventEnd - perfData.domContentLoadedEventStart,
        cls: (performance as any).getCumulativeLayoutShift?.() || 0,
        renderCount: 0,
        avgRenderTime: 0
      })
    })
  })

  await browser.close()
  return metrics
}

// Run benchmarks
async function runBenchmarks() {
  console.log('Running performance benchmarks...\n')

  const components = [
    { name: 'DashboardPage', url: 'http://localhost:3000/', selector: '[data-testid="dashboard"]' },
    { name: 'PatientsPage', url: 'http://localhost:3000/patients', selector: '[data-testid="patients-table"]' },
    { name: 'MetricsPage', url: 'http://localhost:3000/metrics', selector: '[data-testid="metrics-dashboard"]' }
  ]

  const results: PerformanceMetrics[] = []

  for (const component of components) {
    console.log(`Measuring ${component.name}...`)
    const metrics = await measureComponentPerformance(component.url, component.selector)
    metrics.component = component.name
    results.push(metrics)
    console.log(`  FCP: ${metrics.fcp.toFixed(2)}ms`)
    console.log(`  LCP: ${metrics.lcp.toFixed(2)}ms`)
    console.log(`  TTI: ${metrics.tti.toFixed(2)}ms\n`)
  }

  // Save results to JSON
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-')
  const fs = require('fs')
  fs.writeFileSync(
    `performance-results-${timestamp}.json`,
    JSON.stringify(results, null, 2)
  )

  console.log(`Results saved to performance-results-${timestamp}.json`)
}

runBenchmarks()
```

### 2. Run Benchmarks

```bash
# Install dependencies
npm install --save-dev puppeteer

# Run before optimization
npm run dev &
sleep 5
npx ts-node scripts/measure-performance.ts > baseline.json

# Apply optimizations...

# Run after optimization
npm run dev &
sleep 5
npx ts-node scripts/measure-performance.ts > optimized.json

# Compare results
npx ts-node scripts/compare-performance.ts baseline.json optimized.json
```

### 3. Comparison Script

```typescript
// /scripts/compare-performance.ts
import fs from 'fs'

interface PerformanceMetrics {
  component: string
  fcp: number
  lcp: number
  tti: number
  renderCount: number
  avgRenderTime: number
}

function compareResults(baselinePath: string, optimizedPath: string) {
  const baseline: PerformanceMetrics[] = JSON.parse(fs.readFileSync(baselinePath, 'utf-8'))
  const optimized: PerformanceMetrics[] = JSON.parse(fs.readFileSync(optimizedPath, 'utf-8'))

  console.log('\n📊 Performance Comparison Report\n')
  console.log('─'.repeat(80))

  baseline.forEach((base, index) => {
    const opt = optimized[index]
    if (!opt || base.component !== opt.component) return

    console.log(`\n🔍 ${base.component}`)
    console.log('─'.repeat(80))

    const fcpDiff = ((base.fcp - opt.fcp) / base.fcp) * 100
    const lcpDiff = ((base.lcp - opt.lcp) / base.lcp) * 100
    const ttiDiff = ((base.tti - opt.tti) / base.tti) * 100

    console.log(`First Contentful Paint:`)
    console.log(`  Before: ${base.fcp.toFixed(2)}ms`)
    console.log(`  After:  ${opt.fcp.toFixed(2)}ms`)
    console.log(`  Change: ${fcpDiff > 0 ? '🟢' : '🔴'} ${fcpDiff.toFixed(2)}%\n`)

    console.log(`Largest Contentful Paint:`)
    console.log(`  Before: ${base.lcp.toFixed(2)}ms`)
    console.log(`  After:  ${opt.lcp.toFixed(2)}ms`)
    console.log(`  Change: ${lcpDiff > 0 ? '🟢' : '🔴'} ${lcpDiff.toFixed(2)}%\n`)

    console.log(`Time to Interactive:`)
    console.log(`  Before: ${base.tti.toFixed(2)}ms`)
    console.log(`  After:  ${opt.tti.toFixed(2)}ms`)
    console.log(`  Change: ${ttiDiff > 0 ? '🟢' : '🔴'} ${ttiDiff.toFixed(2)}%`)
  })

  console.log('\n' + '─'.repeat(80))
}

const [baselinePath, optimizedPath] = process.argv.slice(2)
compareResults(baselinePath, optimizedPath)
```

---

## CI/CD Integration

### 1. GitHub Actions Workflow

```yaml
# /.github/workflows/performance.yml
name: Performance Testing

on:
  pull_request:
    branches: [main, develop]
  push:
    branches: [main]

jobs:
  performance-test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
          cache: 'npm'

      - name: Install dependencies
        run: npm ci

      - name: Build application
        run: npm run build

      - name: Start server
        run: |
          npm run preview &
          sleep 5

      - name: Run performance benchmarks
        run: npx ts-node scripts/measure-performance.ts

      - name: Upload performance results
        uses: actions/upload-artifact@v3
        with:
          name: performance-results
          path: performance-results-*.json

      - name: Check performance budgets
        run: npx ts-node scripts/check-budgets.ts

      - name: Comment PR with results
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v6
        with:
          script: |
            const fs = require('fs')
            const results = JSON.parse(fs.readFileSync('performance-results-latest.json'))

            let comment = '## 📊 Performance Test Results\n\n'
            results.forEach(metric => {
              comment += `### ${metric.component}\n`
              comment += `- FCP: ${metric.fcp.toFixed(2)}ms\n`
              comment += `- LCP: ${metric.lcp.toFixed(2)}ms\n`
              comment += `- TTI: ${metric.tti.toFixed(2)}ms\n\n`
            })

            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: comment
            })
```

### 2. Performance Budget Checker

```typescript
// /scripts/check-budgets.ts
import fs from 'fs'

interface PerformanceBudget {
  component: string
  maxFCP: number
  maxLCP: number
  maxTTI: number
  maxRenderTime: number
}

const budgets: PerformanceBudget[] = [
  {
    component: 'DashboardPage',
    maxFCP: 1500,
    maxLCP: 2500,
    maxTTI: 3500,
    maxRenderTime: 200
  },
  {
    component: 'PatientsPage',
    maxFCP: 1200,
    maxLCP: 2000,
    maxTTI: 3000,
    maxRenderTime: 150
  },
  {
    component: 'MetricsPage',
    maxFCP: 1800,
    maxLCP: 3000,
    maxTTI: 4000,
    maxRenderTime: 250
  }
]

function checkBudgets(resultsPath: string) {
  const results = JSON.parse(fs.readFileSync(resultsPath, 'utf-8'))
  let passed = true
  let violations: string[] = []

  results.forEach((result: any) => {
    const budget = budgets.find(b => b.component === result.component)
    if (!budget) return

    if (result.fcp > budget.maxFCP) {
      violations.push(`❌ ${result.component}: FCP ${result.fcp}ms exceeds budget ${budget.maxFCP}ms`)
      passed = false
    }

    if (result.lcp > budget.maxLCP) {
      violations.push(`❌ ${result.component}: LCP ${result.lcp}ms exceeds budget ${budget.maxLCP}ms`)
      passed = false
    }

    if (result.tti > budget.maxTTI) {
      violations.push(`❌ ${result.component}: TTI ${result.tti}ms exceeds budget ${budget.maxTTI}ms`)
      passed = false
    }
  })

  if (!passed) {
    console.error('\n🚨 Performance Budget Violations:\n')
    violations.forEach(v => console.error(v))
    process.exit(1)
  } else {
    console.log('\n✅ All performance budgets met!')
  }
}

checkBudgets('performance-results-latest.json')
```

---

## Performance Budgets

### Recommended Budgets

```typescript
// /config/performance-budgets.ts
export const performanceBudgets = {
  // Page-level budgets
  pages: {
    dashboard: {
      fcp: 1500,  // First Contentful Paint
      lcp: 2500,  // Largest Contentful Paint
      tti: 3500,  // Time to Interactive
      tbt: 300,   // Total Blocking Time
      cls: 0.1    // Cumulative Layout Shift
    },
    patients: {
      fcp: 1200,
      lcp: 2000,
      tti: 3000,
      tbt: 250,
      cls: 0.1
    },
    metrics: {
      fcp: 1800,
      lcp: 3000,
      tti: 4000,
      tbt: 350,
      cls: 0.1
    }
  },

  // Component-level budgets
  components: {
    QuizCompletionChart: {
      maxRenderTime: 200,
      maxRenderCount: 3
    },
    PatientsTable: {
      maxRenderTime: 150,
      maxRenderCount: 2
    },
    MessagesList: {
      maxRenderTime: 100,
      maxRenderCount: 2
    },
    RecentActivity: {
      maxRenderTime: 80,
      maxRenderCount: 2
    }
  },

  // Bundle size budgets
  bundles: {
    main: 250 * 1024,      // 250 KB
    vendor: 500 * 1024,    // 500 KB
    charts: 150 * 1024,    // 150 KB
    total: 1000 * 1024     // 1 MB
  }
}
```

---

## Monitoring Dashboard

### Real-time Performance Monitoring

```typescript
// /src/utils/performanceMonitor.ts
interface PerformanceEntry {
  component: string
  timestamp: number
  renderTime: number
  renderCount: number
  props: Record<string, any>
}

class PerformanceMonitor {
  private entries: PerformanceEntry[] = []
  private maxEntries = 1000

  log(entry: PerformanceEntry) {
    this.entries.push(entry)

    // Keep only recent entries
    if (this.entries.length > this.maxEntries) {
      this.entries = this.entries.slice(-this.maxEntries)
    }

    // Send to analytics service (e.g., Google Analytics, Sentry)
    this.sendToAnalytics(entry)
  }

  private sendToAnalytics(entry: PerformanceEntry) {
    // Example: Send to Google Analytics
    if (typeof window !== 'undefined' && (window as any).gtag) {
      (window as any).gtag('event', 'performance_metric', {
        component: entry.component,
        render_time: entry.renderTime,
        render_count: entry.renderCount
      })
    }

    // Example: Send to Sentry
    if (typeof window !== 'undefined' && (window as any).Sentry) {
      (window as any).Sentry.addBreadcrumb({
        category: 'performance',
        message: `${entry.component} rendered in ${entry.renderTime}ms`,
        level: 'info',
        data: entry
      })
    }
  }

  getMetrics(component?: string) {
    const relevantEntries = component
      ? this.entries.filter(e => e.component === component)
      : this.entries

    if (relevantEntries.length === 0) return null

    const renderTimes = relevantEntries.map(e => e.renderTime)
    const avgRenderTime = renderTimes.reduce((a, b) => a + b, 0) / renderTimes.length
    const maxRenderTime = Math.max(...renderTimes)
    const minRenderTime = Math.min(...renderTimes)

    return {
      totalRenders: relevantEntries.length,
      avgRenderTime,
      maxRenderTime,
      minRenderTime,
      p95: this.percentile(renderTimes, 95),
      p99: this.percentile(renderTimes, 99)
    }
  }

  private percentile(values: number[], p: number) {
    const sorted = values.slice().sort((a, b) => a - b)
    const index = Math.ceil((sorted.length * p) / 100) - 1
    return sorted[index]
  }

  clear() {
    this.entries = []
  }
}

export const performanceMonitor = new PerformanceMonitor()
```

---

## Regression Detection

### Automated Regression Testing

```typescript
// /scripts/detect-regression.ts
import fs from 'fs'

interface Metrics {
  component: string
  fcp: number
  lcp: number
  tti: number
}

function detectRegression(
  baselinePath: string,
  currentPath: string,
  threshold = 0.1 // 10% regression threshold
) {
  const baseline: Metrics[] = JSON.parse(fs.readFileSync(baselinePath, 'utf-8'))
  const current: Metrics[] = JSON.parse(fs.readFileSync(currentPath, 'utf-8'))

  let hasRegression = false
  const regressions: string[] = []

  baseline.forEach((base, index) => {
    const curr = current[index]
    if (!curr || base.component !== curr.component) return

    const fcpRegression = (curr.fcp - base.fcp) / base.fcp
    const lcpRegression = (curr.lcp - base.lcp) / base.lcp
    const ttiRegression = (curr.tti - base.tti) / base.tti

    if (fcpRegression > threshold) {
      regressions.push(`⚠️  ${base.component}: FCP regressed by ${(fcpRegression * 100).toFixed(2)}%`)
      hasRegression = true
    }

    if (lcpRegression > threshold) {
      regressions.push(`⚠️  ${base.component}: LCP regressed by ${(lcpRegression * 100).toFixed(2)}%`)
      hasRegression = true
    }

    if (ttiRegression > threshold) {
      regressions.push(`⚠️  ${base.component}: TTI regressed by ${(ttiRegression * 100).toFixed(2)}%`)
      hasRegression = true
    }
  })

  if (hasRegression) {
    console.error('\n🚨 Performance Regressions Detected:\n')
    regressions.forEach(r => console.error(r))
    process.exit(1)
  } else {
    console.log('\n✅ No performance regressions detected!')
  }
}

const [baselinePath, currentPath] = process.argv.slice(2)
detectRegression(baselinePath, currentPath)
```

---

## Best Practices Summary

### During Development
1. ✅ Use React DevTools Profiler regularly
2. ✅ Add performance hooks to components being optimized
3. ✅ Set up `useWhyDidYouUpdate` for debugging
4. ✅ Monitor console for performance warnings
5. ✅ Run local benchmarks before committing

### In CI/CD
1. ✅ Run automated performance tests on every PR
2. ✅ Check performance budgets
3. ✅ Detect regressions against baseline
4. ✅ Comment results on PR
5. ✅ Block merge if budgets violated

### In Production
1. ✅ Send metrics to analytics service
2. ✅ Monitor real user metrics (RUM)
3. ✅ Set up alerts for performance degradation
4. ✅ Track performance trends over time
5. ✅ Correlate performance with business metrics

---

## Next Steps

1. ⏩ Install React DevTools extension
2. ⏩ Set up performance hooks in development
3. ⏩ Run baseline benchmarks
4. ⏩ Implement optimizations
5. ⏩ Measure improvements
6. ⏩ Set up CI/CD performance testing
7. ⏩ Define and enforce performance budgets

---

**Document Version:** 1.0
**Last Updated:** 2025-11-13
**Tools Provided:** 15+ monitoring utilities
**CI/CD Ready:** Yes
**Status:** Ready for Implementation
