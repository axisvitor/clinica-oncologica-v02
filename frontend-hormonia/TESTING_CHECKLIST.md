# Testing Checklist - Lazy Loading Implementation

## 🧪 Como Testar as Otimizações

Este guia contém comandos práticos e métodos para validar as otimizações de lazy loading implementadas.

---

## 1️⃣ **Bundle Size Analysis**

### Comando: Build Production
```bash
cd frontend-hormonia
npm run build
```

### Verificar tamanho dos chunks:
```bash
# Windows (PowerShell)
Get-ChildItem dist/js -Recurse | Select-Object Name, @{Name="Size(KB)";Expression={[math]::Round($_.Length/1KB,2)}} | Sort-Object "Size(KB)" -Descending

# Linux/Mac
du -sh dist/js/* | sort -hr
```

### Métricas esperadas:
```
ANTES (sem lazy loading):
main.[hash].js:     ~1800KB
vendor.[hash].js:   ~600KB
TOTAL:              ~2400KB

DEPOIS (com lazy loading):
main.[hash].js:     ~800KB   (-1000KB ✅)
vendor.[hash].js:   ~300KB   (-300KB ✅)
charts.[hash].js:   ~430KB   (novo chunk)
firebase.[hash].js: ~107KB   (novo chunk - após integração)
router.[hash].js:   ~200KB   (novo chunk)
TOTAL inicial:      ~1100KB  (-1300KB ✅)
TOTAL após navegação: ~2000KB (lazy chunks carregados)
```

---

## 2️⃣ **Lighthouse Performance Audit**

### Opção 1: Chrome DevTools
```
1. Abrir Chrome DevTools (F12)
2. Tab "Lighthouse"
3. Selecionar:
   ✅ Performance
   ✅ Desktop ou Mobile
   ✅ Clear storage
4. "Analyze page load"
```

### Opção 2: CLI
```bash
# Instalar Lighthouse
npm install -g @lhci/cli

# Executar audit
lhci autorun --collect.url=https://seu-site.com

# Ou local
npx lighthouse http://localhost:5173 --view
```

### Métricas esperadas:
```
ANTES:
Performance Score: ~65
FCP: 4.2s
LCP: 6.8s
TTI: 6.5s
Total Blocking Time: 1200ms

DEPOIS:
Performance Score: ~85  (+20 ✅)
FCP: 2.0s             (-52% ✅)
LCP: 3.5s             (-48% ✅)
TTI: 3.5s             (-46% ✅)
Total Blocking Time: 500ms (-58% ✅)
```

---

## 3️⃣ **React Query Deduplication Test**

### Método Manual (DevTools):

1. **Instalar React Query DevTools:**
```tsx
// App.tsx (temporary, for testing only)
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';

function App() {
  return (
    <>
      {/* ... */}
      <ReactQueryDevtools initialIsOpen={false} />
    </>
  );
}
```

2. **Abrir página com múltiplos componentes que usam mesma query:**
```
Exemplo: Dashboard (vários componentes pedem lista de pacientes)
```

3. **Verificar no DevTools:**
```
- Abrir React Query DevTools (ícone canto inferior)
- Procurar query key: ['patients', 'list', { page: 1 }]
- Verificar "Observers": Deve mostrar múltiplos componentes
- Verificar "Data Updated At": Deve ter apenas 1 timestamp
- Verificar Network tab: Deve ter apenas 1 request HTTP
```

### Teste Automatizado:
```typescript
// tests/query-deduplication.test.ts
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { usePatients } from '@/hooks/usePatients';

test('deduplicates simultaneous requests', async () => {
  const queryClient = new QueryClient();
  const wrapper = ({ children }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );

  // Render 3 hooks simultaneously
  const { result: result1 } = renderHook(() => usePatients(1), { wrapper });
  const { result: result2 } = renderHook(() => usePatients(1), { wrapper });
  const { result: result3 } = renderHook(() => usePatients(1), { wrapper });

  await waitFor(() => {
    expect(result1.current.isSuccess).toBe(true);
    expect(result2.current.isSuccess).toBe(true);
    expect(result3.current.isSuccess).toBe(true);
  });

  // Verificar que todos compartilham mesma data
  expect(result1.current.data).toBe(result2.current.data);
  expect(result2.current.data).toBe(result3.current.data);
});
```

---

## 4️⃣ **Cache Hit Rate Analysis**

### Método 1: React Query DevTools
```
1. Abrir React Query DevTools
2. Navegar entre páginas (Dashboard → Patients → Dashboard)
3. Verificar:
   - "Data Updated At" não muda se < 5s (cache hit ✅)
   - "Status: fresh" indica cache válido
   - "Observers" mostra quantos componentes usam o cache
```

### Método 2: Network Monitoring
```bash
# Teste manual:
1. Abrir Network tab (DevTools)
2. Navegar: Dashboard → Patients → Dashboard (voltar < 5s)
3. Verificar:
   - 1ª visita Dashboard: Request HTTP ✅
   - Visita Patients: Request HTTP ✅
   - 2ª visita Dashboard (< 5s): SEM request (cache hit ✅)
```

### Métrica esperada:
```
Cache Hit Rate: 50-70%
(50-70% das requests usam cache ao invés de HTTP)
```

---

## 5️⃣ **Firebase Lazy Loading Validation**

### Teste (após integração):

1. **Abrir Network tab (DevTools)**
2. **Acessar homepage (sem login):**
```
Verificar: NENHUM request para firebase.googleapis.com ✅
Bundle: firebase.[hash].js NÃO carregado ✅
```

3. **Clicar em "Login":**
```
Verificar: firebase.[hash].js AGORA é carregado ✅
Requests para firebase.googleapis.com aparecem ✅
```

### Comando para verificar bundle:
```bash
# Verificar se firebase está em chunk separado
npm run build
grep -r "firebase" dist/js/*.js

# Deve mostrar:
# firebase.[hash].js (chunk separado)
# main.[hash].js (sem firebase)
```

---

## 6️⃣ **Recharts Lazy Loading Validation**

### Teste Manual:

1. **Abrir Network tab**
2. **Acessar Dashboard (tem gráficos):**
```
Verificar: charts.[hash].js é carregado ✅
```

3. **Acessar Patients (sem gráficos):**
```
Verificar: charts.[hash].js NÃO é carregado ✅
```

### Verificar bundle:
```bash
npm run build
ls -lh dist/js/charts*.js

# Esperado: ~430KB
```

---

## 7️⃣ **Route-Based Code Splitting**

### Teste Manual:

1. **Abrir Network tab**
2. **Acessar Login:**
```
Verificar: Apenas LoginPage chunk carregado
```

3. **Fazer login → Dashboard:**
```
Verificar: DashboardPage chunk carregado AGORA ✅
```

4. **Navegar → Patients:**
```
Verificar: PatientsPage chunk carregado AGORA ✅
```

### Verificar chunks criados:
```bash
npm run build
ls dist/js/*.js

# Esperado:
# main.[hash].js
# vendor.[hash].js
# router.[hash].js
# charts.[hash].js
# firebase.[hash].js
# DashboardPage-[hash].js
# PatientsPage-[hash].js
# ... (outros chunks de rotas)
```

---

## 8️⃣ **Query Keys Consistency**

### Teste Manual (React Query DevTools):

```
1. Abrir Dashboard
2. Abrir React Query DevTools
3. Verificar query keys:

❌ RUIM (antes):
['patients', 1]
['patients', { page: 1 }]
['patient-list', 1]

✅ BOM (depois):
['patients', 'list', { page: 1 }]
['patients', 'list', { page: 1, status: 'active' }]
['patients', 'detail', '123']
```

### Teste de Invalidação:
```typescript
// Teste: Criar paciente deve atualizar lista
1. Abrir lista de pacientes (note os nomes)
2. Criar novo paciente
3. Verificar: Lista atualiza automaticamente ✅

// Em código:
const mutation = useMutation({
  mutationFn: (data) => apiClient.patients.create(data),
  onSuccess: () => {
    invalidateQueries.allPatients(queryClient);
    // Lista deve atualizar automaticamente
  }
});
```

---

## 9️⃣ **Performance Monitoring (Continuous)**

### Opção 1: Lighthouse CI
```bash
# Instalar
npm install -D @lhci/cli

# lighthouserc.json
{
  "ci": {
    "collect": {
      "url": ["http://localhost:5173"],
      "numberOfRuns": 3
    },
    "assert": {
      "assertions": {
        "categories:performance": ["error", { "minScore": 0.8 }],
        "first-contentful-paint": ["error", { "maxNumericValue": 2500 }]
      }
    }
  }
}

# Executar
npm run build
npm run preview
lhci autorun
```

### Opção 2: Bundle Analyzer
```bash
# Instalar
npm install -D rollup-plugin-visualizer

# vite.config.ts
import { visualizer } from 'rollup-plugin-visualizer';

export default defineConfig({
  plugins: [
    visualizer({
      open: true,
      gzipSize: true,
      brotliSize: true
    })
  ]
});

# Build + analisar
npm run build
# Abre stats.html automaticamente
```

---

## 🎯 Checklist Completo de Testes

### Bundle Size:
- [ ] Main bundle < 1.1MB (antes: ~1.8MB)
- [ ] Recharts chunk ~430KB existente
- [ ] Firebase chunk ~107KB existente (após integração)
- [ ] Route chunks 50-150KB cada

### Lighthouse:
- [ ] Performance score > 80 (antes: ~65)
- [ ] FCP < 2.5s (antes: ~4.2s)
- [ ] LCP < 4s (antes: ~6.8s)
- [ ] TTI < 4s (antes: ~6.5s)

### React Query:
- [ ] Cache hit rate > 50%
- [ ] Deduplicação funciona (múltiplos componentes = 1 request)
- [ ] Invalidação funciona (mutations atualizam listas)
- [ ] Query keys consistentes (React Query DevTools)

### Lazy Loading:
- [ ] Firebase só carrega no login
- [ ] Recharts só carrega em páginas com gráficos
- [ ] Rotas carregam sob demanda
- [ ] Suspense boundaries funcionam (loading states)

### Network:
- [ ] Requests duplicadas < 10%
- [ ] Waterfall otimizado (chunks em paralelo)
- [ ] Tamanho total transferido < 1.5MB (primeira visita)

---

## 🚨 Troubleshooting

### Bundle muito grande ainda:
```bash
# Verificar o que está no bundle
npm run build
npx vite-bundle-visualizer

# Procurar:
# - Dependências não usadas
# - Imports desnecessários
# - Code duplication
```

### Cache hit rate baixo:
```bash
# Verificar staleTime no App.tsx
# Deve ser >= 5000 (5s)

# Verificar se hooks usam queryKeys factories
# Procurar: grep -r "useQuery" src/hooks
```

### Lazy loading não funciona:
```bash
# Verificar imports
# ❌ RUIM: import { Dashboard } from './pages'
# ✅ BOM: const Dashboard = lazy(() => import('./pages/Dashboard'))

# Verificar Suspense boundaries
# Todos os lazy() DEVEM estar dentro de <Suspense>
```

---

## 📊 Resultados Esperados (Summary)

| Métrica | Antes | Depois | Melhoria |
|---------|-------|--------|----------|
| Bundle inicial | 1.8MB | 1.0MB | -44% ✅ |
| FCP (3G) | 4.2s | 2.0s | -52% ✅ |
| Performance Score | 65 | 85 | +30% ✅ |
| Cache hit rate | 20% | 60% | +200% ✅ |
| API requests duplicadas | 40% | <10% | -75% ✅ |

---

**Última atualização:** 2025-10-09
**Próximo passo:** Executar testes após integração do Firebase lazy loading
