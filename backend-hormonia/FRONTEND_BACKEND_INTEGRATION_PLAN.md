# 🔗 Plano de Integração Frontend-Backend

## 📊 Status Atual

### ✅ **Funcionando**
- **DashboardPage** → `/api/v1/analytics/dashboard`
- **Templates CRUD Backend** → `/api/v1/templates/*` endpoints registrados
- **Quiz APIs** → `/api/v1/quiz/*` e `/api/v1/monthly-quiz/*`
- **Flows Execution** → `/api/v1/flows/*`
- **Reports** → `/api/v1/reports/*` (307 redirect resolvido)

### ⚠️ **Gaps Críticos**

#### 1. **Hooks useTemplates - Divergência de Endpoints**
**Problema**: 
```typescript
// Frontend hooks (useTemplates.ts)
POST /templates/flows     // ❌ Não existe
GET  /templates/flows     // ❌ Não existe
PUT  /templates/flows/:id // ❌ Não existe

// Backend disponível
POST /api/v1/templates/flows     // ✅ Existe
GET  /api/v1/templates/flows     // ✅ Existe  
PUT  /api/v1/templates/flows/:id // ✅ Existe
```

**Correção Necessária**:
```typescript
// Em frontend-hormonia/src/hooks/useTemplates.ts
// Trocar base URLs:
const FLOWS_BASE = '/api/v1/templates/flows'    // Era: '/templates/flows'
const QUIZ_BASE = '/api/v1/templates/quiz'      // Era: '/templates/quiz'
```

#### 2. **Rota Admin para Templates**
**Problema**: `TemplateManagementPage` não está acessível via admin

**Correção Necessária**:
```typescript
// Em frontend-hormonia/src/routes/AdminRoutes.tsx
// Adicionar rota:
{
  path: "templates",
  element: <TemplateManagementPage />,
  // Requer permissões admin
}
```

#### 3. **Base URL Configuration**
**Verificar**: Se `apiClient` está usando base URL correta em produção

## 🛠️ Implementação das Correções

### Prioridade 1: Corrigir Hooks useTemplates

**Arquivo**: `frontend-hormonia/src/hooks/useTemplates.ts`

**Mudanças**:
```typescript
// Antes
const FLOWS_BASE = '/templates/flows'
const QUIZ_BASE = '/templates/quiz'

// Depois  
const FLOWS_BASE = '/api/v1/templates/flows'
const QUIZ_BASE = '/api/v1/templates/quiz'
```

### Prioridade 2: Adicionar Rota Admin

**Arquivo**: `frontend-hormonia/src/routes/AdminRoutes.tsx`

**Adicionar**:
```typescript
import { TemplateManagementPage } from '@/pages/TemplateManagementPage'

// Na lista de rotas:
{
  path: "templates",
  element: <TemplateManagementPage />,
  handle: {
    crumb: () => "Template Management",
    permissions: ["admin.templates.read"]
  }
}
```

### Prioridade 3: Verificar Base URL

**Arquivo**: `frontend-hormonia/src/lib/api-client.ts`

**Verificar**:
```typescript
// Garantir que baseURL está correto
const baseURL = process.env.REACT_APP_API_URL || 'http://localhost:8000'
```

## 🧪 Testes de Validação

### Teste 1: Templates Hooks
```bash
# Após correção dos hooks
# Testar se TemplateManagementPage consegue:
1. Listar templates de flows ✅
2. Criar novo template de flow ✅  
3. Editar template existente ✅
4. Deletar template ✅
5. Mesmo para quiz templates ✅
```

### Teste 2: Rota Admin
```bash
# Após adicionar rota
# Verificar se:
1. /admin/templates é acessível ✅
2. Página carrega corretamente ✅
3. Permissões funcionam ✅
4. Menu admin mostra link ✅
```

### Teste 3: Integração Completa
```bash
# Fluxo end-to-end:
1. Login como admin ✅
2. Navegar para /admin/templates ✅
3. Criar template de flow ✅
4. Salvar no backend ✅
5. Recarregar página ✅
6. Template aparece na lista ✅
```

## 📋 Checklist de Implementação

### Backend (✅ Completo)
- [x] Endpoints `/api/v1/templates/*` registrados
- [x] Authentication/authorization funcionando
- [x] CRUD completo para flows e quiz
- [x] Trailing slash redirects resolvidos
- [x] Performance otimizada

### Frontend (🔄 Em Progresso)
- [ ] Corrigir base URLs em `useTemplates.ts`
- [ ] Adicionar rota `/admin/templates`
- [ ] Verificar base URL do `apiClient`
- [ ] Testar integração completa
- [ ] Adicionar link no menu admin

### Testes (📋 Pendente)
- [ ] Teste de criação de template
- [ ] Teste de edição de template
- [ ] Teste de listagem
- [ ] Teste de permissões
- [ ] Teste de navegação admin

## 🎯 Resultado Esperado

Após implementação:

### ✅ **Funcionalidades Habilitadas**
1. **Gestão Visual de Templates**: Admins podem criar/editar flows via UI
2. **CRUD Completo**: Todas operações funcionando via interface
3. **Integração Seamless**: React ↔ FastAPI sem problemas
4. **Acesso Admin**: Templates acessíveis via `/admin/templates`
5. **Persistência**: Dados salvos corretamente no banco

### 📊 **Métricas de Sucesso**
- ✅ Zero erros 404 nos hooks useTemplates
- ✅ TemplateManagementPage totalmente funcional
- ✅ Admins conseguem gerenciar templates via UI
- ✅ Dados persistem entre sessões
- ✅ Performance adequada (<2s para operações CRUD)

## 🚀 Próximos Passos

1. **Implementar correções no frontend** (useTemplates + AdminRoutes)
2. **Testar integração completa**
3. **Documentar para equipe**
4. **Deploy coordenado frontend + backend**

---

**Status**: 🔄 **Backend Pronto, Frontend Precisa de Ajustes**
**ETA**: ~2-4 horas de desenvolvimento frontend
**Risco**: Baixo (mudanças simples e bem definidas)