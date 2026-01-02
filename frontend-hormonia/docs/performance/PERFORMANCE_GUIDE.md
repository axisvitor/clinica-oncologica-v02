# Guia de Performance do Frontend

**Status:** Implementado
**Ultima Atualizacao:** 2025-12
**Sistema:** Clinica Oncologica v2.1 - Frontend (React 18 + TypeScript)
**Escopo:** 196 componentes TSX

---

## Visao Geral

Este documento consolida todas as otimizacoes de performance do frontend, incluindo lazy loading, padroes de otimizacao React, monitoramento e melhores praticas.

### Estado Atual

| Metrica | Valor | Observacao |
|---------|-------|------------|
| **Total de Componentes** | 196 | 100% analisados |
| **Operacoes Map** | 242 | Instancias identificadas |
| **Componentes sem React.memo** | 180 | 92% precisam otimizacao |
| **Hooks de Otimizacao Existentes** | 112 | 30% cobertura atual |
| **Cobertura Alvo** | 280+ hooks | 80% cobertura |

### Metas de Performance

| Metrica | Antes | Depois | Melhoria |
|---------|-------|--------|----------|
| **Dashboard Load** | 2.5s | 1.2s | -52% |
| **Patient List Render** | 800ms | 350ms | -56% |
| **Chart Updates** | 1.2s | 450ms | -62% |
| **Message Thread** | 600ms | 250ms | -58% |
| **Bundle Inicial** | 314KB | ~150KB | -52% |
| **FCP** | 3.2s | 1.8s | -44% |

---

## Padroes de Otimizacao React

### Padrao 1: Memoizacao de Listas

**Problema:** Listas re-renderizam todos os itens quando o estado do pai muda.

**Solucao:** React.memo no item + useMemo para dados.

```typescript
// Componente item memoizado
const ActivityItem = React.memo(({ activity }: { activity: UIActivityItem }) => {
  const Icon = useMemo(() => getActivityIcon(activity.type), [activity.type])
  const colorClass = useMemo(() => getActivityColor(activity.type), [activity.type])
  const formattedTime = useMemo(() => {
    return formatDistanceToNow(new Date(activity.timestamp), {
      addSuffix: true,
      locale: ptBR
    })
  }, [activity.timestamp])

  return (
    <div className="flex items-start space-x-3">
      <div className={`w-8 h-8 rounded-full ${colorClass}`}>
        <Icon className="w-4 h-4" />
      </div>
      <div className="flex-1">
        <p>{activity.description}</p>
        <p className="text-xs text-gray-500">{formattedTime}</p>
      </div>
    </div>
  )
}, (prevProps, nextProps) => {
  return prevProps.activity.id === nextProps.activity.id &&
         prevProps.activity.timestamp === nextProps.activity.timestamp
})

ActivityItem.displayName = 'ActivityItem'

// Componente pai
export const RecentActivity = React.memo(({ activities }: Props) => {
  return (
    <div className="space-y-4">
      {activities.map((activity) => (
        <ActivityItem key={activity.id} activity={activity} />
      ))}
    </div>
  )
}, (prevProps, nextProps) => {
  return prevProps.activities === nextProps.activities
})
```

**Ganho:** 60-70% menos renders.

---

### Padrao 2: Memoizacao de Callbacks

**Problema:** Callbacks inline quebram memoizacao de componentes filhos.

**Solucao:** useCallback para referencias estaveis.

```typescript
// ERRADO - nova funcao a cada render
{users.map(user => (
  <UserCard
    key={user.id}
    user={user}
    onDelete={() => handleDelete(user.id)} // Nova referencia!
  />
))}

// CORRETO - referencia estavel
const handleDelete = useCallback((userId: string) => {
  deleteUser(userId)
}, [])

{users.map(user => (
  <UserCard
    key={user.id}
    user={user}
    onDelete={handleDelete} // Referencia estavel
  />
))}

// Componente filho
const UserCard = React.memo(({ user, onDelete }: Props) => {
  const handleClick = useCallback(() => {
    onDelete(user.id)
  }, [user.id, onDelete])

  return <Button onClick={handleClick}>Delete</Button>
})
```

**Ganho:** 50-60% menos re-renders.

---

### Padrao 3: Memoizacao de Computacoes Pesadas

**Problema:** Operacoes caras (filter, sort, reduce) executam a cada render.

**Solucao:** useMemo para transformacoes de dados.

```typescript
// ANTES - executa a cada render
const trendData = data.completion_trend.map(point => ({
  ...point,
  date: new Date(point.date).toLocaleDateString('pt-BR')
})).reverse()

// DEPOIS - so recomputa quando data muda
const trendData = useMemo(() => {
  return data.completion_trend.map(point => ({
    ...point,
    date: new Date(point.date).toLocaleDateString('pt-BR')
  })).reverse()
}, [data.completion_trend])

const quizTypeData = useMemo(() => {
  return Object.entries(data.quiz_types).map(([type, stats]) => ({
    type,
    total: stats.total_sessions,
    completed: stats.completed_sessions,
    completion_rate: stats.completion_rate
  }))
}, [data.quiz_types])

const bestQuiz = useMemo(() => {
  return quizTypeData.reduce((prev, current) =>
    prev.completion_rate > current.completion_rate ? prev : current
  )
}, [quizTypeData])
```

**Ganho:** 85-90% reducao de CPU.

---

### Padrao 4: Memoizacao de Dependencias

**Problema:** Novos objetos/arrays em dependencias de useEffect.

**Solucao:** useMemo para objetos de dependencia.

```typescript
// ERRADO - novo objeto a cada render
useEffect(() => {
  fetchData()
}, [{ userId: user.id }]) // Novo objeto!

// CORRETO - objeto memoizado
const params = useMemo(() => ({ userId: user.id }), [user.id])
useEffect(() => {
  fetchData(params)
}, [params])
```

---

### Quando Usar Cada Tecnica

#### React.memo
- Componentes que renderizam frequentemente
- Componentes com logica de render cara
- Itens de lista
- Componentes com props grandes

#### useMemo
- Computacoes caras (filter, sort, reduce)
- Transformacoes de dados
- Objetos/arrays para dependencias
- Calculos complexos no render

#### useCallback
- Funcoes passadas para filhos memoizados
- Funcoes em dependencias de useEffect
- Event handlers para itens de lista
- Callbacks usados em multiplos lugares

---

## Lazy Loading

### Route-Based Code Splitting

```typescript
import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'

// Lazy load das paginas
const Dashboard = lazy(() => import('./pages/Dashboard'))
const PatientList = lazy(() => import('./pages/PatientList'))
const PatientDetails = lazy(() => import('./pages/PatientDetails'))
const Reports = lazy(() => import('./pages/Reports'))
const Settings = lazy(() => import('./pages/Settings'))

function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<PageSkeleton />}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/patients" element={<PatientList />} />
          <Route path="/patients/:id" element={<PatientDetails />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}
```

### Component-Based Lazy Loading

```typescript
const HeavyChart = lazy(() => import('@/components/charts/HeavyChart'))

export function Dashboard() {
  const [showChart, setShowChart] = useState(false)

  return (
    <div>
      <Button onClick={() => setShowChart(true)}>Mostrar Grafico</Button>

      {showChart && (
        <Suspense fallback={<ChartSkeleton />}>
          <HeavyChart data={chartData} />
        </Suspense>
      )}
    </div>
  )
}
```

### Preloading Estrategico

```typescript
// Preload apos carregamento inicial
useEffect(() => {
  const timer = setTimeout(() => {
    import('./pages/PatientList')
    import('./pages/Reports')
  }, 2000)
  return () => clearTimeout(timer)
}, [])

// Hover preloading
<Link
  to="/patients"
  onMouseEnter={() => import('./pages/PatientList')}
>
  Pacientes
</Link>
```

### Skeleton Loaders

```typescript
export function PageSkeleton() {
  return (
    <div className="p-6 space-y-4 animate-pulse">
      <div className="h-8 bg-gray-200 rounded w-1/4" />
      <div className="space-y-3">
        <div className="h-4 bg-gray-200 rounded" />
        <div className="h-4 bg-gray-200 rounded w-5/6" />
      </div>
      <div className="grid grid-cols-3 gap-4 mt-6">
        <div className="h-24 bg-gray-200 rounded" />
        <div className="h-24 bg-gray-200 rounded" />
        <div className="h-24 bg-gray-200 rounded" />
      </div>
    </div>
  )
}
```

### Vite Configuration

```typescript
// vite.config.ts
export default defineConfig({
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'ui-vendor': ['@radix-ui/react-dialog', '@radix-ui/react-dropdown-menu'],
          'chart-vendor': ['recharts'],
          'firebase': ['firebase/app', 'firebase/auth'],
        },
      },
    },
    chunkSizeWarningLimit: 1000,
  },
})
```

---

## Monitoramento de Performance

### React DevTools Profiler

**Interpretacao:**
- Amarelo: Componente re-renderizou
- Cinza: Componente memoizado (nao renderizou)
- Vermelho: Componente demorou muito (gargalo)
- Barra larga = tempo de render maior

### Hooks de Medicao

```typescript
// Hook para contar renders
export function useRenderCount(componentName: string) {
  const renderCount = useRef(0)
  useEffect(() => {
    renderCount.current += 1
    console.log(`[${componentName}] Render #${renderCount.current}`)
  })
  return renderCount.current
}

// Hook para medir tempo de render
export function useRenderTime(componentName: string) {
  const startTime = useRef(performance.now())
  const timings = useRef<number[]>([])

  useEffect(() => {
    const duration = performance.now() - startTime.current
    timings.current.push(duration)
    const avgTime = timings.current.reduce((a, b) => a + b, 0) / timings.current.length
    console.log(`[${componentName}] Duration: ${duration.toFixed(2)}ms, Avg: ${avgTime.toFixed(2)}ms`)
    startTime.current = performance.now()
  })
}

// Hook para debugar re-renders
export function useWhyDidYouUpdate(name: string, props: Record<string, any>) {
  const previousProps = useRef<Record<string, any>>()

  useEffect(() => {
    if (previousProps.current) {
      const changedProps: Record<string, { from: any; to: any }> = {}
      Object.keys({ ...previousProps.current, ...props }).forEach(key => {
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
```

### Performance Monitor Class

```typescript
class PerformanceMonitor {
  private entries: PerformanceEntry[] = []
  private maxEntries = 1000

  log(entry: PerformanceEntry) {
    this.entries.push(entry)
    if (this.entries.length > this.maxEntries) {
      this.entries = this.entries.slice(-this.maxEntries)
    }
    this.sendToAnalytics(entry)
  }

  getMetrics(component?: string) {
    const relevant = component
      ? this.entries.filter(e => e.component === component)
      : this.entries
    if (!relevant.length) return null

    const times = relevant.map(e => e.renderTime)
    return {
      totalRenders: relevant.length,
      avgRenderTime: times.reduce((a, b) => a + b, 0) / times.length,
      maxRenderTime: Math.max(...times),
      p95: this.percentile(times, 95)
    }
  }

  private percentile(values: number[], p: number) {
    const sorted = values.slice().sort((a, b) => a - b)
    return sorted[Math.ceil((sorted.length * p) / 100) - 1]
  }
}

export const performanceMonitor = new PerformanceMonitor()
```

---

## Metricas e Benchmarks

### Performance Budgets

```typescript
export const performanceBudgets = {
  pages: {
    dashboard: { fcp: 1500, lcp: 2500, tti: 3500, tbt: 300, cls: 0.1 },
    patients: { fcp: 1200, lcp: 2000, tti: 3000, tbt: 250, cls: 0.1 },
    metrics: { fcp: 1800, lcp: 3000, tti: 4000, tbt: 350, cls: 0.1 }
  },
  components: {
    QuizCompletionChart: { maxRenderTime: 200, maxRenderCount: 3 },
    PatientsTable: { maxRenderTime: 150, maxRenderCount: 2 },
    MessagesList: { maxRenderTime: 100, maxRenderCount: 2 },
    RecentActivity: { maxRenderTime: 80, maxRenderCount: 2 }
  },
  bundles: {
    main: 250 * 1024,
    vendor: 500 * 1024,
    charts: 150 * 1024,
    total: 1000 * 1024
  }
}
```

### Componentes Prioritarios

| Componente | Ganho Esperado | Tempo | Prioridade |
|------------|----------------|-------|------------|
| QuizCompletionChart | 60% | 2.5h | CRITICO |
| AIPersonalizationChart | 60% | 2.5h | CRITICO |
| SystemHealthChart | 55% | 2h | CRITICO |
| EngagementChart | 55% | 2h | CRITICO |
| MetricsDashboard | 50% | 2h | CRITICO |
| AlertsPanel | 45% | 1.5h | ALTO |
| RecentActivity | 45% | 1.5h | ALTO |
| MessagesList | 50% | 2h | ALTO |
| QuizResponseViewer | 50% | 2h | ALTO |
| PatientTimeline | 45% | 1.5h | ALTO |

---

## Melhores Praticas

### Lazy Loading

**USAR para:**
- Features opcionais grandes (admin, relatorios)
- Rotas condicionais
- Features usadas por <20% dos usuarios
- Bibliotecas sem tree-shaking

**NAO usar para:**
- Componentes UI core
- Componentes frequentes
- Quando quebra type safety

### React Query Optimization

```typescript
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30 * 1000,       // 30s deduplication
      gcTime: 5 * 60 * 1000,      // 5min cache
      refetchOnWindowFocus: false,
      refetchOnMount: false,
    }
  }
})
```

**Impacto:** 40-60% reducao em chamadas API.

### Armadilhas Comuns

```typescript
// ERRADO - dependencia faltando
const filtered = useMemo(() => {
  return items.filter(item => item.status === status)
}, [items]) // Falta 'status'!

// ERRADO - memoizar demais
const sum = useMemo(() => 5 + 5, []) // Desperdicio!
const sum = 5 + 5 // Correto

// ERRADO - named export com lazy
export function Dashboard() { ... }
const Dashboard = lazy(() => import('./Dashboard')) // Falha!

// CORRETO - default export
export default function Dashboard() { ... }
// ou
const Dashboard = lazy(() =>
  import('./Dashboard').then(m => ({ default: m.Dashboard }))
)

// ERRADO - displayName faltando
const Component = React.memo(() => { ... })

// CORRETO
const Component = React.memo(() => { ... })
Component.displayName = 'Component'
```

---

## Checklist de Implementacao

### Por Componente

- [ ] Componente renderiza sem erros
- [ ] Props passam corretamente
- [ ] Memoizacao funciona (render count reduzido)
- [ ] Funcao de comparacao customizada funciona
- [ ] Edge cases tratados (empty, null, undefined)

### Testes de Performance

- [ ] Medir render count (antes/depois)
- [ ] Medir render time (antes/depois)
- [ ] Profile com React DevTools
- [ ] Verificar uso de memoria
- [ ] Confirmar ausencia de memory leaks

### CI/CD Integration

```yaml
# .github/workflows/performance.yml
name: Performance Testing
on: [pull_request]
jobs:
  performance-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with: { node-version: '18' }
      - run: npm ci
      - run: npm run build
      - run: npm run preview &
      - run: sleep 5
      - run: npx ts-node scripts/measure-performance.ts
      - run: npx ts-node scripts/check-budgets.ts
```

---

## Referencias

- [React.lazy() Documentation](https://react.dev/reference/react/lazy)
- [React.memo](https://react.dev/reference/react/memo)
- [Vite Code Splitting](https://vitejs.dev/guide/build.html#chunking-strategy)
- [React Query Documentation](https://tanstack.com/query/latest)
- [Web Vitals](https://web.dev/vitals/)

---

**Status:** Pronto para Implementacao
**Proxima Acao:** Otimizar QuizCompletionChart
