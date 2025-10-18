# 🎯 Exemplos Práticos de Lazy Loading

## 📚 Índice

1. [Lazy Loading de Páginas](#lazy-loading-de-páginas)
2. [Lazy Loading de Componentes](#lazy-loading-de-componentes)
3. [Lazy Loading de Modais](#lazy-loading-de-modais)
4. [Lazy Loading de Tabs](#lazy-loading-de-tabs)
5. [Prefetch de Rotas](#prefetch-de-rotas)
6. [Skeletons Personalizados](#skeletons-personalizados)
7. [Dynamic Imports](#dynamic-imports)
8. [Error Handling](#error-handling)

---

## 1. Lazy Loading de Páginas

### Exemplo Básico

```typescript
// src/pages/PatientsPage.tsx
import { lazy, Suspense } from 'react'
import { PageSkeleton } from '@/components/loaders/Skeletons'

// ❌ RUIM - Import direto
// import { PatientsPage } from './PatientsPage'

// ✅ BOM - Lazy load
const PatientsPage = lazy(() => import('./PatientsPage'))

function App() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <PatientsPage />
    </Suspense>
  )
}
```

### Com Named Export

```typescript
// Se o componente é um named export
const DashboardPage = lazy(() => 
  import('./DashboardPage').then(module => ({
    default: module.DashboardPage
  }))
)

// Uso
<Suspense fallback={<PageSkeleton />}>
  <DashboardPage />
</Suspense>
```

### Com Skeleton Especializado

```typescript
import { DashboardSkeleton } from '@/components/loaders/Skeletons'

const DashboardPage = lazy(() => import('@/pages/DashboardPage'))

function DashboardRoute() {
  return (
    <Layout>
      <Suspense fallback={<DashboardSkeleton />}>
        <DashboardPage />
      </Suspense>
    </Layout>
  )
}
```

---

## 2. Lazy Loading de Componentes

### Charts Pesados

```typescript
// src/components/charts/LazyCharts.tsx
import { lazy } from 'react'

// Recharts é pesado (~200KB) - sempre lazy load!
export const LazyLineChart = lazy(() => 
  import('./LineChart').then(m => ({ default: m.LineChart }))
)

export const LazyBarChart = lazy(() => 
  import('./BarChart').then(m => ({ default: m.BarChart }))
)

export const LazyPieChart = lazy(() => 
  import('./PieChart').then(m => ({ default: m.PieChart }))
)

// Uso
import { Suspense } from 'react'
import { LazyLineChart } from '@/components/charts/LazyCharts'
import { ChartSkeleton } from '@/components/loaders/Skeletons'

function DashboardMetrics() {
  return (
    <div className="grid grid-cols-2 gap-4">
      <Suspense fallback={<ChartSkeleton />}>
        <LazyLineChart data={salesData} />
      </Suspense>
      
      <Suspense fallback={<ChartSkeleton />}>
        <LazyPieChart data={distributionData} />
      </Suspense>
    </div>
  )
}
```

### Tabelas Complexas

```typescript
// src/components/tables/LazyDataTable.tsx
import { lazy } from 'react'

export const LazyDataTable = lazy(() => 
  import('./DataTable').then(m => ({ default: m.DataTable }))
)

// Uso com Skeleton
import { Suspense } from 'react'
import { TableSkeleton } from '@/components/loaders/Skeletons'

function PatientsTable() {
  return (
    <Suspense fallback={<TableSkeleton rows={10} columns={5} />}>
      <LazyDataTable 
        data={patients} 
        columns={patientColumns}
      />
    </Suspense>
  )
}
```

### Editor Rico

```typescript
// src/components/editor/LazyRichTextEditor.tsx
import { lazy } from 'react'

// TipTap, Slate, etc são muito pesados
export const LazyRichTextEditor = lazy(() => 
  import('./RichTextEditor')
)

// Uso
function MessageComposer() {
  const [showEditor, setShowEditor] = useState(false)
  
  return (
    <div>
      <button onClick={() => setShowEditor(true)}>
        Compor Mensagem
      </button>
      
      {showEditor && (
        <Suspense fallback={<div>Carregando editor...</div>}>
          <LazyRichTextEditor 
            onSave={handleSave}
            initialContent=""
          />
        </Suspense>
      )}
    </div>
  )
}
```

---

## 3. Lazy Loading de Modais

### Modal com Estado

```typescript
// src/components/dialogs/LazyCreatePatientDialog.tsx
import { lazy, Suspense, useState } from 'react'
import { DialogSkeleton } from '@/components/loaders/Skeletons'

const CreatePatientDialog = lazy(() => 
  import('./CreatePatientDialog').then(m => ({
    default: m.CreatePatientDialog
  }))
)

function PatientsPage() {
  const [isDialogOpen, setIsDialogOpen] = useState(false)
  
  return (
    <>
      <Button onClick={() => setIsDialogOpen(true)}>
        Novo Paciente
      </Button>
      
      {/* Só carrega o modal quando necessário */}
      {isDialogOpen && (
        <Suspense fallback={<DialogSkeleton />}>
          <CreatePatientDialog 
            open={isDialogOpen}
            onOpenChange={setIsDialogOpen}
            onSuccess={handlePatientCreated}
          />
        </Suspense>
      )}
    </>
  )
}
```

### Modal com Hook Customizado

```typescript
// src/hooks/useLazyDialog.ts
import { lazy, useState } from 'react'

export function useLazyDialog<T extends ComponentType<any>>(
  importFn: () => Promise<{ default: T }>
) {
  const [isOpen, setIsOpen] = useState(false)
  const LazyComponent = lazy(importFn)
  
  return {
    isOpen,
    open: () => setIsOpen(true),
    close: () => setIsOpen(false),
    Dialog: LazyComponent,
  }
}

// Uso
function MyPage() {
  const { isOpen, open, close, Dialog } = useLazyDialog(() => 
    import('./MyDialog')
  )
  
  return (
    <>
      <Button onClick={open}>Abrir Dialog</Button>
      
      {isOpen && (
        <Suspense fallback={<DialogSkeleton />}>
          <Dialog open={isOpen} onClose={close} />
        </Suspense>
      )}
    </>
  )
}
```

---

## 4. Lazy Loading de Tabs

### Tabs com Lazy Content

```typescript
// src/pages/PatientDetailPage.tsx
import { lazy, Suspense, useState } from 'react'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Skeleton } from '@/components/loaders/Skeletons'

// Lazy load cada tab
const PatientOverview = lazy(() => import('./tabs/PatientOverview'))
const PatientHistory = lazy(() => import('./tabs/PatientHistory'))
const PatientMessages = lazy(() => import('./tabs/PatientMessages'))
const PatientReports = lazy(() => import('./tabs/PatientReports'))

function PatientDetailPage({ patientId }: { patientId: string }) {
  const [activeTab, setActiveTab] = useState('overview')
  
  return (
    <Tabs value={activeTab} onValueChange={setActiveTab}>
      <TabsList>
        <TabsTrigger value="overview">Visão Geral</TabsTrigger>
        <TabsTrigger value="history">Histórico</TabsTrigger>
        <TabsTrigger value="messages">Mensagens</TabsTrigger>
        <TabsTrigger value="reports">Relatórios</TabsTrigger>
      </TabsList>
      
      <TabsContent value="overview">
        <Suspense fallback={<Skeleton className="h-64" />}>
          <PatientOverview patientId={patientId} />
        </Suspense>
      </TabsContent>
      
      <TabsContent value="history">
        <Suspense fallback={<Skeleton className="h-96" />}>
          <PatientHistory patientId={patientId} />
        </Suspense>
      </TabsContent>
      
      <TabsContent value="messages">
        <Suspense fallback={<Skeleton className="h-96" />}>
          <PatientMessages patientId={patientId} />
        </Suspense>
      </TabsContent>
      
      <TabsContent value="reports">
        <Suspense fallback={<Skeleton className="h-96" />}>
          <PatientReports patientId={patientId} />
        </Suspense>
      </TabsContent>
    </Tabs>
  )
}
```

### Com Prefetch ao Selecionar Tab

```typescript
function PatientDetailPage({ patientId }: { patientId: string }) {
  const [activeTab, setActiveTab] = useState('overview')
  
  // Prefetch próximo tab provável
  const handleTabChange = (newTab: string) => {
    setActiveTab(newTab)
    
    // Prefetch tabs adjacentes
    if (newTab === 'overview') {
      import('./tabs/PatientHistory') // Prefetch próximo tab
    } else if (newTab === 'history') {
      import('./tabs/PatientMessages')
    }
  }
  
  return (
    <Tabs value={activeTab} onValueChange={handleTabChange}>
      {/* ... */}
    </Tabs>
  )
}
```

---

## 5. Prefetch de Rotas

### Prefetch Automático no App

```typescript
// App.tsx
import { useEffect } from 'react'
import { prefetchCriticalRoutes } from '@/utils/route-prefetch'

function App() {
  // Prefetch rotas críticas após load
  useEffect(() => {
    if (import.meta.env.PROD) {
      prefetchCriticalRoutes()
    }
  }, [])
  
  return (
    <Router>
      {/* ... */}
    </Router>
  )
}
```

### Prefetch ao Hover

```typescript
// src/components/navigation/Sidebar.tsx
import { PrefetchLink } from '@/components/navigation/PrefetchLink'

function Sidebar() {
  return (
    <nav>
      <PrefetchLink to="/dashboard" prefetchDelay={200}>
        Dashboard
      </PrefetchLink>
      
      <PrefetchLink to="/patients" prefetchDelay={200}>
        Pacientes
      </PrefetchLink>
      
      <PrefetchLink to="/messages" prefetchDelay={300}>
        Mensagens
      </PrefetchLink>
    </nav>
  )
}
```

### Prefetch Manual

```typescript
import { prefetchRoute } from '@/utils/route-prefetch'

function NavigationCard() {
  const handleMouseEnter = () => {
    // Prefetch quando usuário mostra interesse
    prefetchRoute('/patients')
  }
  
  return (
    <Card 
      onMouseEnter={handleMouseEnter}
      onClick={() => navigate('/patients')}
    >
      <h3>Pacientes</h3>
      <p>Gerenciar pacientes</p>
    </Card>
  )
}
```

### Hook de Prefetch

```typescript
import { usePrefetchRoute } from '@/utils/route-prefetch'

function NavItem({ to, children }) {
  const { onMouseEnter, onMouseLeave } = usePrefetchRoute(to, 200)
  
  return (
    <Link 
      to={to}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
    >
      {children}
    </Link>
  )
}
```

---

## 6. Skeletons Personalizados

### Skeleton Básico

```typescript
import { Skeleton } from '@/components/loaders/Skeletons'

function MyComponent() {
  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-3/4" />
      </div>
    )
  }
  
  return <ActualContent />
}
```

### Skeleton de Card

```typescript
import { CardSkeleton } from '@/components/loaders/Skeletons'

function DashboardCards() {
  if (isLoading) {
    return (
      <div className="grid grid-cols-4 gap-4">
        <CardSkeleton />
        <CardSkeleton />
        <CardSkeleton />
        <CardSkeleton />
      </div>
    )
  }
  
  return <ActualCards />
}
```

### Skeleton de Tabela

```typescript
import { TableSkeleton } from '@/components/loaders/Skeletons'

function PatientsTable() {
  return (
    <Suspense fallback={<TableSkeleton rows={10} columns={5} />}>
      <LazyDataTable data={patients} />
    </Suspense>
  )
}
```

### Skeleton Customizado

```typescript
// src/components/MyCustomSkeleton.tsx
import { Skeleton } from '@/components/loaders/Skeletons'

export function PatientCardSkeleton() {
  return (
    <div className="border rounded-lg p-4 space-y-4">
      {/* Avatar */}
      <div className="flex items-center gap-4">
        <Skeleton className="h-16 w-16 rounded-full" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-4 w-48" />
          <Skeleton className="h-3 w-32" />
        </div>
      </div>
      
      {/* Info */}
      <div className="space-y-2">
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-3/4" />
      </div>
      
      {/* Actions */}
      <div className="flex gap-2">
        <Skeleton className="h-8 w-24" />
        <Skeleton className="h-8 w-24" />
      </div>
    </div>
  )
}
```

---

## 7. Dynamic Imports

### Carregar Biblioteca Pesada

```typescript
// src/utils/pdf-export.ts

export async function exportToPDF(data: any) {
  // Só carrega pdfmake quando necessário
  const pdfMake = await import('pdfmake/build/pdfmake')
  const pdfFonts = await import('pdfmake/build/vfs_fonts')
  
  pdfMake.vfs = pdfFonts.pdfMake.vfs
  
  const docDefinition = generatePDFDefinition(data)
  pdfMake.createPdf(docDefinition).download('report.pdf')
}

// Uso
function ExportButton() {
  const [isExporting, setIsExporting] = useState(false)
  
  const handleExport = async () => {
    setIsExporting(true)
    try {
      await exportToPDF(reportData)
    } catch (error) {
      console.error('Export failed:', error)
    } finally {
      setIsExporting(false)
    }
  }
  
  return (
    <Button onClick={handleExport} disabled={isExporting}>
      {isExporting ? 'Exportando...' : 'Exportar PDF'}
    </Button>
  )
}
```

### Carregar Componente Condicional

```typescript
// src/pages/AnalyticsPage.tsx

function AnalyticsPage() {
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [AdvancedCharts, setAdvancedCharts] = useState(null)
  
  const loadAdvancedCharts = async () => {
    const module = await import('./components/AdvancedCharts')
    setAdvancedCharts(() => module.AdvancedCharts)
  }
  
  const handleShowAdvanced = () => {
    setShowAdvanced(true)
    if (!AdvancedCharts) {
      loadAdvancedCharts()
    }
  }
  
  return (
    <div>
      <BasicCharts />
      
      <Button onClick={handleShowAdvanced}>
        Ver Análise Avançada
      </Button>
      
      {showAdvanced && AdvancedCharts && (
        <AdvancedCharts data={analyticsData} />
      )}
    </div>
  )
}
```

---

## 8. Error Handling

### Error Boundary com Suspense

```typescript
// src/components/SuspenseWithError.tsx
import { Suspense, Component, ReactNode } from 'react'

class ErrorBoundary extends Component<
  { children: ReactNode; fallback: ReactNode },
  { hasError: boolean }
> {
  state = { hasError: false }
  
  static getDerivedStateFromError() {
    return { hasError: true }
  }
  
  componentDidCatch(error: Error, errorInfo: any) {
    console.error('Lazy load error:', error, errorInfo)
  }
  
  render() {
    if (this.state.hasError) {
      return this.props.fallback
    }
    return this.props.children
  }
}

export function SuspenseWithError({ 
  children, 
  loadingFallback,
  errorFallback 
}: {
  children: ReactNode
  loadingFallback: ReactNode
  errorFallback: ReactNode
}) {
  return (
    <ErrorBoundary fallback={errorFallback}>
      <Suspense fallback={loadingFallback}>
        {children}
      </Suspense>
    </ErrorBoundary>
  )
}

// Uso
<SuspenseWithError
  loadingFallback={<PageSkeleton />}
  errorFallback={<ErrorState message="Falha ao carregar página" />}
>
  <LazyPage />
</SuspenseWithError>
```

### Retry ao Falhar

```typescript
// src/utils/lazy-with-retry.ts

export function lazyWithRetry<T extends ComponentType<any>>(
  importFn: () => Promise<{ default: T }>,
  maxRetries = 3
) {
  return lazy(async () => {
    let retries = 0
    
    while (retries < maxRetries) {
      try {
        return await importFn()
      } catch (error) {
        retries++
        
        if (retries >= maxRetries) {
          throw error
        }
        
        // Aguardar antes de retry (backoff exponencial)
        await new Promise(resolve => 
          setTimeout(resolve, 1000 * Math.pow(2, retries))
        )
      }
    }
    
    throw new Error('Max retries exceeded')
  })
}

// Uso
const ReliablePage = lazyWithRetry(
  () => import('./MyPage'),
  3 // 3 tentativas
)
```

### Chunk Load Error Handler

```typescript
// src/utils/chunk-error-handler.ts

export function setupChunkErrorHandler() {
  window.addEventListener('error', (event) => {
    if (event.message.includes('ChunkLoadError')) {
      console.warn('Chunk load failed, reloading...')
      
      // Notificar usuário
      toast.warning('Nova versão disponível. Recarregando página...')
      
      // Recarregar após 2s
      setTimeout(() => {
        window.location.reload()
      }, 2000)
    }
  })
}

// main.tsx
setupChunkErrorHandler()
```

---

## 📋 Checklist de Implementação

Ao adicionar lazy loading, sempre:

- [ ] Usar `lazy()` para imports pesados (> 50KB)
- [ ] Adicionar `<Suspense>` com fallback apropriado
- [ ] Escolher skeleton adequado ao conteúdo
- [ ] Adicionar error boundary se crítico
- [ ] Testar em conexão lenta (DevTools → Network → Slow 3G)
- [ ] Verificar que não há console.logs/erros
- [ ] Confirmar que chunk foi criado (`npm run build && npm run analyze`)
- [ ] Documentar dependências pesadas

---

## 🚨 Erros Comuns

### ❌ Erro 1: Esquecer Suspense

```typescript
// ❌ RUIM
const LazyPage = lazy(() => import('./Page'))
<LazyPage /> // Erro: precisa de Suspense!

// ✅ BOM
<Suspense fallback={<Loader />}>
  <LazyPage />
</Suspense>
```

### ❌ Erro 2: Lazy Load Componente Pequeno

```typescript
// ❌ RUIM - Button é < 5KB
const LazyButton = lazy(() => import('./Button'))

// ✅ BOM - Import direto
import { Button } from './Button'
```

### ❌ Erro 3: Suspense Muito Alto

```typescript
// ❌ RUIM - Suspense engloba tudo
<Suspense fallback={<FullPageLoader />}>
  <Layout>
    <Sidebar />
    <LazyContent />
  </Layout>
</Suspense>

// ✅ BOM - Suspense apenas no lazy component
<Layout>
  <Sidebar />
  <Suspense fallback={<ContentLoader />}>
    <LazyContent />
  </Suspense>
</Layout>
```

---

## 📚 Recursos

- [Documentação Completa](../LAZY_LOADING_GUIDE.md)
- [Bundle Analysis](../BUNDLE_ANALYSIS.md)
- [React Lazy Docs](https://react.dev/reference/react/lazy)

---

**Última Atualização**: Janeiro 2025  
**Versão**: 1.0