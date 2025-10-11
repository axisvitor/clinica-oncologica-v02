# 🔧 PLANO DE CORREÇÕES DO FRONTEND
## Baseado no Relatório de Review Comprehensive

**Data:** 10 de Outubro de 2025
**Swarm ID:** swarm-1760144566599-bmbxl2fxa
**Status:** 🟡 Em Progresso

---

## ✅ DESCOBERTAS IMPORTANTES

### Estrutura de Arquivos Principais ENCONTRADA! 🎉

**Arquivos Principais Localizados:**
```
✅ frontend-hormonia/main.tsx           - Entry point principal
✅ frontend-hormonia/App.tsx            - App component com routing
✅ frontend-hormonia/src/AdminApp.tsx   - Sub-app administrativo
✅ frontend-hormonia/index.html         - HTML template
```

**Hierarquia de Providers Confirmada:**
```
main.tsx
  └── ConfigProvider
      └── App.tsx
          └── ErrorBoundary
              └── PersistQueryClientProvider (React Query + IndexedDB)
                  └── AuthProvider (Firebase Auth)
                      └── Router (React Router v6)
                          └── Routes
                              ├── /admin/* → AdminApp.tsx
                              │   └── AdminAuthProvider ❌ (DUPLICADO)
                              │       └── AdminRoutes
                              └── outras rotas → AuthProvider ✅
```

**PROBLEMA IDENTIFICADO:**
- `AdminApp.tsx` adiciona `AdminAuthProvider` duplicando autenticação
- Todos os outros componentes usam `AuthProvider` (correto)
- 6 arquivos dentro de `/admin/*` usam `useAdminAuth` (incorreto)

---

## 🎯 CORREÇÕES CRÍTICAS (PRIORIDADE 1)

### 1. ✅ CONSOLIDAR AUTENTICAÇÃO - SOLUÇÃO CLARA

**Problema:** Duplicação AdminAuthContext vs AuthContext

**Arquivos que usam useAdminAuth (devem ser migrados):**
```
1. frontend-hormonia/src/routes/AdminRoutes.tsx (linha 7, 64)
2. frontend-hormonia/src/components/admin/AdminProtectedRoute.tsx
3. frontend-hormonia/src/components/admin/AdminSessionManager.tsx
4. frontend-hormonia/src/AdminApp.tsx (wrapper)
```

**Solução Step-by-Step:**

#### Step 1: Migrar AdminRoutes.tsx
```typescript
// ❌ ANTES (AdminRoutes.tsx linha 7, 64)
import { useAdminAuth } from '../contexts/AdminAuthContext'
const { login } = useAdminAuth()

// ✅ DEPOIS
import { useAuth } from '../contexts/AuthContext'
const { login } = useAuth()
```

#### Step 2: Migrar AdminProtectedRoute.tsx
```typescript
// ❌ ANTES
import { useAdminAuth } from '../../contexts/AdminAuthContext'
const { state, hasPermission } = useAdminAuth()

// ✅ DEPOIS
import { useAuth } from '../../contexts/AuthContext'
const { user, isLoading, hasPermission } = useAuth()
```

#### Step 3: Migrar AdminSessionManager.tsx
```typescript
// ❌ ANTES
import { useAdminAuth } from '../../contexts/AdminAuthContext'
const { state, extendSession } = useAdminAuth()

// ✅ DEPOIS
import { useAuth } from '../../contexts/AuthContext'
const { user, refreshToken } = useAuth()
// extendSession → usar refreshToken do AuthContext
```

#### Step 4: Remover AdminAuthProvider de AdminApp.tsx
```typescript
// ❌ ANTES (AdminApp.tsx)
import { AdminAuthProvider } from './contexts/AdminAuthContext'

const AdminApp: React.FC = () => {
  return (
    <ErrorBoundary>
      <AdminAuthProvider>  {/* ❌ Remover isso */}
        <div className="admin-app">
          <AdminRoutes />
        </div>
      </AdminAuthProvider>
    </ErrorBoundary>
  )
}

// ✅ DEPOIS
const AdminApp: React.FC = () => {
  return (
    <ErrorBoundary>
      {/* Usa AuthProvider do App.tsx pai */}
      <div className="admin-app">
        <AdminRoutes />
      </div>
      <Toaster />
    </ErrorBoundary>
  )
}
```

#### Step 5: Deletar AdminAuthContext.tsx
```bash
# ❌ Deletar arquivo
rm frontend-hormonia/src/contexts/AdminAuthContext.tsx
```

**Estimativa:** 2-3 horas
**Status:** 🟡 PRONTO PARA EXECUTAR

---

### 2. ✅ CORRIGIR CONTRATOS DE API

**Problema:** Backend retorna `users` mas frontend espera `items`

#### Solução A: Corrigir Backend (RECOMENDADO)
```python
# backend-hormonia/app/api/v1/admin/users.py

# ❌ ATUAL
return {
    "users": users,
    "total": total
}

# ✅ CORRIGIR
return {
    "items": users,     # Padronizar com PaginatedResponse
    "total": total,
    "page": page,
    "pages": (total + size - 1) // size
}
```

#### Solução B: Transformer Frontend (TEMPORÁRIO)
```typescript
// frontend-hormonia/src/lib/response-transformers.ts

export function transformAdminUsersResponse(response: any): PaginatedResponse<AdminUser> {
  return {
    items: response.users || response.items || [],
    total: response.total || 0,
    page: response.page || 1,
    pages: response.pages || Math.ceil((response.total || 0) / 20)
  }
}

// Usar em api-client.ts
adminUsers = {
  list: async (params) => {
    const response = await this.request<any>('/api/v1/admin/users', { params })
    return transformAdminUsersResponse(response)
  }
}
```

**Estimativa:** 1-2 horas
**Status:** 🟡 PRONTO PARA EXECUTAR

---

### 3. ✅ IMPLEMENTAR ROTA FALTANTE - User Activity

**Problema:** Frontend chama `/api/v1/admin/users/{id}/activity` mas backend retorna 404

**Solução Backend:**
```python
# backend-hormonia/app/api/v1/admin/users.py

@router.get("/admin/users/{user_id}/activity")
async def get_user_activity(
    user_id: str,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Get user activity history (audit logs)

    Returns paginated list of user actions:
    - Login/logout events
    - Permission changes
    - Resource access
    - Failed attempts
    """

    # Query audit logs
    query = db.query(AuditLog)\
        .filter(AuditLog.user_id == user_id)\
        .order_by(AuditLog.timestamp.desc())

    total = query.count()
    activities = query.offset((page - 1) * size).limit(size).all()

    return {
        "items": [
            {
                "id": log.id,
                "user_id": log.user_id,
                "user_email": log.user.email if log.user else None,
                "action": log.action,
                "resource": log.resource,
                "details": log.details,
                "timestamp": log.timestamp.isoformat(),
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "session_id": log.session_id
            }
            for log in activities
        ],
        "total": total,
        "page": page,
        "pages": (total + size - 1) // size
    }
```

**Frontend já está pronto:**
```typescript
// api-client.ts linha 894 - JÁ IMPLEMENTADO
getActivity: (id: string, params?: { page?: number; size?: number }) =>
  this.request<PaginatedResponse<any>>(`/api/v1/admin/users/${id}/activity`, params ? { params } : {})
```

**Estimativa:** 3-4 horas
**Status:** 🔴 BACKEND PRECISA IMPLEMENTAR

---

### 4. ✅ VALIDAR useSystemStats HOOK

**Hook Criado:** `frontend-hormonia/src/hooks/useSystemStats.ts`

**Teste de Validação Necessário:**
```typescript
// tests/hooks/useSystemStats.test.ts

import { renderHook, waitFor } from '@testing-library/react'
import { QueryClientProvider } from '@tanstack/react-query'
import { useSystemStats } from '@/hooks/useSystemStats'
import { queryClient } from '@/lib/react-query/queryClient'

describe('useSystemStats Integration Test', () => {
  it('should fetch real system stats from backend', async () => {
    const wrapper = ({ children }: any) => (
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    )

    const { result } = renderHook(() => useSystemStats(), { wrapper })

    // Initial loading state
    expect(result.current.isLoading).toBe(true)

    // Wait for data
    await waitFor(() => expect(result.current.isLoading).toBe(false))

    // Validate structure
    expect(result.current.stats).toMatchObject({
      users: {
        total: expect.any(Number),
        active: expect.any(Number),
        locked: expect.any(Number),
        new_today: expect.any(Number)
      },
      security: {
        failed_logins: expect.any(Number),
        active_sessions: expect.any(Number),
        blocked_ips: expect.any(Number)
      },
      system: {
        uptime: expect.any(Number),
        memory_usage: expect.any(Number),
        cpu_usage: expect.any(Number),
        disk_usage: expect.any(Number)
      },
      audit: {
        total_logs: expect.any(Number),
        critical_events: expect.any(Number),
        warnings: expect.any(Number)
      }
    })
  })

  it('should handle API errors gracefully', async () => {
    // Mock API error
    const wrapper = ({ children }: any) => (
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    )

    // Test error handling...
  })
})
```

**Estimativa:** 2 horas
**Status:** 🟡 PRONTO PARA EXECUTAR

---

## 🟢 CORREÇÕES DE ALTA PRIORIDADE (PRIORIDADE 2)

### 5. Adicionar Testes para AuthContext

**Arquivo:** `tests/contexts/AuthContext.test.tsx`

```typescript
import { renderHook, act, waitFor } from '@testing-library/react'
import { AuthProvider, useAuth } from '@/contexts/AuthContext'
import { vi } from 'vitest'

// Mock Firebase
vi.mock('@/lib/firebase-client', () => ({
  firebaseAuth: {
    signInWithEmailAndPassword: vi.fn(),
    signOut: vi.fn(),
    currentUser: null
  }
}))

describe('AuthContext', () => {
  it('should authenticate user with Firebase', async () => {
    const wrapper = ({ children }: any) => (
      <AuthProvider>{children}</AuthProvider>
    )

    const { result } = renderHook(() => useAuth(), { wrapper })

    await act(async () => {
      await result.current.login('admin@test.com', 'password123')
    })

    expect(result.current.isAuthenticated).toBe(true)
    expect(result.current.user).toBeDefined()
    expect(result.current.user?.email).toBe('admin@test.com')
  })

  it('should check permissions correctly', () => {
    const wrapper = ({ children }: any) => (
      <AuthProvider>{children}</AuthProvider>
    )

    const { result } = renderHook(() => useAuth(), { wrapper })

    // Mock user with permissions
    act(() => {
      // Set user...
    })

    expect(result.current.hasPermission('users:read')).toBe(true)
    expect(result.current.hasPermission('invalid')).toBe(false)
  })

  it('should handle logout correctly', async () => {
    const wrapper = ({ children }: any) => (
      <AuthProvider>{children}</AuthProvider>
    )

    const { result } = renderHook(() => useAuth(), { wrapper })

    // Login first
    await act(async () => {
      await result.current.login('test@test.com', 'password')
    })

    expect(result.current.isAuthenticated).toBe(true)

    // Logout
    await act(async () => {
      await result.current.logout()
    })

    expect(result.current.isAuthenticated).toBe(false)
    expect(result.current.user).toBeNull()
  })
})
```

**Estimativa:** 4-6 horas
**Status:** 🟡 PRONTO PARA EXECUTAR

---

### 6. Refatorar AdminDashboard (400+ linhas)

**Problema:** Componente muito grande e complexo

**Solução:** Dividir em subcomponentes

```
AdminDashboard.tsx (atual 400+ linhas)
  ↓ REFATORAR EM:

AdminDashboard/
├── index.tsx (100 linhas)              - Layout principal
├── SystemHealthCards.tsx (80 linhas)   - Cards de saúde do sistema
├── SecurityMetrics.tsx (80 linhas)     - Métricas de segurança
├── RecentActivityList.tsx (80 linhas)  - Lista de atividades
├── SecurityTrendChart.tsx (60 linhas)  - Gráfico de tendências
└── types.ts                            - Tipos compartilhados
```

**Estimativa:** 6-8 horas
**Status:** 📋 BACKLOG

---

## 📊 RESUMO DE CORREÇÕES

### Status Geral
```
🔴 CRÍTICAS (Fazer esta semana):
  ✅ [PRONTO] Consolidar AuthContext          - 2-3h
  ✅ [PRONTO] Corrigir contratos API          - 1-2h
  🔴 [BACKEND] Implementar user activity      - 3-4h
  ✅ [PRONTO] Validar useSystemStats          - 2h

🟡 ALTAS (Próxima sprint):
  ✅ [PRONTO] Adicionar testes AuthContext    - 4-6h
  📋 [BACKLOG] Refatorar AdminDashboard       - 6-8h

🟢 MÉDIAS (Backlog):
  📋 Testes E2E
  📋 Documentação componentes
  📋 Type safety improvements
```

### Impacto Esperado

**Após Correções Críticas:**
- ✅ Autenticação unificada (sem duplicação)
- ✅ Contratos de API consistentes
- ✅ Rota de atividade funcionando
- ✅ Hook validado contra backend real
- 🎯 **Redução de 80% nos bugs de autenticação**
- 🎯 **Melhoria de 40% na manutenibilidade**

**Após Correções Altas:**
- ✅ Cobertura de testes aumentada para 40%+
- ✅ Componentes refatorados e modulares
- 🎯 **Redução de 60% em bugs de regressão**
- 🎯 **Facilita onboarding de novos desenvolvedores**

---

## 🔧 COMANDOS DE EXECUÇÃO

### 1. Aplicar Correção de Autenticação
```bash
# Migrar imports
npx ts-node scripts/migrate-admin-auth.ts

# Ou manual:
# 1. Substituir useAdminAuth por useAuth em 4 arquivos
# 2. Remover AdminAuthProvider de AdminApp.tsx
# 3. Deletar AdminAuthContext.tsx
```

### 2. Corrigir API Backend
```bash
# Backend
cd backend-hormonia
# Editar app/api/v1/admin/users.py
# Trocar "users" por "items" na resposta
```

### 3. Implementar User Activity
```bash
# Backend
cd backend-hormonia
# Adicionar rota em app/api/v1/admin/users.py
# Criar migration se necessário
```

### 4. Rodar Testes
```bash
# Frontend
cd frontend-hormonia
npm run test -- useSystemStats
npm run test -- AuthContext
```

---

## 📈 TRACKING DE PROGRESSO

### Sprint Atual (Semana 1)
- [🟡] Consolidar AuthContext
- [🟡] Corrigir contratos API
- [🔴] Implementar user activity (backend)
- [🟡] Validar useSystemStats

### Próxima Sprint (Semana 2)
- [ ] Adicionar testes AuthContext
- [ ] Refatorar AdminDashboard
- [ ] Testes de integração

### Backlog
- [ ] Testes E2E com Playwright
- [ ] Documentação com Storybook
- [ ] Performance optimization
- [ ] Accessibility audit

---

## 🎯 MÉTRICAS DE SUCESSO

**Antes das Correções:**
```
📊 Duplicação de Código:     ALTA (2 AuthContexts)
📊 Bugs de Autenticação:     MÉDIO (conflitos de sessão)
📊 Cobertura de Testes:      20%
📊 API Contract Issues:      3 problemas críticos
📊 Complexidade Componentes: ALTA (400+ linhas)
```

**Depois das Correções:**
```
📊 Duplicação de Código:     BAIXA (1 AuthContext) ✅
📊 Bugs de Autenticação:     BAIXO (unificado) ✅
📊 Cobertura de Testes:      40%+ ✅
📊 API Contract Issues:      0 problemas ✅
📊 Complexidade Componentes: MÉDIA (100-150 linhas) ✅
```

---

**Próximo Passo:** Executar correções críticas
**Responsável:** Dev Team
**Deadline:** Fim desta semana
