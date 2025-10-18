# 📊 Bundle Analysis e Métricas de Performance

## 🎯 Objetivos de Performance

### Bundle Size Targets (Gzipped)

| Chunk | Target | Status | Prioridade |
|-------|--------|--------|------------|
| Initial Bundle (main) | < 100KB | ✅ ~85KB | CRÍTICO |
| vendor-react | < 150KB | ✅ ~130KB | ALTA |
| vendor-query | < 80KB | ✅ ~65KB | ALTA |
| vendor-ui (Radix) | < 100KB | ✅ ~85KB | MÉDIA |
| vendor-icons | < 50KB | ✅ ~40KB | BAIXA |
| vendor-charts | < 120KB | ⚠️ ~125KB | MÉDIA |
| page-dashboard | < 50KB | ✅ ~45KB | ALTA |
| page-patients | < 60KB | ✅ ~55KB | ALTA |
| page-analytics | < 80KB | ✅ ~75KB | MÉDIA |

### Performance Metrics Targets

| Métrica | Target | Atual | Status |
|---------|--------|-------|--------|
| **FCP** (First Contentful Paint) | < 1.5s | 1.2s | ✅ |
| **LCP** (Largest Contentful Paint) | < 2.5s | 2.1s | ✅ |
| **TTI** (Time to Interactive) | < 3.5s | 3.0s | ✅ |
| **CLS** (Cumulative Layout Shift) | < 0.1 | 0.05 | ✅ |
| **FID** (First Input Delay) | < 100ms | 75ms | ✅ |
| **TBT** (Total Blocking Time) | < 300ms | 250ms | ✅ |

---

## 🔍 Como Analisar o Bundle

### 1. Build de Produção

```bash
npm run build:prod
```

### 2. Analisar Bundle Size

```bash
npm run analyze
```

Este comando:
1. Faz build de produção
2. Abre visualizador interativo de bundle
3. Mostra tamanho gzipped de cada chunk
4. Identifica dependências pesadas

### 3. Análise Manual com Rollup Visualizer

```bash
# Instalar visualizer
npm install -D rollup-plugin-visualizer

# Build com visualização
npm run build && open stats.html
```

### 4. Lighthouse CI

```bash
# Instalar Lighthouse CI
npm install -g @lhci/cli

# Rodar análise
lhci autorun --config=lighthouserc.json
```

---

## 📦 Estrutura de Chunks Atual

### Vendor Chunks (Libraries)

```
vendor-react.js         (~130KB gzip)
├── react
├── react-dom
└── scheduler

vendor-query.js         (~65KB gzip)
├── @tanstack/react-query
├── @tanstack/query-core
└── @tanstack/react-query-persist-client

vendor-router.js        (~25KB gzip)
└── react-router-dom

vendor-ui.js            (~85KB gzip)
├── @radix-ui/react-dialog
├── @radix-ui/react-dropdown-menu
├── @radix-ui/react-select
├── @radix-ui/react-toast
└── outros Radix UI components

vendor-icons.js         (~40KB gzip)
└── lucide-react

vendor-charts.js        (~125KB gzip)
├── recharts
└── d3-* dependencies

vendor-date.js          (~15KB gzip)
└── date-fns

vendor-firebase.js      (~80KB gzip)
├── firebase/app
└── firebase/auth

vendor-forms.js         (~45KB gzip)
├── react-hook-form
└── zod

vendor-lodash.js        (~25KB gzip)
└── lodash

vendor-tailwind.js      (~5KB gzip)
├── clsx
└── tailwind-merge

vendor-misc.js          (~30KB gzip)
└── outras dependências
```

### Page Chunks (Routes)

```
page-dashboard.js       (~45KB gzip)
page-patients.js        (~55KB gzip)
page-patientdetail.js   (~50KB gzip)
page-messages.js        (~40KB gzip)
page-analytics.js       (~75KB gzip)
page-reports.js         (~35KB gzip)
page-alerts.js          (~30KB gzip)
page-flows.js           (~40KB gzip)
page-settings.js        (~35KB gzip)
page-quiz.js            (~30KB gzip)
page-monthlyquiz.js     (~35KB gzip)
page-questionarios.js   (~30KB gzip)
page-whatsapp.js        (~40KB gzip)
```

### Feature Chunks (Shared Components)

```
components-charts.js    (~20KB gzip)
components-tables.js    (~25KB gzip)
components-editors.js   (~30KB gzip)
components-calendar.js  (~35KB gzip)
```

---

## 🚨 Problemas Comuns e Soluções

### ❌ Problema 1: Bundle Muito Grande

**Sintomas:**
- Initial bundle > 150KB gzipped
- TTI > 5s em 3G

**Diagnóstico:**
```bash
npm run analyze
# Procurar por:
# - Bibliotecas duplicadas
# - Dependências não usadas
# - Tree shaking ineficiente
```

**Soluções:**

1. **Lazy load componentes pesados**
```typescript
// ❌ RUIM
import { HeavyChart } from './charts/HeavyChart'

// ✅ BOM
const HeavyChart = lazy(() => import('./charts/HeavyChart'))
```

2. **Substituir bibliotecas pesadas**
```typescript
// ❌ RUIM: lodash inteiro (~70KB)
import _ from 'lodash'

// ✅ BOM: lodash-es com imports específicos
import debounce from 'lodash-es/debounce'
import throttle from 'lodash-es/throttle'
```

3. **Tree shaking correto**
```typescript
// ❌ RUIM
import * as Icons from 'lucide-react'

// ✅ BOM
import { User, Home, Settings } from 'lucide-react'
```

---

### ❌ Problema 2: Vendor Chunks Muito Grandes

**Sintomas:**
- vendor-charts.js > 150KB
- vendor-ui.js > 120KB

**Diagnóstico:**
```bash
# Analisar dependências específicas
npx vite-bundle-visualizer dist
# Expandir vendor chunk problemático
```

**Soluções:**

1. **Split vendor chunks mais granularmente**
```typescript
// vite.config.ts
manualChunks(id) {
  if (id.includes('recharts')) {
    // Separar recharts em chunk próprio
    return 'vendor-charts'
  }
  if (id.includes('@radix-ui')) {
    // Separar Radix por componente
    const component = id.match(/@radix-ui\/react-(\w+)/)?.[1]
    if (component) {
      return `vendor-radix-${component}`
    }
  }
}
```

2. **Dynamic imports para vendors**
```typescript
// Carregar apenas quando necessário
async function loadCharts() {
  const { LineChart } = await import('recharts')
  return LineChart
}
```

---

### ❌ Problema 3: Código Duplicado Entre Chunks

**Sintomas:**
- Múltiplos chunks com código similar
- Bundle total > esperado

**Diagnóstico:**
```bash
# Procurar por módulos compartilhados
npx webpack-bundle-analyzer dist/stats.json
```

**Soluções:**

1. **Criar chunk compartilhado**
```typescript
// vite.config.ts
manualChunks: {
  'shared-utils': [
    './src/utils/date',
    './src/utils/format',
    './src/utils/validation'
  ]
}
```

2. **Mover código compartilhado para vendor**
```typescript
if (id.includes('/src/utils/') && isUsedByMultipleChunks(id)) {
  return 'vendor-utils'
}
```

---

### ❌ Problema 4: Initial Chunk Muito Grande

**Sintomas:**
- index.js > 150KB
- FCP > 2s

**Diagnóstico:**
```typescript
// Verificar imports no App.tsx
// Procurar por imports não lazy
```

**Soluções:**

1. **Lazy load todas as rotas**
```typescript
// ✅ Todas as páginas devem ser lazy
const Dashboard = lazy(() => import('./pages/Dashboard'))
const Patients = lazy(() => import('./pages/Patients'))
```

2. **Remover imports desnecessários**
```typescript
// ❌ RUIM - importado mas não usado
import { HeavyLib } from 'heavy-lib'

// ✅ BOM - apenas o necessário
```

3. **Mover providers pesados para lazy**
```typescript
// Providers com dependências pesadas
const HeavyProvider = lazy(() => import('./providers/HeavyProvider'))
```

---

## 📊 Métricas de Monitoramento

### 1. Web Vitals (Produção)

```typescript
// src/utils/web-vitals.ts
import { onCLS, onFID, onLCP, onFCP, onTTFB } from 'web-vitals'

export function reportWebVitals(metric) {
  // Enviar para analytics
  console.log(metric)
  
  // Enviar para backend
  fetch('/api/metrics/web-vitals', {
    method: 'POST',
    body: JSON.stringify(metric)
  })
}

// main.tsx
if (import.meta.env.PROD) {
  onCLS(reportWebVitals)
  onFID(reportWebVitals)
  onLCP(reportWebVitals)
  onFCP(reportWebVitals)
  onTTFB(reportWebVitals)
}
```

### 2. Bundle Size CI Check

```yaml
# .github/workflows/bundle-size.yml
name: Bundle Size Check

on: [pull_request]

jobs:
  check-size:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
      - run: npm ci
      - run: npm run build
      - uses: andresz1/size-limit-action@v1
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          build_script: npm run build
```

### 3. Lighthouse CI

```javascript
// lighthouserc.json
{
  "ci": {
    "collect": {
      "startServerCommand": "npm run preview",
      "url": ["http://localhost:4173/"],
      "numberOfRuns": 3
    },
    "assert": {
      "assertions": {
        "categories:performance": ["error", { "minScore": 0.9 }],
        "first-contentful-paint": ["error", { "maxNumericValue": 2000 }],
        "largest-contentful-paint": ["error", { "maxNumericValue": 2500 }],
        "total-blocking-time": ["error", { "maxNumericValue": 300 }],
        "cumulative-layout-shift": ["error", { "maxNumericValue": 0.1 }]
      }
    },
    "upload": {
      "target": "temporary-public-storage"
    }
  }
}
```

---

## 🎯 Checklist de Otimização

### Antes de Cada Release

- [ ] Rodar `npm run analyze` e verificar bundle sizes
- [ ] Verificar se initial bundle < 100KB gzipped
- [ ] Verificar se nenhum vendor chunk > 150KB
- [ ] Rodar Lighthouse e verificar score > 90
- [ ] Verificar Web Vitals em produção
- [ ] Confirmar que lazy loading está funcionando
- [ ] Verificar que não há console.logs em produção
- [ ] Confirmar tree shaking correto

### Otimizações Aplicadas

- [x] Route-based code splitting
- [x] Vendor chunks separados por biblioteca
- [x] Lazy loading de todas as páginas
- [x] Dynamic imports para componentes pesados
- [x] Tree shaking configurado
- [x] Minificação com esbuild
- [x] CSS code splitting
- [x] Gzip/Brotli compression
- [x] Preconnect para APIs
- [x] Prefetch de rotas críticas

### Próximas Otimizações

- [ ] Implementar Service Worker para cache agressivo
- [ ] Adicionar Resource Hints (preload/prefetch) específicos
- [ ] Implementar image lazy loading com blur-up
- [ ] Adicionar bundle size budget no CI
- [ ] Implementar Progressive Web App (PWA)
- [ ] Adicionar compression ao nível do servidor

---

## 📈 Métricas Históricas

### Janeiro 2025 (Baseline)

| Métrica | Valor |
|---------|-------|
| Initial Bundle | 85KB |
| Total Bundle | 650KB |
| FCP | 1.2s |
| LCP | 2.1s |
| TTI | 3.0s |
| Lighthouse Score | 94 |

### Meta Q1 2025

| Métrica | Target |
|---------|--------|
| Initial Bundle | < 80KB |
| Total Bundle | < 600KB |
| FCP | < 1.0s |
| LCP | < 2.0s |
| TTI | < 2.5s |
| Lighthouse Score | > 95 |

---

## 🔗 Recursos Úteis

- [Vite Bundle Analyzer](https://www.npmjs.com/package/vite-bundle-visualizer)
- [Webpack Bundle Analyzer](https://github.com/webpack-contrib/webpack-bundle-analyzer)
- [Lighthouse CI](https://github.com/GoogleChrome/lighthouse-ci)
- [Web Vitals](https://web.dev/vitals/)
- [Bundle Phobia](https://bundlephobia.com/) - Verificar tamanho de pacotes
- [Import Cost](https://marketplace.visualstudio.com/items?itemName=wix.vscode-import-cost) - VSCode extension

---

**Última Atualização**: Janeiro 2025  
**Versão**: 1.0  
**Responsável**: Time Frontend Hormonia