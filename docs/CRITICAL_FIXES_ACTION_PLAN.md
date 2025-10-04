# 🚨 Plano de Ação - Correções Críticas
**Prioridade:** ALTA
**Prazo:** 1-2 dias
**Status:** READY TO IMPLEMENT

---

## 🎯 Fix #1: Deploy Quiz Interface no Railway

### Status: ⛔ BLOCKER CRÍTICO
**Impacto:** Pacientes não conseguem acessar quizzes mensais
**Estimativa:** 4 horas
**Responsável:** DevOps + Backend

### Passos de Implementação:

#### 1. Criar Serviço no Railway

```bash
cd quiz-mensal-interface

# Inicializar Railway no diretório do Quiz
railway link

# Criar novo serviço
railway up --service quiz-interface

# Ou via Railway Dashboard:
# 1. New Project > Deploy from GitHub repo
# 2. Select repository
# 3. Root directory: quiz-mensal-interface/
```

#### 2. Configurar Variáveis de Ambiente

```bash
# Via CLI
railway variables set NEXT_PUBLIC_API_URL=https://clinica-oncologica-v02-production.up.railway.app
railway variables set NODE_ENV=production
railway variables set PORT=3000

# Ou adicionar no Railway Dashboard > Variables:
```

**Variáveis necessárias:**
```env
NEXT_PUBLIC_API_URL=https://clinica-oncologica-v02-production.up.railway.app
NODE_ENV=production
PORT=3000
```

#### 3. Configurar Build Settings

**Railway Dashboard > Settings:**
- **Build Command:** `npm run build`
- **Start Command:** `npm start`
- **Root Directory:** `quiz-mensal-interface/`

#### 4. Atualizar Backend .env

Após deploy, pegar URL gerada pelo Railway (ex: `https://quiz-interface-production-xyz.up.railway.app`)

```bash
# Editar backend-hormonia/.env linha 158
MONTHLY_QUIZ_BASE_URL="https://quiz-interface-production-xyz.up.railway.app/quiz/monthly"
```

#### 5. Testar Fluxo Completo

```bash
# 1. Gerar link de quiz via backend
curl -X POST https://clinica-oncologica-v02-production.up.railway.app/api/v1/monthly-quiz-links \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_id": "uuid-here",
    "quiz_month": "2025-10",
    "expiry_hours": 72
  }'

# 2. Copiar quiz_link retornado
# 3. Abrir no browser
# 4. Verificar se carrega o quiz corretamente
```

### Checklist de Validação:
- [ ] Serviço Railway criado e rodando
- [ ] Env vars configuradas
- [ ] Build bem-sucedido
- [ ] URL acessível via browser
- [ ] Backend consegue gerar links
- [ ] Paciente consegue acessar quiz via link
- [ ] Quiz carrega dados do backend corretamente
- [ ] Submissão de respostas funciona
- [ ] Completamento do quiz atualiza backend

---

## 🎯 Fix #2: Corrigir WebSocket Fallback URL

### Status: 🔴 HIGH PRIORITY BUG
**Impacto:** Conexão WebSocket falha em ambientes sem env vars
**Estimativa:** 1 hora
**Responsável:** Frontend

### Problema:
```typescript
// ❌ ERRADO - Falta /connect no final
VITE_WS_BASE_URL: 'wss://backend-production-e0bd.up.railway.app/ws'
```

Backend espera conexões em `/ws/connect` (veja [backend-hormonia/app/main.py:253](backend-hormonia/app/main.py#L253))

### Solução:

#### 1. Editar Arquivo de Runtime Config

**Arquivo:** `frontend-hormonia/src/lib/runtime-config.ts`

**Linha 63 - ANTES:**
```typescript
VITE_WS_BASE_URL: 'wss://backend-production-e0bd.up.railway.app/ws'
```

**Linha 63 - DEPOIS:**
```typescript
VITE_WS_BASE_URL: 'wss://clinica-oncologica-v02-production.up.railway.app/ws/connect'
```

#### 2. Adicionar Validação de Endpoint

**Arquivo:** `frontend-hormonia/src/lib/websocket.ts`

Adicionar após linha 100:

```typescript
private validateWebSocketUrl(url: string): void {
  if (!url.endsWith('/ws/connect')) {
    console.warn(
      `[WebSocket] URL should end with /ws/connect. Got: ${url}. ` +
      `Connection might fail. Appending /connect...`
    )
  }

  // Auto-fix common mistakes
  if (url.endsWith('/ws') && !url.endsWith('/ws/connect')) {
    this.wsUrl = `${url}/connect`
    console.info(`[WebSocket] Auto-corrected URL to: ${this.wsUrl}`)
  }
}

// Chamar no construtor:
constructor() {
  const config = getRuntimeConfig()
  this.wsUrl = config.VITE_WS_BASE_URL
  this.validateWebSocketUrl(this.wsUrl)  // ← Adicionar esta linha
  // ... resto do código
}
```

#### 3. Testar em Ambiente Sem Env Vars

```bash
# Simular ambiente sem VITE_WS_BASE_URL
cd frontend-hormonia

# Remover env var temporariamente
mv .env .env.backup

# Build e test
npm run build
npm run preview

# Abrir DevTools Console
# Verificar se WebSocket conecta corretamente
# URL deve ser: wss://clinica-oncologica-v02-production.up.railway.app/ws/connect

# Restaurar .env
mv .env.backup .env
```

### Checklist de Validação:
- [ ] URL fallback corrigida em runtime-config.ts
- [ ] Validação adicionada no WebSocketManager
- [ ] Build sem warnings
- [ ] Conexão WebSocket bem-sucedida em prod
- [ ] Teste sem .env bem-sucedido
- [ ] DevTools Console sem erros 404 no WebSocket
- [ ] Auto-correção funciona para URLs com /ws

### Commit:
```bash
git add frontend-hormonia/src/lib/runtime-config.ts
git add frontend-hormonia/src/lib/websocket.ts
git commit -m "fix(websocket): corrigir fallback URL para incluir /connect endpoint

- Atualizar runtime-config.ts linha 63 com URL completa
- Adicionar validação e auto-correção no WebSocketManager
- Prevenir 404 em ambientes sem VITE_WS_BASE_URL

Resolves: WebSocket connection failures in fallback scenarios"
```

---

## 🎯 Fix #3: Alinhar Patient Schema (Frontend ↔ Backend)

### Status: 🔴 HIGH PRIORITY DEBT
**Impacto:** Bugs de runtime, dados perdidos/corrompidos
**Estimativa:** 6 horas
**Responsável:** Frontend + Backend

### Problemas Identificados:

#### Naming Mismatch (camelCase vs snake_case):
- `dateOfBirth` → `birth_date`
- `firstName` → `first_name` (se existir)
- `phoneNumber` → `phone_number` (se existir)

#### Ghost Fields (existem no frontend, não no backend):
- `lastVisit: string | undefined`
- `nextAppointment: string | undefined`

#### Missing Fields (existem no backend, não no frontend):
- `flow_state: FlowState`
- `doctor_id: UUID`
- `treatment_start_date: date`
- `cpf: string` (LGPD critical!)

### Solução:

#### 1. Criar Transformation Layer

**Criar arquivo:** `frontend-hormonia/src/lib/transformers/patient.transformer.ts`

```typescript
import type { Patient } from '@/types'
import type { PatientResponse } from '@/types/api' // Será gerado

/**
 * Transforma dados de paciente do backend (snake_case) para frontend (camelCase)
 */
export function fromBackendPatient(backendPatient: PatientResponse): Patient {
  return {
    id: backendPatient.id,
    name: backendPatient.name,
    email: backendPatient.email,
    phone: backendPatient.phone,

    // Transformações de naming
    dateOfBirth: backendPatient.birth_date || '',

    // Campos adicionais do backend
    flowState: backendPatient.flow_state,
    doctorId: backendPatient.doctor_id,
    treatmentStartDate: backendPatient.treatment_start_date || undefined,
    cpf: backendPatient.cpf || undefined,

    // Status e timestamps
    status: backendPatient.status,
    createdAt: backendPatient.created_at,
    updatedAt: backendPatient.updated_at,

    // Ghost fields - REMOVER ou calcular dinamicamente
    // lastVisit e nextAppointment devem vir de queries separadas
    // Não existem no modelo Patient do backend
  }
}

/**
 * Transforma dados de paciente do frontend (camelCase) para backend (snake_case)
 */
export function toBackendPatient(frontendPatient: Partial<Patient>): Partial<PatientResponse> {
  return {
    id: frontendPatient.id,
    name: frontendPatient.name,
    email: frontendPatient.email,
    phone: frontendPatient.phone,

    // Transformações de naming
    birth_date: frontendPatient.dateOfBirth,

    // Campos adicionais
    flow_state: frontendPatient.flowState,
    doctor_id: frontendPatient.doctorId,
    treatment_start_date: frontendPatient.treatmentStartDate,
    cpf: frontendPatient.cpf,

    // Status
    status: frontendPatient.status,

    // Remover ghost fields - não existem no backend
    // lastVisit, nextAppointment não devem ser enviados
  }
}

/**
 * Valida estrutura de paciente antes de enviar ao backend
 */
export function validatePatientData(patient: Partial<Patient>): {
  valid: boolean
  errors: string[]
} {
  const errors: string[] = []

  if (!patient.name || patient.name.trim().length === 0) {
    errors.push('Nome é obrigatório')
  }

  if (!patient.email || !patient.email.includes('@')) {
    errors.push('Email inválido')
  }

  if (patient.dateOfBirth && !isValidDate(patient.dateOfBirth)) {
    errors.push('Data de nascimento inválida')
  }

  // Validação CPF (LGPD - importante!)
  if (patient.cpf && !isValidCPF(patient.cpf)) {
    errors.push('CPF inválido')
  }

  return {
    valid: errors.length === 0,
    errors
  }
}

// Helper functions
function isValidDate(dateString: string): boolean {
  const date = new Date(dateString)
  return date instanceof Date && !isNaN(date.getTime())
}

function isValidCPF(cpf: string): boolean {
  // Implementar validação de CPF
  const cleanCPF = cpf.replace(/\D/g, '')
  return cleanCPF.length === 11 // Simplificado, adicionar validação real
}
```

#### 2. Atualizar Interface Patient

**Arquivo:** `frontend-hormonia/src/types/index.ts`

**ANTES:**
```typescript
interface Patient {
  id: string
  name: string
  dateOfBirth: string
  status: 'active' | 'inactive' | 'completed' | 'paused' | 'cancelled'
  lastVisit?: string          // ❌ Ghost field
  nextAppointment?: string    // ❌ Ghost field
}
```

**DEPOIS:**
```typescript
interface Patient {
  id: string
  name: string
  email: string
  phone?: string

  // Naming alinhado com backend (mantém camelCase no frontend)
  dateOfBirth: string  // backend: birth_date

  // Campos do backend adicionados
  flowState: 'initial' | 'active' | 'completed' | 'paused' | 'cancelled'  // backend: flow_state
  doctorId: string  // backend: doctor_id
  treatmentStartDate?: string  // backend: treatment_start_date
  cpf?: string  // backend: cpf (LGPD!)

  // Status e metadata
  status: 'active' | 'inactive' | 'completed' | 'paused' | 'cancelled'
  createdAt: string
  updatedAt: string

  // ❌ REMOVER ghost fields ou buscar dinamicamente
  // lastVisit?: string - não existe no backend
  // nextAppointment?: string - não existe no backend
}

// Se lastVisit e nextAppointment são necessários, criar interface separada:
interface PatientWithAppointments extends Patient {
  lastVisit?: string  // Calculado de appointments table
  nextAppointment?: string  // Calculado de appointments table
}
```

#### 3. Atualizar API Client para Usar Transformers

**Arquivo:** `frontend-hormonia/src/lib/api-client.ts`

```typescript
import { fromBackendPatient, toBackendPatient } from './transformers/patient.transformer'

export class ApiClient {
  // ... código existente

  patients = {
    async getAll(params?: PaginationParams): Promise<PaginatedResponse<Patient>> {
      const response = await this.get<PaginatedResponse<PatientResponse>>(
        '/patients',
        params
      )

      // ✅ Transformar todos pacientes de backend para frontend
      return {
        ...response,
        data: response.data.map(fromBackendPatient)
      }
    },

    async getById(id: string): Promise<Patient> {
      const response = await this.get<PatientResponse>(`/patients/${id}`)

      // ✅ Transformar paciente individual
      return fromBackendPatient(response)
    },

    async create(patient: Partial<Patient>): Promise<Patient> {
      // ✅ Transformar de frontend para backend antes de enviar
      const backendPatient = toBackendPatient(patient)

      const response = await this.post<PatientResponse>('/patients', backendPatient)

      // ✅ Transformar resposta de volta para frontend
      return fromBackendPatient(response)
    },

    async update(id: string, patient: Partial<Patient>): Promise<Patient> {
      // ✅ Transformar de frontend para backend
      const backendPatient = toBackendPatient(patient)

      const response = await this.put<PatientResponse>(
        `/patients/${id}`,
        backendPatient
      )

      // ✅ Transformar resposta de volta
      return fromBackendPatient(response)
    },

    // ... outros métodos
  }
}
```

#### 4. Criar Testes Unitários

**Criar arquivo:** `frontend-hormonia/src/lib/transformers/__tests__/patient.transformer.test.ts`

```typescript
import { describe, it, expect } from 'vitest'
import { fromBackendPatient, toBackendPatient, validatePatientData } from '../patient.transformer'

describe('Patient Transformer', () => {
  describe('fromBackendPatient', () => {
    it('deve transformar snake_case para camelCase', () => {
      const backendPatient = {
        id: '123',
        name: 'João Silva',
        email: 'joao@example.com',
        birth_date: '1990-01-01',
        flow_state: 'active',
        doctor_id: 'doc-456',
        treatment_start_date: '2025-01-01',
        cpf: '12345678900',
        status: 'active',
        created_at: '2025-01-01T00:00:00Z',
        updated_at: '2025-01-01T00:00:00Z'
      }

      const frontendPatient = fromBackendPatient(backendPatient)

      expect(frontendPatient.dateOfBirth).toBe('1990-01-01')
      expect(frontendPatient.flowState).toBe('active')
      expect(frontendPatient.doctorId).toBe('doc-456')
      expect(frontendPatient.cpf).toBe('12345678900')
    })
  })

  describe('toBackendPatient', () => {
    it('deve transformar camelCase para snake_case', () => {
      const frontendPatient = {
        id: '123',
        name: 'João Silva',
        dateOfBirth: '1990-01-01',
        doctorId: 'doc-456',
        cpf: '12345678900'
      }

      const backendPatient = toBackendPatient(frontendPatient)

      expect(backendPatient.birth_date).toBe('1990-01-01')
      expect(backendPatient.doctor_id).toBe('doc-456')
      expect(backendPatient.cpf).toBe('12345678900')
    })
  })

  describe('validatePatientData', () => {
    it('deve validar dados obrigatórios', () => {
      const invalidPatient = {
        name: '',
        email: 'invalid-email'
      }

      const result = validatePatientData(invalidPatient)

      expect(result.valid).toBe(false)
      expect(result.errors).toContain('Nome é obrigatório')
      expect(result.errors).toContain('Email inválido')
    })
  })
})
```

#### 5. Atualizar Componentes React

**Exemplo:** `frontend-hormonia/src/components/patients/PatientForm.tsx`

```typescript
import { validatePatientData } from '@/lib/transformers/patient.transformer'

function PatientForm() {
  const handleSubmit = async (data: Partial<Patient>) => {
    // ✅ Validar antes de enviar
    const validation = validatePatientData(data)

    if (!validation.valid) {
      toast.error(validation.errors.join(', '))
      return
    }

    // ✅ API client já faz a transformação
    await apiClient.patients.create(data)
  }

  return (
    <form onSubmit={handleSubmit}>
      {/* Usar camelCase nos campos do form */}
      <input name="dateOfBirth" type="date" />
      <input name="cpf" type="text" />
      {/* ... */}
    </form>
  )
}
```

### Checklist de Validação:
- [ ] Transformer criado em `src/lib/transformers/patient.transformer.ts`
- [ ] Interface Patient atualizada com todos campos do backend
- [ ] Ghost fields removidos ou movidos para interface separada
- [ ] API client usa transformers em todos métodos
- [ ] Testes unitários criados e passando
- [ ] Componentes React atualizados
- [ ] Validação de CPF implementada (LGPD)
- [ ] Build sem erros TypeScript
- [ ] Testes E2E passando com dados reais

### Commit:
```bash
git add frontend-hormonia/src/lib/transformers/
git add frontend-hormonia/src/types/index.ts
git add frontend-hormonia/src/lib/api-client.ts
git commit -m "feat(types): alinhar schema Patient com backend

- Criar transformation layer para converter snake_case ↔ camelCase
- Adicionar campos faltantes: flowState, doctorId, cpf, treatmentStartDate
- Remover ghost fields: lastVisit, nextAppointment
- Implementar validação de CPF (LGPD compliance)
- Adicionar testes unitários para transformers

Breaking changes:
- Patient.dateOfBirth agora vem de birth_date do backend
- Ghost fields removidos, usar PatientWithAppointments se necessário

Resolves: Type mismatches between frontend and backend"
```

---

## 📋 Ordem de Execução Recomendada

### Dia 1:
1. **Manhã:** Fix #2 (WebSocket URL) - 1h ✅ Quick win
2. **Tarde:** Fix #1 (Deploy Quiz Interface) - 4h 🎯 Maior impacto

### Dia 2:
3. **Dia todo:** Fix #3 (Alinhar Patient Schema) - 6h 🔧 Mais trabalhoso

### Validação Final:
- Testar fluxo completo: Login → Dashboard → Pacientes → Quiz
- Verificar WebSocket conecta sem erros
- Confirmar dados de pacientes corretos em frontend e backend
- Validar quiz mensal acessível via link

---

## 🆘 Troubleshooting

### Quiz Interface não builda:
```bash
# Verificar dependências
cd quiz-mensal-interface
npm install

# Verificar env vars
cat .env.local  # Deve ter NEXT_PUBLIC_API_URL

# Build local
npm run build

# Se erro de TypeScript, rodar:
npm run typecheck
```

### WebSocket não conecta:
```bash
# Testar URL manualmente
wscat -c wss://clinica-oncologica-v02-production.up.railway.app/ws/connect

# Verificar backend logs
railway logs --service backend-web | grep -i websocket

# Verificar CORS
curl -I https://clinica-oncologica-v02-production.up.railway.app/ws/connect
```

### Type errors no build:
```bash
cd frontend-hormonia

# Rodar typecheck
npm run typecheck

# Se erros em transformers:
npx tsc --noEmit --project tsconfig.json

# Verificar imports
npx eslint src/lib/transformers/ --fix
```

---

**Última atualização:** 2025-10-04
**Próxima revisão:** Após implementação dos 3 fixes
