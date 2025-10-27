# 🔄 ANÁLISE DE ALINHAMENTO: FRONTEND ↔ BACKEND
## Sistema de Deleção de Pacientes

**Data:** 27 de Outubro de 2025  
**Escopo:** Verificação de alinhamento entre frontend e backend para soft delete

---

## 📊 STATUS ATUAL

### ✅ **BACKEND - IMPLEMENTADO**
- ✅ Soft delete implementado no modelo Patient
- ✅ Coluna `deleted_at` adicionada ao banco
- ✅ Serviço PatientService com soft delete
- ✅ Repositório PatientRepository com filtros
- ✅ Endpoint DELETE `/api/v1/patients/{id}` (soft delete)
- ✅ Endpoint POST `/api/v1/patients/{id}/restore` (restauração)
- ✅ Índices de performance criados

### ⚠️ **FRONTEND - PARCIALMENTE ALINHADO**
- ✅ Cliente API tem método `deletePatient()`
- ✅ Cliente API tem método `restore()`
- ✅ Componente PatientsTable chama deleção
- ❌ **PROBLEMA:** Frontend usa `/api/v2/patients` mas backend implementou `/api/v1/patients`
- ❌ **AUSENTE:** Interface para listar pacientes deletados
- ❌ **AUSENTE:** Interface para restaurar pacientes
- ❌ **AUSENTE:** Feedback visual sobre soft delete

---

## 🚨 INCONSISTÊNCIAS IDENTIFICADAS

### 1. **Versão da API Divergente**
**Problema:** Frontend chama v2, backend implementou v1

**Frontend:**
```typescript
// frontend-hormonia/src/lib/api-client/patients.ts
delete: async (patientId: string): Promise<{ message: string }> => {
  return client.delete<{ message: string }>(`/api/v2/patients/${patientId}`)
},

deletePatient: async (patientId: string): Promise<{ message: string }> => {
  return client.delete<{ message: string }>(`/api/v2/patients/${patientId}`)
},
```

**Backend:**
```python
# backend-hormonia/app/api/v1/patients.py
@router.delete("/{patient_id}", status_code=204)
async def delete_patient(patient_id: UUID, ...):
    # Implementação do soft delete
```

### 2. **Método de Restauração Divergente**
**Frontend:**
```typescript
restore: async (patientId: string): Promise<Patient> => {
  return client.patch<Patient>(`/api/v1/patients/${patientId}/restore`)
},
```

**Backend:**
```python
# Implementado como POST, não PATCH
@router.post("/{patient_id}/restore", response_model=PatientResponse)
async def restore_patient(patient_id: UUID, ...):
```

### 3. **Interface de Gerenciamento Ausente**
- ❌ Não há página para listar pacientes deletados
- ❌ Não há botão de restauração na interface
- ❌ Usuário não sabe que deleção é "soft"

---

## 🔧 CORREÇÕES NECESSÁRIAS

### 🔴 **Prioridade Alta - Alinhamento de APIs**

#### 1. **Corrigir Versão da API no Frontend**
```typescript
// Opção A: Mudar frontend para usar v1
delete: async (patientId: string): Promise<{ message: string }> => {
  return client.delete<{ message: string }>(`/api/v1/patients/${patientId}`)
},

// Opção B: Implementar endpoint v2 no backend (recomendado)
```

#### 2. **Corrigir Método de Restauração**
```typescript
// Mudar de PATCH para POST
restore: async (patientId: string): Promise<Patient> => {
  return client.post<Patient>(`/api/v1/patients/${patientId}/restore`)
},
```

### 🟡 **Prioridade Média - Funcionalidades Ausentes**

#### 3. **Criar Interface de Pacientes Deletados**
- Página `/patients/deleted` para listar pacientes soft-deleted
- Botão "Restaurar" para cada paciente
- Filtros e busca em pacientes deletados

#### 4. **Melhorar Feedback Visual**
- Toast informando que deleção é reversível
- Ícone diferente para indicar soft delete
- Opção "Desfazer" imediata após deleção

### 🟢 **Prioridade Baixa - Melhorias UX**

#### 5. **Dashboard de Pacientes Deletados**
- Estatísticas de pacientes deletados
- Gráficos de tendências
- Alertas para pacientes deletados há muito tempo

---

## 🛠️ IMPLEMENTAÇÃO DAS CORREÇÕES

### Correção 1: Alinhamento de API

**Opção A - Atualizar Frontend (Rápido):**
```typescript
// frontend-hormonia/src/lib/api-client/patients.ts
delete: async (patientId: string): Promise<void> => {
  return client.delete<void>(`/api/v1/patients/${patientId}`)
},

restore: async (patientId: string): Promise<Patient> => {
  return client.post<Patient>(`/api/v1/patients/${patientId}/restore`)
},
```

**Opção B - Implementar v2 no Backend (Recomendado):**
```python
# backend-hormonia/app/api/v2/patients.py
@router.delete("/{patient_id}", status_code=204)
async def delete_patient_v2(patient_id: UUID, ...):
    # Mesma implementação de v1
    
@router.post("/{patient_id}/restore", response_model=PatientResponse)
async def restore_patient_v2(patient_id: UUID, ...):
    # Mesma implementação de v1
```

### Correção 2: Interface de Pacientes Deletados

**Novo Componente:**
```typescript
// frontend-hormonia/src/components/patients/DeletedPatientsTable.tsx
export function DeletedPatientsTable() {
  const { data: deletedPatients } = useQuery({
    queryKey: ['patients', 'deleted'],
    queryFn: () => apiClient.patients.listDeleted()
  })

  const restoreMutation = useMutation({
    mutationFn: (id: string) => apiClient.patients.restore(id),
    onSuccess: () => {
      toast({ title: 'Paciente restaurado com sucesso' })
      queryClient.invalidateQueries(['patients'])
    }
  })

  return (
    // Interface para listar e restaurar pacientes
  )
}
```

**Nova Página:**
```typescript
// frontend-hormonia/src/pages/DeletedPatientsPage.tsx
export function DeletedPatientsPage() {
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">Pacientes Excluídos</h1>
        <Badge variant="secondary">
          {deletedCount} pacientes
        </Badge>
      </div>
      
      <DeletedPatientsTable />
    </div>
  )
}
```

### Correção 3: Melhorar Feedback de Deleção

**Atualizar PatientsTable:**
```typescript
const handleDelete = (e: React.MouseEvent, patientId: string, patientName: string) => {
  e.stopPropagation()
  if (confirmDeleteId === patientId) {
    setConfirmDeleteId(null)
    deleteMutation.mutate(patientId, {
      onSuccess: () => {
        toast({
          title: 'Paciente excluído',
          description: `${patientName} foi movido para a lixeira. Você pode restaurá-lo a qualquer momento.`,
          action: (
            <ToastAction 
              altText="Desfazer"
              onClick={() => restoreMutation.mutate(patientId)}
            >
              Desfazer
            </ToastAction>
          )
        })
      }
    })
    return
  }
  // ... resto da lógica
}
```

---

## 📋 PLANO DE IMPLEMENTAÇÃO

### **Fase 1: Alinhamento Crítico (Esta Sprint)**
1. ✅ Implementar endpoint DELETE em `/api/v2/patients/{id}`
2. ✅ Implementar endpoint POST em `/api/v2/patients/{id}/restore`
3. ✅ Testar endpoints com frontend atual
4. ✅ Corrigir método de restauração (PATCH → POST)

### **Fase 2: Interface de Gerenciamento (Próxima Sprint)**
1. 🔄 Criar `DeletedPatientsTable` component
2. 🔄 Criar `DeletedPatientsPage` page
3. 🔄 Adicionar rota `/patients/deleted`
4. 🔄 Implementar endpoint `GET /api/v2/patients/deleted`

### **Fase 3: Melhorias UX (Roadmap)**
1. 🔄 Toast com ação "Desfazer"
2. 🔄 Ícones visuais para soft delete
3. 🔄 Dashboard de estatísticas
4. 🔄 Filtros avançados

---

## 🧪 TESTES NECESSÁRIOS

### **Testes de API**
```bash
# Testar deleção
curl -X DELETE http://localhost:8000/api/v2/patients/{id}

# Testar restauração
curl -X POST http://localhost:8000/api/v2/patients/{id}/restore

# Listar pacientes deletados
curl -X GET http://localhost:8000/api/v2/patients/deleted
```

### **Testes de Frontend**
```typescript
// Testar deleção
await apiClient.patients.delete(patientId)

// Testar restauração
await apiClient.patients.restore(patientId)

// Testar listagem de deletados
await apiClient.patients.listDeleted()
```

---

## 📊 MÉTRICAS DE SUCESSO

### **Antes das Correções**
- ❌ Frontend e backend desalinhados
- ❌ Usuário não sabe que deleção é reversível
- ❌ Sem interface para gerenciar pacientes deletados
- ❌ Sem feedback adequado sobre soft delete

### **Depois das Correções**
- ✅ APIs v1 e v2 funcionais
- ✅ Frontend e backend sincronizados
- ✅ Interface completa para gerenciar deletados
- ✅ UX clara sobre soft delete
- ✅ Funcionalidade de "Desfazer" imediata

---

## 🎯 RECOMENDAÇÃO FINAL

**Implementar Opção B (v2 no Backend)** porque:

1. **Compatibilidade:** Mantém frontend funcionando
2. **Versionamento:** Segue padrões de API
3. **Flexibilidade:** Permite evoluções futuras
4. **Menos Impacto:** Não quebra código existente

**Próximo passo:** Implementar endpoints v2 no backend e criar interface de gerenciamento no frontend.

---

**Status:** ⚠️ **PARCIALMENTE ALINHADO - CORREÇÕES NECESSÁRIAS**  
**Prioridade:** 🔴 **ALTA - Funcionalidade crítica para usuários**