# Guia de Lazy Loading - Frontend Hormonia

## 🎯 Objetivo

Implementar lazy loading (carregamento preguiçoso) para otimizar o desempenho do frontend, reduzindo o tamanho do bundle inicial e melhorando o tempo de carregamento da página.

## 📊 Benefícios

- **Redução do bundle inicial**: Carrega apenas o código necessário para a rota atual
- **Melhor First Contentful Paint (FCP)**: Usuário vê conteúdo mais rápido
- **Melhor Time to Interactive (TTI)**: Aplicação fica interativa mais rápido
- **Economia de banda**: Usuários não baixam código de páginas que não visitam

## 🏗️ Estratégia de Implementação

### 1. Route-Based Code Splitting

Dividir a aplicação por rotas é a forma mais eficaz de lazy loading.

#### Antes (Sem Lazy Loading)

```typescript
// src/App.tsx
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import PatientList from './pages/PatientList'
import PatientDetails from './pages/PatientDetails'
import Reports from './pages/Reports'
import Settings from './pages/Settings'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/patients" element={<PatientList />} />
        <Route path="/patients/:id" element={<PatientDetails />} />
        <Route path="/reports" element={<Reports />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </BrowserRouter>
  )
}
```

**Problema**: Todas as páginas são incluídas no bundle inicial, mesmo que o usuário não visite todas.

#### Depois (Com Lazy Loading)

```typescript
// src/App.tsx
import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import LoadingSpinner from './components/LoadingSpinner'

// Lazy load das páginas
const Dashboard = lazy(() => import('./pages/Dashboard'))
const PatientList = lazy(() => import('./pages/PatientList'))
const PatientDetails = lazy(() => import('./pages/PatientDetails'))
const Reports = lazy(() => import('./pages/Reports'))
const Settings = lazy(() => import('./pages/Settings'))

function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<LoadingSpinner />}>
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

**Benefício**: Cada página é carregada apenas quando o usuário navega até ela.

### 2. Component-Based Lazy Loading

Para componentes pesados que não são sempre visíveis.

```typescript
// src/pages/Dashboard.tsx
import { lazy, Suspense, useState } from 'react'
import { Button } from '@/components/ui/button'

// Lazy load de componente pesado
const HeavyChart = lazy(() => import('@/components/charts/HeavyChart'))
const DataTable = lazy(() => import('@/components/tables/DataTable'))

export function Dashboard() {
  const [showChart, setShowChart] = useState(false)

  return (
    <div>
      <h1>Dashboard</h1>

      <Button onClick={() => setShowChart(true)}>
        Mostrar Gráfico
      </Button>

      {showChart && (
        <Suspense fallback={<div>Carregando gráfico...</div>}>
          <HeavyChart data={chartData} />
        </Suspense>
      )}

      <Suspense fallback={<div>Carregando tabela...</div>}>
        <DataTable data={tableData} />
      </Suspense>
    </div>
  )
}
```

### 3. Preloading Estratégico

Carregar componentes antes que o usuário os solicite.

```typescript
// src/utils/preload.ts
import { ComponentType } from 'react'

export function preloadComponent(
  factory: () => Promise<{ default: ComponentType<any> }>
) {
  // Inicia o carregamento mas não bloqueia
  factory()
}

// src/App.tsx
import { useEffect } from 'react'
import { preloadComponent } from './utils/preload'

function App() {
  useEffect(() => {
    // Preload de rotas comuns após o carregamento inicial
    const timer = setTimeout(() => {
      preloadComponent(() => import('./pages/PatientList'))
      preloadComponent(() => import('./pages/Reports'))
    }, 2000) // 2 segundos após o carregamento inicial

    return () => clearTimeout(timer)
  }, [])

  // ... resto do código
}
```

### 4. Hover Preloading

Carregar página quando usuário passa o mouse sobre o link.

```typescript
// src/components/NavLink.tsx
import { Link } from 'react-router-dom'
import { preloadComponent } from '@/utils/preload'

interface NavLinkProps {
  to: string
  children: React.ReactNode
  preload?: () => Promise<any>
}

export function NavLink({ to, children, preload }: NavLinkProps) {
  const handleMouseEnter = () => {
    if (preload) {
      preload()
    }
  }

  return (
    <Link to={to} onMouseEnter={handleMouseEnter}>
      {children}
    </Link>
  )
}

// Uso
<NavLink
  to="/patients"
  preload={() => import('./pages/PatientList')}
>
  Pacientes
</NavLink>
```

## 🎨 Componentes de Loading

### Loading Spinner

```typescript
// src/components/LoadingSpinner.tsx
export function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary" />
    </div>
  )
}
```

### Skeleton Loader (Melhor UX)

```typescript
// src/components/PageSkeleton.tsx
export function PageSkeleton() {
  return (
    <div className="p-6 space-y-4 animate-pulse">
      <div className="h-8 bg-gray-200 rounded w-1/4" />
      <div className="space-y-3">
        <div className="h-4 bg-gray-200 rounded" />
        <div className="h-4 bg-gray-200 rounded w-5/6" />
        <div className="h-4 bg-gray-200 rounded w-4/6" />
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

### Error Boundary para Lazy Loading

```typescript
// src/components/LazyErrorBoundary.tsx
import { Component, ReactNode } from 'react'
import { Button } from '@/components/ui/button'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
}

export class LazyErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidCatch(error: Error) {
    console.error('Lazy loading error:', error)
  }

  handleRetry = () => {
    this.setState({ hasError: false })
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center min-h-screen p-6">
          <h2 className="text-2xl font-bold mb-4">
            Erro ao carregar página
          </h2>
          <p className="text-gray-600 mb-4">
            Ocorreu um erro ao carregar esta página.
          </p>
          <Button onClick={this.handleRetry}>
            Tentar Novamente
          </Button>
        </div>
      )
    }

    return this.props.children
  }
}
```

## 📦 Configuração do Vite

O Vite já faz code splitting automático, mas você pode otimizar:

```typescript
// vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          // Agrupa bibliotecas grandes em chunks separados
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'ui-vendor': ['@radix-ui/react-dialog', '@radix-ui/react-dropdown-menu'],
          'chart-vendor': ['recharts', 'd3'],
        },
      },
    },
    chunkSizeWarningLimit: 1000, // Aviso se chunk > 1MB
  },
})
```

## 🎯 Rotas Prioritárias

### Rotas que DEVEM ter lazy loading:
- ✅ Settings/Configurações (pouco acessada)
- ✅ Reports/Relatórios (componentes pesados)
- ✅ Admin Panel (apenas alguns usuários)
- ✅ Quiz Editor (componentes complexos)
- ✅ Analytics Dashboard (gráficos pesados)

### Rotas que PODEM ser eager loaded:
- ⚠️ Login/Auth (primeira interação)
- ⚠️ Dashboard inicial (alta frequência)
- ⚠️ Navigation/Header (sempre visível)

## 📊 Medindo o Impacto

### Antes de implementar:
```bash
npm run build
```

Observe o tamanho dos chunks:
```
dist/assets/index-abc123.js   450.25 kB │ gzip: 145.32 kB
```

### Após implementar:
```bash
npm run build
```

Chunks divididos:
```
dist/assets/index-xyz789.js          85.12 kB │ gzip: 28.45 kB
dist/assets/Dashboard-abc123.js      45.34 kB │ gzip: 15.23 kB
dist/assets/PatientList-def456.js    67.89 kB │ gzip: 22.11 kB
dist/assets/Reports-ghi789.js       125.45 kB │ gzip: 41.78 kB
```

**Resultado**: Bundle inicial reduzido de 145KB para 28KB (gzip) ✅

## 🛠️ Implementação Passo a Passo

### Passo 1: Identificar rotas pesadas

```bash
# Análise do bundle
npm run build
npx vite-bundle-visualizer
```

### Passo 2: Converter imports para lazy

```typescript
// De:
import Dashboard from './pages/Dashboard'

// Para:
const Dashboard = lazy(() => import('./pages/Dashboard'))
```

### Passo 3: Adicionar Suspense boundaries

```typescript
<Suspense fallback={<PageSkeleton />}>
  <Routes>
    {/* rotas aqui */}
  </Routes>
</Suspense>
```

### Passo 4: Adicionar Error Boundaries

```typescript
<LazyErrorBoundary>
  <Suspense fallback={<PageSkeleton />}>
    <Routes>
      {/* rotas aqui */}
    </Routes>
  </Suspense>
</LazyErrorBoundary>
```

### Passo 5: Implementar preloading

```typescript
// Preload em hover dos links de navegação
<NavLink to="/patients" preload={() => import('./pages/PatientList')}>
  Pacientes
</NavLink>
```

## 🚨 Armadilhas Comuns

### ❌ Problema 1: Named exports

```typescript
// ❌ ERRADO - Named export não funciona com lazy()
export function Dashboard() { ... }

// ✅ CORRETO - Default export
export default function Dashboard() { ... }

// ✅ ALTERNATIVA - Named export com wrapper
const Dashboard = lazy(() => 
  import('./pages/Dashboard').then(module => ({ 
    default: module.Dashboard 
  }))
)
```

### ❌ Problema 2: Suspense muito granular

```typescript
// ❌ ERRADO - Muitos Suspense causam "cascatas"
<Suspense fallback={<Spinner />}>
  <Header />
</Suspense>
<Suspense fallback={<Spinner />}>
  <Sidebar />
</Suspense>
<Suspense fallback={<Spinner />}>
  <Content />
</Suspense>

// ✅ CORRETO - Suspense em nível de rota
<Suspense fallback={<PageSkeleton />}>
  <Layout>
    <Header />
    <Sidebar />
    <Content />
  </Layout>
</Suspense>
```

### ❌ Problema 3: Lazy loading excessivo

```typescript
// ❌ ERRADO - Lazy load de componentes muito pequenos
const Button = lazy(() => import('./components/Button'))

// ✅ CORRETO - Apenas componentes grandes (>20KB)
const HeavyChartComponent = lazy(() => import('./components/charts/HeavyChart'))
```

## 📈 Métricas de Sucesso

Use Lighthouse ou WebPageTest para medir:

- **FCP (First Contentful Paint)**: < 1.8s ✅
- **LCP (Largest Contentful Paint)**: < 2.5s ✅
- **TTI (Time to Interactive)**: < 3.8s ✅
- **Bundle inicial**: < 200KB (gzip) ✅

## 🔗 Recursos

- [React Docs - Code Splitting](https://react.dev/reference/react/lazy)
- [Vite - Code Splitting](https://vitejs.dev/guide/features.html#code-splitting)
- [Web.dev - Code Splitting](https://web.dev/reduce-javascript-payloads-with-code-splitting/)

---

**Última Atualização**: Janeiro 2025  
**Versão**: 1.0  
**Responsável**: Time de Performance