# Fase 2 - Plano de Implementação: Otimizações Avançadas
**Data:** 09 de Outubro de 2025
**Status:** 🚀 PLANEJAMENTO
**Baseado em:** Review Abrangente 2025-10-09
**Metodologia:** SPARC Multi-Agent Parallel Execution

---

## 📊 Visão Geral da Fase 2

### Objetivos Principais

A Fase 2 foca em otimizações de performance, qualidade de código e cobertura de testes, elevando o sistema de **8.1/10 para 9.0+/10**.

**Prioridades:**
1. **Performance Backend** - Eliminar N+1 queries, adicionar monitoring
2. **Performance Frontend** - Cache persistente, otimizações React Query
3. **Cobertura de Testes** - Aumentar de 4.2% para 70%+ no frontend
4. **Code Quality** - Refatorar componentes grandes, consolidar serviços
5. **Monitoring** - Adicionar observability completa

### Impacto Esperado

| Métrica | Atual | Meta Fase 2 | Melhoria |
|---------|-------|-------------|----------|
| **Score Geral** | 8.1/10 | 9.0+/10 | +11% |
| **Performance Backend** | 7.5/10 | 9.0/10 | +20% |
| **Performance Frontend** | 7.0/10 | 8.5/10 | +21% |
| **Cobertura Testes Frontend** | 4.2% | 70%+ | +1567% |
| **Query Performance** | N+1 issues | Eager loading | +60-70% |
| **API Response Time** | ~200ms | ~50-100ms | +50-75% |

---

## 🎯 Fase 2.1 - Performance Backend (P1)

### Objetivos
- Eliminar N+1 queries nos 20 repositórios mais usados
- Adicionar query monitoring e alertas
- Implementar query result caching
- Otimizar database connection pooling

### Tarefas

#### 1. Query Optimization Framework
**Estimativa:** 8-12 horas | **Prioridade:** ALTA

**Implementação:**
```python
# backend-hormonia/app/utils/query_optimizer.py
from sqlalchemy.orm import joinedload, selectinload
from functools import wraps
import logging

logger = logging.getLogger(__name__)

def optimized_query(relationships: dict):
    """
    Decorator para aplicar eager loading automaticamente.

    Args:
        relationships: Dict com config de eager loading
            {
                'one_to_one': ['doctor', 'profile'],
                'one_to_many': ['messages', 'alerts']
            }
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            query = func(*args, **kwargs)

            # Aplicar joinedload para 1:1
            for rel in relationships.get('one_to_one', []):
                query = query.options(joinedload(rel))

            # Aplicar selectinload para 1:many
            for rel in relationships.get('one_to_many', []):
                query = query.options(selectinload(rel))

            return query
        return wrapper
    return decorator
```

**Uso:**
```python
# backend-hormonia/app/repositories/patient.py
@optimized_query({
    'one_to_one': ['doctor', 'current_treatment'],
    'one_to_many': ['messages', 'alerts', 'flow_states']
})
def get_patients_list(self, filters=None):
    query = self.db.query(Patient)
    # filters aplicados...
    return query.all()
```

#### 2. Query Performance Monitoring
**Estimativa:** 4-6 horas | **Prioridade:** ALTA

**Implementação:**
```python
# backend-hormonia/app/middleware/query_monitor.py
from sqlalchemy import event
from time import time

class QueryMonitor:
    def __init__(self, threshold_ms: int = 100):
        self.threshold_ms = threshold_ms
        self.slow_queries = []

    def log_slow_query(self, query, duration_ms):
        if duration_ms > self.threshold_ms:
            logger.warning(
                f"Slow query detected: {duration_ms}ms\n"
                f"Query: {query}"
            )
            self.slow_queries.append({
                'query': str(query),
                'duration_ms': duration_ms,
                'timestamp': time()
            })

# Setup event listener
@event.listens_for(Engine, "before_cursor_execute")
def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    conn.info.setdefault('query_start_time', []).append(time())

@event.listens_for(Engine, "after_cursor_execute")
def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    total = time() - conn.info['query_start_time'].pop()
    monitor.log_slow_query(statement, total * 1000)
```

#### 3. Repository Updates (Top 20)
**Estimativa:** 16-20 horas | **Prioridade:** ALTA

**Repositórios Prioritários:**
1. ✅ `patient.py` - Já otimizado
2. ✅ `flow.py` - Já otimizado
3. ✅ `alert.py` - Já otimizado
4. ✅ `quiz.py` - Já otimizado
5. ✅ `report.py` - Já otimizado
6. 🔄 `treatment.py` - PENDENTE
7. 🔄 `appointment.py` - PENDENTE
8. 🔄 `notification.py` - PENDENTE
9. 🔄 `document.py` - PENDENTE
10. 🔄 `prescription.py` - PENDENTE
11. 🔄 `lab_result.py` - PENDENTE
12. 🔄 `vital_sign.py` - PENDENTE
13. 🔄 `medication.py` - PENDENTE
14. 🔄 `symptom.py` - PENDENTE
15. 🔄 `side_effect.py` - PENDENTE
16. 🔄 `care_plan.py` - PENDENTE
17. 🔄 `referral.py` - PENDENTE
18. 🔄 `insurance.py` - PENDENTE
19. 🔄 `billing.py` - PENDENTE
20. 🔄 `audit_trail.py` - PENDENTE

**Padrão de Implementação:**
- Adicionar eager loading aos métodos `list()` e `get_by_id()`
- Criar métodos `*_with_relations()` para casos de uso específicos
- Documentar relações carregadas e impacto de performance
- Adicionar testes de performance

#### 4. Query Result Caching
**Estimativa:** 6-8 horas | **Prioridade:** MÉDIA

**Implementação:**
```python
# backend-hormonia/app/utils/query_cache.py
from functools import wraps
from app.core.redis_factory import get_redis

def cached_query(ttl: int = 300, key_prefix: str = 'query'):
    """
    Cache query results in Redis.

    Args:
        ttl: Time to live in seconds (default: 5 minutes)
        key_prefix: Prefix for Redis key
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Gerar cache key baseado em args/kwargs
            cache_key = f"{key_prefix}:{func.__name__}:{hash(str(args))}{hash(str(kwargs))}"

            # Tentar buscar do cache
            redis = get_redis('cache')
            cached = await redis.get(cache_key)

            if cached:
                logger.debug(f"Cache HIT: {cache_key}")
                return json.loads(cached)

            # Cache MISS: executar query
            logger.debug(f"Cache MISS: {cache_key}")
            result = await func(*args, **kwargs)

            # Armazenar no cache
            await redis.setex(cache_key, ttl, json.dumps(result))

            return result
        return wrapper
    return decorator
```

### Deliverables Fase 2.1

- [ ] `app/utils/query_optimizer.py` - Framework de otimização
- [ ] `app/middleware/query_monitor.py` - Monitoring de queries lentas
- [ ] `app/utils/query_cache.py` - Sistema de cache de queries
- [ ] 15 repositórios atualizados com eager loading
- [ ] `docs/backend/QUERY_OPTIMIZATION_GUIDE.md` - Guia de otimização
- [ ] Testes de performance para queries otimizadas
- [ ] Dashboard de monitoring (opcional)

### Métricas de Sucesso

- [ ] 90%+ das queries principais com eager loading
- [ ] Query count reduzido em 60-70%
- [ ] 0 queries > 500ms em operações comuns
- [ ] Cache hit rate > 70% em queries frequentes
- [ ] Documentação completa de padrões de otimização

---

## 🚀 Fase 2.2 - Performance Frontend (P1)

### Objetivos
- Implementar cache persistente para React Query
- Otimizar re-renders com React.memo e useMemo
- Adicionar service worker para offline support
- Implementar query deduplication avançado

### Tarefas

#### 1. React Query Persistent Cache
**Estimativa:** 6-8 horas | **Prioridade:** ALTA

**Implementação:**
```typescript
// frontend-hormonia/src/lib/react-query/persistor.ts
import { PersistedClient, Persistor } from '@tanstack/react-query-persist-client'
import { del, get, set } from 'idb-keyval'

/**
 * IndexedDB persistor for React Query cache
 * Stores query results in browser's IndexedDB for offline access
 */
export function createIDBPersistor(idbValidKey: IDBValidKey = 'reactQuery'): Persistor {
  return {
    persistClient: async (client: PersistedClient) => {
      await set(idbValidKey, client)
    },
    restoreClient: async () => {
      return await get<PersistedClient>(idbValidKey)
    },
    removeClient: async () => {
      await del(idbValidKey)
    },
  }
}

// frontend-hormonia/src/App.tsx
import { PersistQueryClientProvider } from '@tanstack/react-query-persist-client'
import { createIDBPersistor } from './lib/react-query/persistor'

const persister = createIDBPersistor()

function App() {
  return (
    <PersistQueryClientProvider
      client={queryClient}
      persistOptions={{
        persister,
        maxAge: 1000 * 60 * 60 * 24, // 24 horas
        dehydrateOptions: {
          // Não persistir queries sensíveis
          shouldDehydrateQuery: (query) => {
            return !query.queryKey.includes('sensitive')
          }
        }
      }}
    >
      {/* App content */}
    </PersistQueryClientProvider>
  )
}
```

#### 2. Advanced Query Deduplication
**Estimativa:** 4-6 horas | **Prioridade:** MÉDIA

**Implementação:**
```typescript
// frontend-hormonia/src/lib/react-query/queryClient.ts
import { QueryClient } from '@tanstack/react-query'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Deduplication avançado
      staleTime: 5 * 60 * 1000, // 5 minutos
      gcTime: 10 * 60 * 1000, // 10 minutos (cache)

      // Network-first com fallback para cache
      networkMode: 'online',

      // Refetch inteligente
      refetchOnWindowFocus: false,
      refetchOnReconnect: true,
      refetchOnMount: false,

      // Retry com exponential backoff
      retry: (failureCount, error: any) => {
        // Não retenta erros 4xx
        if (error?.response?.status >= 400 && error?.response?.status < 500) {
          return false
        }
        return failureCount < 3
      },
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
    },
    mutations: {
      retry: 1,
      // Invalidação automática de queries relacionadas
      onSuccess: (data, variables, context: any) => {
        if (context?.invalidateQueries) {
          context.invalidateQueries.forEach((queryKey: string[]) => {
            queryClient.invalidateQueries({ queryKey })
          })
        }
      }
    }
  }
})
```

#### 3. React Performance Optimization
**Estimativa:** 8-12 horas | **Prioridade:** MÉDIA

**Padrões a Implementar:**
```typescript
// 1. Memoização de componentes pesados
export const PatientCard = React.memo(({ patient }) => {
  // Renderização...
}, (prevProps, nextProps) => {
  // Custom comparison
  return prevProps.patient.id === nextProps.patient.id &&
         prevProps.patient.updated_at === nextProps.patient.updated_at
})

// 2. useMemo para cálculos pesados
function PatientDashboard({ patients }) {
  const statistics = useMemo(() => {
    return calculateComplexStatistics(patients)
  }, [patients])

  return <StatisticsView data={statistics} />
}

// 3. useCallback para event handlers
function PatientList({ onPatientClick }) {
  const handleClick = useCallback((patientId) => {
    onPatientClick(patientId)
  }, [onPatientClick])

  return patients.map(p => <PatientCard onClick={handleClick} />)
}
```

#### 4. Service Worker para Offline Support
**Estimativa:** 10-12 horas | **Prioridade:** BAIXA

**Implementação:**
```typescript
// frontend-hormonia/src/service-worker.ts
import { precacheAndRoute } from 'workbox-precaching'
import { registerRoute } from 'workbox-routing'
import { CacheFirst, NetworkFirst, StaleWhileRevalidate } from 'workbox-strategies'
import { ExpirationPlugin } from 'workbox-expiration'

// Cache de assets estáticos (build assets)
precacheAndRoute(self.__WB_MANIFEST)

// API calls: Network-first com fallback para cache
registerRoute(
  ({ url }) => url.pathname.startsWith('/api/'),
  new NetworkFirst({
    cacheName: 'api-cache',
    plugins: [
      new ExpirationPlugin({
        maxEntries: 50,
        maxAgeSeconds: 5 * 60, // 5 minutos
      })
    ]
  })
)

// Imagens: Cache-first com expiração
registerRoute(
  ({ request }) => request.destination === 'image',
  new CacheFirst({
    cacheName: 'images-cache',
    plugins: [
      new ExpirationPlugin({
        maxEntries: 100,
        maxAgeSeconds: 30 * 24 * 60 * 60, // 30 dias
      })
    ]
  })
)
```

### Deliverables Fase 2.2

- [ ] `src/lib/react-query/persistor.ts` - IndexedDB persistor
- [ ] `src/lib/react-query/queryClient.ts` - Query client otimizado
- [ ] `src/service-worker.ts` - Service worker com Workbox
- [ ] 10+ componentes refatorados com React.memo
- [ ] `docs/frontend/PERFORMANCE_OPTIMIZATION_GUIDE.md`
- [ ] Testes de performance (Lighthouse CI)

### Métricas de Sucesso

- [ ] Cache hit rate > 60% em queries frequentes
- [ ] Re-renders reduzidos em 40%+
- [ ] Lighthouse Performance Score > 90
- [ ] Offline functionality para operações críticas
- [ ] FCP < 1.5s, LCP < 2.5s, CLS < 0.1

---

## 🧪 Fase 2.3 - Cobertura de Testes Frontend (P1)

### Objetivos
- Aumentar cobertura de 4.2% para 70%+
- Implementar testes de componentes críticos
- Adicionar testes de integração E2E
- Configurar CI/CD com coverage enforcement

### Tarefas

#### 1. Test Infrastructure Setup
**Estimativa:** 4-6 horas | **Prioridade:** ALTA

**Configuração:**
```typescript
// frontend-hormonia/vitest.config.ts
export default defineConfig({
  test: {
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html', 'lcov'],
      exclude: [
        'node_modules/',
        'tests/',
        '**/*.test.{ts,tsx}',
        '**/*.spec.{ts,tsx}',
        '**/types.ts',
        '**/*.d.ts'
      ],
      thresholds: {
        lines: 70,
        functions: 70,
        branches: 70,
        statements: 70
      }
    }
  }
})
```

#### 2. Component Tests (40 componentes críticos)
**Estimativa:** 40-50 horas | **Prioridade:** ALTA

**Categorias:**
- **Auth Components** (8 componentes): LoginPage, RegisterPage, ProtectedRoute, etc.
- **Dashboard Components** (12 componentes): PatientDashboard, Analytics, Charts, etc.
- **Form Components** (10 componentes): PatientForm, AppointmentForm, etc.
- **UI Components** (10 componentes): Modal, Table, Button, Input, etc.

**Padrão de Teste:**
```typescript
// tests/components/LoginPage.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { LoginPage } from '@/pages/LoginPage'
import { AuthProvider } from '@/contexts/AuthContext'
import { QueryClientProvider } from '@tanstack/react-query'

describe('LoginPage', () => {
  it('should render login form', () => {
    render(<LoginPage />, { wrapper: Providers })

    expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /entrar/i })).toBeInTheDocument()
  })

  it('should show validation errors for invalid input', async () => {
    render(<LoginPage />, { wrapper: Providers })

    const submitButton = screen.getByRole('button', { name: /entrar/i })
    fireEvent.click(submitButton)

    await waitFor(() => {
      expect(screen.getByText(/email é obrigatório/i)).toBeInTheDocument()
    })
  })

  it('should call login API on valid submit', async () => {
    const mockLogin = vi.fn().mockResolvedValue({ success: true })
    render(<LoginPage />, { wrapper: Providers })

    // Preencher formulário
    fireEvent.change(screen.getByLabelText(/email/i), {
      target: { value: 'test@example.com' }
    })
    fireEvent.change(screen.getByLabelText(/password/i), {
      target: { value: 'password123' }
    })

    // Submeter
    fireEvent.click(screen.getByRole('button', { name: /entrar/i }))

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith({
        email: 'test@example.com',
        password: 'password123'
      })
    })
  })
})
```

#### 3. Hook Tests (20 hooks)
**Estimativa:** 20-25 horas | **Prioridade:** ALTA

**Hooks Prioritários:**
- `useAuth`, `useAuthSubmit`, `useSessionManagement`
- `usePatients`, `usePatient`, `useCreatePatient`
- `useMessages`, `useWebSocket`
- `useApi`, `useMutation`

#### 4. Integration Tests (E2E)
**Estimativa:** 16-20 horas | **Prioridade:** MÉDIA

**Cenários de Teste:**
```typescript
// tests/e2e/patient-management.spec.ts
import { test, expect } from '@playwright/test'

test.describe('Patient Management', () => {
  test('should create new patient', async ({ page }) => {
    // Login
    await page.goto('/login')
    await page.fill('[name="email"]', 'doctor@example.com')
    await page.fill('[name="password"]', 'password123')
    await page.click('button:has-text("Entrar")')

    // Navegar para cadastro de pacientes
    await page.click('a:has-text("Pacientes")')
    await page.click('button:has-text("Novo Paciente")')

    // Preencher formulário
    await page.fill('[name="name"]', 'João Silva')
    await page.fill('[name="email"]', 'joao@example.com')
    await page.fill('[name="phone"]', '11999999999')
    await page.fill('[name="birthdate"]', '1980-01-01')

    // Submeter
    await page.click('button:has-text("Salvar")')

    // Verificar sucesso
    await expect(page.locator('text=Paciente criado com sucesso')).toBeVisible()
  })
})
```

### Deliverables Fase 2.3

- [ ] 40+ arquivos de teste de componentes
- [ ] 20+ arquivos de teste de hooks
- [ ] 10+ cenários E2E com Playwright
- [ ] Coverage report > 70%
- [ ] CI/CD com coverage enforcement
- [ ] `docs/frontend/TESTING_GUIDE.md`

### Métricas de Sucesso

- [ ] Cobertura de testes > 70% (linhas, funções, branches)
- [ ] 100% dos componentes críticos testados
- [ ] 100% dos hooks testados
- [ ] 10+ cenários E2E cobrindo fluxos principais
- [ ] CI/CD bloqueando PRs com coverage < 70%

---

## 📐 Fase 2.4 - Code Quality & Refactoring (P2)

### Objetivos
- Refatorar componentes grandes (>300 linhas)
- Consolidar serviços backend duplicados
- Resolver TODOs/FIXMEs críticos
- Implementar linting rules rigorosas

### Tarefas

#### 1. Frontend Component Refactoring
**Estimativa:** 12-16 horas | **Prioridade:** MÉDIA

**Componentes Alvo:**
- `AuthContext.tsx` (445 linhas) → Split em 3 módulos
- `ApiClient.ts` (938 linhas) → Split por domínio (auth, patients, etc.)
- `MedicoAuthContext.tsx` (300+ linhas) → Consolidar com AuthContext
- `AdminAuthContext.tsx` (250+ linhas) → Consolidar com AuthContext

**Padrão de Refatoração:**
```typescript
// ANTES: AuthContext.tsx (445 linhas)
export function AuthProvider({ children }) {
  // 445 linhas de lógica misturada
}

// DEPOIS: Split em módulos
// auth/AuthProvider.tsx (150 linhas)
// auth/useAuthState.ts (100 linhas)
// auth/useAuthActions.ts (100 linhas)
// auth/useSessionManagement.ts (95 linhas)
export function AuthProvider({ children }) {
  const state = useAuthState()
  const actions = useAuthActions()
  const session = useSessionManagement()

  return (
    <AuthContext.Provider value={{ ...state, ...actions, ...session }}>
      {children}
    </AuthContext.Provider>
  )
}
```

#### 2. Backend Service Consolidation
**Estimativa:** 24-32 horas | **Prioridade:** BAIXA

**Serviços a Consolidar:**
- 4 arquivos de flow engine → 1 serviço unificado
- 3 arquivos de AI cache → 1 serviço unificado
- Duplicação em repositories → Base repository class

#### 3. TODO/FIXME Resolution
**Estimativa:** 40-60 horas | **Prioridade:** BAIXA

**Processo:**
1. Categorizar 337 TODOs por prioridade
2. Resolver P0/P1 (estimado: 50-80 TODOs)
3. Documentar P2/P3 como issues no GitHub
4. Remover TODOs obsoletos

### Deliverables Fase 2.4

- [ ] 4 componentes grandes refatorados
- [ ] 3-5 serviços backend consolidados
- [ ] 50-80 TODOs resolvidos
- [ ] ESLint config atualizado
- [ ] `docs/CODE_QUALITY_STANDARDS.md`

---

## 📊 Fase 2.5 - Monitoring & Observability (P2)

### Objetivos
- Implementar logging estruturado
- Adicionar métricas de performance
- Configurar alertas automáticos
- Dashboard de health monitoring

### Tarefas

#### 1. Structured Logging
**Estimativa:** 8-12 horas | **Prioridade:** MÉDIA

**Implementação:**
```python
# backend-hormonia/app/utils/structured_logger.py
import structlog
from pythonjsonlogger import jsonlogger

def configure_logging():
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

# Uso
logger = structlog.get_logger()
logger.info("patient_created", patient_id=123, doctor_id=456, timestamp=now())
```

#### 2. Performance Metrics
**Estimativa:** 10-14 horas | **Prioridade:** MÉDIA

**Métricas a Coletar:**
- Request duration (p50, p95, p99)
- Query duration
- Cache hit rate
- Error rate
- Active connections

#### 3. Health Check Endpoints
**Estimativa:** 4-6 horas | **Prioridade:** ALTA

**Implementação:**
```python
# backend-hormonia/app/api/v1/health.py
@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "database": await check_database(),
            "redis": await check_redis(),
            "firebase": await check_firebase()
        }
    }

@router.get("/metrics")
async def metrics():
    return {
        "requests_total": request_counter.get(),
        "requests_duration_p95": get_percentile(95),
        "active_connections": connection_pool.active_count,
        "query_cache_hit_rate": cache.hit_rate(),
        "error_rate_5min": error_counter.rate(300)
    }
```

### Deliverables Fase 2.5

- [ ] Structured logging configurado
- [ ] Prometheus metrics endpoint
- [ ] Health check endpoints
- [ ] Grafana dashboard (opcional)
- [ ] Alerting rules configuradas
- [ ] `docs/MONITORING_GUIDE.md`

---

## 📅 Cronograma de Execução

### Fase 2 Completa: 6-8 semanas

| Fase | Duração | Dependências | Prioridade |
|------|---------|--------------|------------|
| **2.1 - Performance Backend** | 2-3 semanas | Fase 1 completa | ALTA |
| **2.2 - Performance Frontend** | 1-2 semanas | Fase 1 completa | ALTA |
| **2.3 - Testes Frontend** | 2-3 semanas | 2.2 completa | ALTA |
| **2.4 - Code Quality** | 2-4 semanas | Paralelo com outras | MÉDIA |
| **2.5 - Monitoring** | 1-2 semanas | Paralelo com outras | MÉDIA |

### Execução Paralela Recomendada

**Sprints de 2 semanas:**

**Sprint 1-2 (Semanas 1-4):**
- Fase 2.1 (Performance Backend) - Lead Agent: backend-dev
- Fase 2.2 (Performance Frontend) - Lead Agent: performance-optimizer
- Fase 2.5 (Monitoring Setup) - Lead Agent: cicd-engineer

**Sprint 3-4 (Semanas 5-8):**
- Fase 2.3 (Testes Frontend) - Lead Agent: tester
- Fase 2.4 (Code Quality) - Lead Agent: refactoring-expert
- Fase 2.5 (Monitoring Completion) - Lead Agent: cicd-engineer

---

## 🎯 Critérios de Sucesso

### Performance
- [ ] API response time p95 < 100ms
- [ ] N+1 queries eliminados em 90%+ das operações
- [ ] Cache hit rate > 70%
- [ ] FCP < 1.5s, LCP < 2.5s
- [ ] Lighthouse Performance Score > 90

### Quality
- [ ] Cobertura de testes > 70%
- [ ] Zero componentes > 400 linhas
- [ ] Zero serviços duplicados
- [ ] 50-80 TODOs resolvidos
- [ ] ESLint sem warnings

### Monitoring
- [ ] Structured logging implementado
- [ ] Métricas de performance coletadas
- [ ] Health checks funcionando
- [ ] Alertas configurados
- [ ] Dashboard de monitoring ativo

### Score Geral
- [ ] Score aumentado de 8.1/10 para 9.0+/10
- [ ] Todas categorias > 8.5/10
- [ ] Zero problemas P0/P1 pendentes

---

## 📚 Documentação a Criar

1. `QUERY_OPTIMIZATION_GUIDE.md` - Padrões de otimização de queries
2. `PERFORMANCE_OPTIMIZATION_GUIDE.md` - Otimizações frontend
3. `TESTING_GUIDE.md` - Estratégias e padrões de teste
4. `CODE_QUALITY_STANDARDS.md` - Padrões de código
5. `MONITORING_GUIDE.md` - Observability e alerting

---

## 🚀 Próximos Passos

1. **Aprovação do Plano:** Revisar e aprovar este plano
2. **Setup de Agents:** Configurar 6-8 agentes especializados
3. **Kick-off Sprint 1:** Iniciar Fases 2.1, 2.2, 2.5 em paralelo
4. **Weekly Reviews:** Review de progresso semanalmente
5. **Sprint 2 Planning:** Planejar Sprint 2 após 2 semanas

Quer que eu inicie a execução da Fase 2.1 (Performance Backend) agora ou prefere revisar o plano primeiro?

---

**END OF PLAN**
