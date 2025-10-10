# Query Keys Migration Guide

## 📋 Objetivo

Migrar todos os hooks personalizados para usar as **query key factories** criadas em `src/lib/query-keys.ts`, garantindo:
- ✅ Cache consistency (mesmas keys em todos os componentes)
- ✅ Deduplicação automática (staleTime: 5s)
- ✅ Invalidação inteligente (helpers prontos)
- ✅ Type safety (TypeScript)

---

## 🔍 Como Encontrar Hooks para Migrar

```bash
# Buscar todos os hooks que usam useQuery/useMutation
grep -r "useQuery" frontend-hormonia/src/hooks --include="*.ts" --include="*.tsx"

# Buscar hooks que NÃO usam queryKeys
grep -r "useQuery" frontend-hormonia/src/hooks -A 3 | grep -v "queryKeys"
```

---

## ✅ Padrão de Migração

### ANTES (Query keys inline - ❌ RUIM)

```typescript
// hooks/usePatients.ts
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api-client';

export function usePatients(page: number, status?: string) {
  return useQuery({
    // ❌ Query key inline - dificulta invalidação e cache consistency
    queryKey: ['patients', page, status],
    queryFn: () => apiClient.patients.list({ page, status })
  });
}
```

**Problemas:**
- ❌ Keys inconsistentes entre componentes
- ❌ Dificulta invalidação (precisa saber estrutura exata)
- ❌ Sem type safety
- ❌ Duplicação de código

### DEPOIS (Query key factory - ✅ BOM)

```typescript
// hooks/usePatients.ts
import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '@/lib/query-keys';
import { apiClient } from '@/lib/api-client';

export function usePatients(page: number, status?: string) {
  return useQuery({
    // ✅ Query key factory - consistente, type-safe, fácil invalidação
    queryKey: queryKeys.patients.list({ page, status }),
    queryFn: () => apiClient.patients.list({ page, status })
  });
}
```

**Benefícios:**
- ✅ Keys consistentes em toda a app
- ✅ Invalidação fácil: `invalidateQueries.allPatients(queryClient)`
- ✅ Type safety completo
- ✅ Código centralizado

---

## 📝 Exemplos de Migração por Tipo

### 1. Lista com Filtros

```typescript
// ❌ ANTES
queryKey: ['patients', { page, size, search, status }]

// ✅ DEPOIS
queryKey: queryKeys.patients.list({ page, size, search, status })
```

### 2. Detalhes de Item

```typescript
// ❌ ANTES
queryKey: ['patient', id]

// ✅ DEPOIS
queryKey: queryKeys.patients.detail(id)
```

### 3. Relacionamentos (timeline, stats, etc.)

```typescript
// ❌ ANTES
queryKey: ['patient-timeline', patientId]

// ✅ DEPOIS
queryKey: queryKeys.patients.timeline(patientId)
```

### 4. Analytics com Datas

```typescript
// ❌ ANTES
queryKey: ['analytics-engagement', startDate, endDate]

// ✅ DEPOIS
queryKey: queryKeys.analytics.engagement({ start_date: startDate, end_date: endDate })
```

### 5. Quiz/Questionários

```typescript
// ❌ ANTES
queryKey: ['quiz-sessions', { patient_id: patientId, status }]

// ✅ DEPOIS
queryKey: queryKeys.quiz.sessions({ patient_id: patientId, status })
```

---

## 🎯 Hooks Prioritários para Migrar

### P0 - Alta Frequência (fazer primeiro)

1. **usePatients** (lista de pacientes)
   - Usado em: PatientsPage, PhysicianDashboard
   - Key atual: `['patients', filters]`
   - Nova key: `queryKeys.patients.list(filters)`

2. **usePatientDetail** (detalhes do paciente)
   - Usado em: PatientDetailPage, PhysicianDashboard
   - Key atual: `['patient', id]`
   - Nova key: `queryKeys.patients.detail(id)`

3. **useDashboardAnalytics** (analytics do dashboard)
   - Usado em: DashboardPage
   - Key atual: `['dashboard-analytics']`
   - Nova key: `queryKeys.analytics.dashboard()`

4. **useEngagementData** (dados de engajamento)
   - Usado em: DashboardPage
   - Key atual: `['engagement', params]`
   - Nova key: `queryKeys.analytics.engagement(params)`

### P1 - Média Frequência

5. **useQuizSessions** (sessões de quiz)
   - Key atual: `['quiz-sessions', filters]`
   - Nova key: `queryKeys.quiz.sessions(filters)`

6. **useMessages** (mensagens)
   - Key atual: `['messages', patientId]`
   - Nova key: `queryKeys.messages.list({ patient_id: patientId })`

7. **useFlows** (fluxos)
   - Key atual: `['flows', patientId]`
   - Nova key: `queryKeys.flows.list({ patient_id: patientId })`

### P2 - Baixa Frequência

8. **useAlerts** (alertas)
9. **useReports** (relatórios)
10. **useAdminUsers** (usuários admin)

---

## 🔧 Template de Migração

```typescript
// hooks/use[Entity].ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { queryKeys, invalidateQueries } from '@/lib/query-keys';
import { apiClient } from '@/lib/api-client';

/**
 * Hook para listar [entidade] com filtros
 */
export function use[Entity]List(filters: { /* ... */ }) {
  return useQuery({
    queryKey: queryKeys.[entity].list(filters),
    queryFn: () => apiClient.[entity].list(filters),
    // Configuração global de staleTime/gcTime já aplicada em App.tsx
  });
}

/**
 * Hook para obter detalhes de [entidade]
 */
export function use[Entity]Detail(id: string) {
  return useQuery({
    queryKey: queryKeys.[entity].detail(id),
    queryFn: () => apiClient.[entity].get(id),
    enabled: !!id, // Só executa se ID existir
  });
}

/**
 * Hook para criar [entidade] com invalidação automática
 */
export function useCreate[Entity]() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: any) => apiClient.[entity].create(data),
    onSuccess: () => {
      // Invalida todas as listas da entidade
      invalidateQueries.all[Entity]s(queryClient);
    }
  });
}

/**
 * Hook para atualizar [entidade] com invalidação específica
 */
export function useUpdate[Entity]() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) =>
      apiClient.[entity].update(id, data),
    onSuccess: (_, { id }) => {
      // Invalida apenas o item específico
      invalidateQueries.[entity](queryClient, id);
    }
  });
}
```

---

## 🧪 Testando a Migração

### 1. Verificar Cache Consistency

```typescript
// Em React Query DevTools
// ANTES: Verá keys inconsistentes
// ['patients', 1]
// ['patients', { page: 1 }]
// ['patient-list', { page: 1 }]

// DEPOIS: Keys consistentes
// ['patients', 'list', { page: 1 }]
// ['patients', 'list', { page: 1, status: 'active' }]
```

### 2. Testar Deduplicação

```typescript
// Abra 2 componentes que usam usePatients(1)
// ANTES: 2 requests simultâneas
// DEPOIS: 1 request compartilhada (deduped)

// Verifique no Network tab do DevTools
```

### 3. Testar Invalidação

```typescript
// Após criar paciente
// ANTES: Precisa refresh manual ou invalidação manual complexa
// DEPOIS: Lista atualiza automaticamente via invalidateQueries.allPatients()
```

---

## 📊 Checklist de Migração

### Hooks para Migrar:
- [ ] `usePatients` → `queryKeys.patients.list()`
- [ ] `usePatientDetail` → `queryKeys.patients.detail()`
- [ ] `usePatientTimeline` → `queryKeys.patients.timeline()`
- [ ] `useDashboardAnalytics` → `queryKeys.analytics.dashboard()`
- [ ] `useEngagementData` → `queryKeys.analytics.engagement()`
- [ ] `useTreatmentDistribution` → `queryKeys.analytics.treatmentDistribution()`
- [ ] `useQuizTemplates` → `queryKeys.quiz.templates()`
- [ ] `useQuizSessions` → `queryKeys.quiz.sessions()`
- [ ] `useMonthlyQuizStats` → `queryKeys.quiz.monthlyStats()`
- [ ] `useMessages` → `queryKeys.messages.list()`
- [ ] `useFlows` → `queryKeys.flows.list()`
- [ ] `useFlowState` → `queryKeys.flows.state()`
- [ ] `useAlerts` → `queryKeys.alerts.list()`
- [ ] `useReports` → `queryKeys.reports.list()`
- [ ] `useAdminUsers` → `queryKeys.admin.users()`

### Validação:
- [ ] React Query DevTools instalado
- [ ] Verificar cache consistency (keys uniformes)
- [ ] Testar deduplicação (1 request para múltiplos componentes)
- [ ] Testar invalidação (listas atualizam após mutations)
- [ ] Medir cache hit rate (esperado: >50%)

---

## 🚨 Armadilhas Comuns

### 1. Parâmetros undefined/null

```typescript
// ❌ RUIM: undefined cria keys diferentes
queryKeys.patients.list({ page, status: undefined })
// ['patients', 'list', { page: 1, status: undefined }]

queryKeys.patients.list({ page })
// ['patients', 'list', { page: 1 }]

// ✅ BOM: Sempre omita parâmetros undefined
const filters = { page };
if (status) filters.status = status;
queryKeys.patients.list(filters);
```

### 2. Order dos parâmetros

```typescript
// ❌ RUIM: Ordem importa em objetos JavaScript
queryKeys.patients.list({ status: 'active', page: 1 })
queryKeys.patients.list({ page: 1, status: 'active' })
// São keys DIFERENTES!

// ✅ BOM: Use factory que normaliza ordem
// queryKeys já garante ordem consistente
```

### 3. Tipos complexos

```typescript
// ❌ RUIM: Objetos complexos não funcionam bem
queryKeys.patients.list({ filter: new Date() })

// ✅ BOM: Converta para primitivos
queryKeys.patients.list({ filter: date.toISOString() })
```

---

## 📚 Recursos

- **Query Keys Factory:** `src/lib/query-keys.ts`
- **React Query Docs:** https://tanstack.com/query/latest/docs/react/guides/query-keys
- **Invalidation Guide:** https://tanstack.com/query/latest/docs/react/guides/query-invalidation
- **DevTools:** https://tanstack.com/query/latest/docs/react/devtools

---

**Última atualização:** 2025-10-09
**Próxima revisão:** Após migração dos hooks P0
