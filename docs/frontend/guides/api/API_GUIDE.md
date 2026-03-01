# Guia Completo do API Client Frontend

**Versao**: 2.1.0
**Framework**: React 19 + TypeScript + Vite
**Ultima Atualizacao**: Janeiro 2025

---

## Sumario

1. [Visao Geral](#visao-geral)
2. [Arquitetura do API Client](#arquitetura-do-api-client)
3. [Padroes de Integracao](#padroes-de-integracao)
4. [Tratamento de Erros](#tratamento-de-erros)
5. [Boas Praticas](#boas-praticas)
6. [Exemplos de Codigo](#exemplos-de-codigo)

---

## Visao Geral

O API Client e uma biblioteca HTTP type-safe que fornece acesso a todos os endpoints do backend. Recursos principais:

- **Autenticacao**: Firebase + Session cookies
- **Protecao CSRF**: Gerenciamento automatico de tokens
- **Tratamento de Erros**: Mensagens amigaveis em portugues
- **Retry Logic**: Retry automatico com backoff exponencial
- **Type Safety**: Interfaces TypeScript completas
- **Paginacao**: Suporte a cursor-based pagination (V2)

### Quick Start

```typescript
import { apiClient } from '@/lib/api-client'

// Listar pacientes
const patients = await apiClient.patients.list({ status: 'active' })

// Buscar paciente
const patient = await apiClient.patients.get('patient-id')

// Criar paciente
const newPatient = await apiClient.patients.create({
  name: 'Joao Silva',
  phone: '+5511999999999',
  doctor_id: 'doctor-id'
})
```

---

## Arquitetura do API Client

### Estrutura Modular

```
src/lib/api-client/
├── index.ts          # Orquestrador principal (~417 linhas)
├── core.ts           # Cliente HTTP base (~446 linhas)
├── auth.ts           # Autenticacao (~197 linhas)
├── patients.ts       # Gestao de pacientes (~375 linhas)
├── monthly-quiz.ts   # Quiz mensal (~453 linhas)
├── analytics.ts      # Analytics e metricas (~364 linhas)
└── types.ts          # Definicoes de tipos
```

### Core HTTP Client

O `ApiClientCore` e a base de toda comunicacao HTTP:

```typescript
export class ApiClientCore {
  // Metodos HTTP
  async get<T>(endpoint: string, params?): Promise<T>
  async post<T>(endpoint: string, data?, params?): Promise<T>
  async put<T>(endpoint: string, data?, params?): Promise<T>
  async delete<T>(endpoint: string, params?): Promise<T>
  async patch<T>(endpoint: string, data?, params?): Promise<T>

  // Configuracao
  setBaseURL(url: string): void
  setAuthToken(token: string | null): void

  // CSRF
  async fetchCsrfToken(): Promise<void>
  getCsrfToken(): string | null
}
```

**Recursos do Core**:
- Retry automatico com backoff exponencial (max 3 tentativas)
- Timeout de 30s padrao
- Retry em: 0 (network), 408, 429, 500-599
- Sem retry em: 401, 403, 4xx (exceto 408, 429)
- Suporte a cookies (`credentials: 'include'`)

### Modulos Disponiveis

#### 1. Auth API

```typescript
// Gerenciamento de sessao
await apiClient.auth.createSession(firebaseToken)
await apiClient.auth.getSession()
await apiClient.auth.logout()
await apiClient.auth.invalidateAllSessions()

// Verificacao
const { authenticated, user } = await apiClient.auth.checkAuth()
```

#### 2. Patients API

```typescript
// CRUD
const patients = await apiClient.patients.list({ status: 'active', page: 1, size: 20 })
const patient = await apiClient.patients.get('patient-id')
const newPatient = await apiClient.patients.create(data)
await apiClient.patients.update('patient-id', { status: 'completed' })
await apiClient.patients.delete('patient-id')

// Busca e dados adicionais
const results = await apiClient.patients.search('Joao')
const timeline = await apiClient.patients.getTimeline('patient-id')
const stats = await apiClient.patients.getStatistics('patient-id')
```

#### 3. Appointments API

```typescript
// Agendamentos
const appointments = await apiClient.appointments.list({
  patient_id: 'patient-id',
  status: 'scheduled'
})

const appointment = await apiClient.appointments.create({
  patient_id: 'patient-id',
  practitioner_id: 'doctor-id',
  scheduled_at: '2025-02-01T10:00:00-03:00',
  duration_minutes: 60
})

// Verificar conflitos
const conflicts = await apiClient.appointments.checkConflicts(
  'doctor-id',
  '2025-02-01T10:00:00-03:00',
  60
)

// Status
await apiClient.appointments.cancel('appointment-id', 'Patient request')
await apiClient.appointments.complete('appointment-id')
```

#### 4. Treatments API

```typescript
// Tratamentos
const treatments = await apiClient.treatments.list({
  patient_id: 'patient-id',
  status: 'active',
  treatment_type: 'quimioterapia'
})

await apiClient.treatments.activate('treatment-id')
await apiClient.treatments.complete('treatment-id')
await apiClient.treatments.suspend('treatment-id', 'Side effects')

// Estatisticas
const stats = await apiClient.treatments.getStatistics({ treatment_type: 'quimioterapia' })
```

#### 5. Monthly Quiz API

```typescript
// Templates e sessoes
const templates = await apiClient.monthlyQuiz.getTemplates()
const session = await apiClient.monthlyQuiz.startSession('patient-id', 'template-id')

await apiClient.monthlyQuiz.submitAnswer('session-id', 'question-id', { answer: 'Sim' })

// Estatisticas
const stats = await apiClient.monthlyQuiz.getStats()
const analysis = await apiClient.monthlyQuiz.getSessionAnalysis('session-id')
```

#### 6. Analytics API

```typescript
const overview = await apiClient.analytics.getOverview({
  startDate: '2025-01-01',
  endDate: '2025-01-31'
})

const adherence = await apiClient.analytics.getAdherenceMetrics()
const risk = await apiClient.analytics.getRiskAssessment('patient-id')

// Export
const csvBlob = await apiClient.analytics.exportAnalytics('csv')
```

#### 7. Dashboard API

```typescript
const stats = await apiClient.dashboard.getStats()
const activity = await apiClient.dashboard.getRecentActivity()
const alerts = await apiClient.dashboard.getAlerts()
```

#### 8. Admin API

```typescript
// Usuarios
const users = await apiClient.admin.users.list({ role: 'doctor' })
await apiClient.admin.users.create({ email: 'doctor@example.com', role: 'doctor' })

// Sistema
const health = await apiClient.admin.system.getHealth()
const metrics = await apiClient.admin.system.getMetrics()

// Auditoria
const logs = await apiClient.admin.audit.list({ startDate: '2025-01-01' })
```

---

## Padroes de Integracao

### Autenticacao Firebase

```typescript
import { signInWithEmailAndPassword } from 'firebase/auth'

// 1. Login com Firebase
const userCredential = await signInWithEmailAndPassword(auth, email, password)

// 2. Obter token
const idToken = await userCredential.user.getIdToken()

// 3. Criar sessao no backend
const sessionResponse = await apiClient.auth.createSession(idToken)

// Cookie de sessao configurado automaticamente
```

### React Query Integration

#### Setup do QueryClient

```typescript
import { QueryClient } from '@tanstack/react-query'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,     // 5 minutos
      gcTime: 10 * 60 * 1000,       // 10 minutos
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
})
```

#### Custom Hooks

```typescript
// hooks/usePatients.ts
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'

export function usePatients(filters?: PatientFilters) {
  return useQuery({
    queryKey: ['patients', filters],
    queryFn: () => apiClient.patients.list(filters),
    staleTime: 5 * 60 * 1000,
  })
}

// Uso
const { data, isLoading, error } = usePatients({ status: 'active' })
```

#### Mutations

```typescript
import { useMutation, useQueryClient } from '@tanstack/react-query'

export function useCreatePatient() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: PatientCreate) => apiClient.patients.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patients'] })
      toast.success('Paciente criado com sucesso!')
    },
    onError: (error: ApiError) => {
      toast.error(error.userFriendlyMessage)
    },
  })
}
```

#### Optimistic Updates

```typescript
const updatePatient = useMutation({
  mutationFn: ({ id, data }) => apiClient.patients.update(id, data),
  onMutate: async ({ id, data }) => {
    await queryClient.cancelQueries({ queryKey: ['patient', id] })
    const previous = queryClient.getQueryData(['patient', id])

    queryClient.setQueryData(['patient', id], (old: Patient) => ({
      ...old,
      ...data,
    }))

    return { previous }
  },
  onError: (err, variables, context) => {
    queryClient.setQueryData(['patient', variables.id], context?.previous)
  },
  onSettled: (data, error, variables) => {
    queryClient.invalidateQueries({ queryKey: ['patient', variables.id] })
  },
})
```

### WebSocket Integration

```typescript
import { useWebSocket } from '@/hooks/useWebSocket'

const {
  isConnected,
  connectionState,
  lastMessage,
  sendMessage
} = useWebSocket({
  url: 'ws://localhost:8000/ws/connect',
  reconnectAttempts: 5,
  reconnectInterval: 3000,
  onMessage: (message) => {
    // Invalidar cache quando receber updates
    queryClient.invalidateQueries({ queryKey: ['patients'] })
  }
})
```

---

## Tratamento de Erros

### Classe ApiError

```typescript
class ApiError extends Error {
  status: number              // HTTP status code
  data: unknown               // Detalhes do erro do backend
  userFriendlyMessage: string // Mensagem traduzida para usuario
  retryable: boolean          // Pode ser retentado?
  timestamp: string           // Timestamp ISO
}
```

### Mensagens por Status

| Status | Retryable | Mensagem |
|--------|-----------|----------|
| 0 (Network) | Sim | "Nao foi possivel conectar ao servidor. Verifique sua conexao." |
| 400 | Nao | "Os dados enviados estao incorretos." |
| 401 | Nao | "Sua sessao expirou. Por favor, faca login novamente." |
| 403 | Nao | "Voce nao tem permissao para realizar esta acao." |
| 404 | Nao | "O recurso solicitado nao foi encontrado." |
| 408 | Sim | "Requisicao demorou muito." |
| 422 | Nao | "Dados nao puderam ser processados." |
| 429 | Sim | "Muitas tentativas. Aguarde alguns minutos." |
| 500 | Sim | "Erro interno do servidor. Nossa equipe foi notificada." |
| 502-504 | Sim | "Servidor temporariamente indisponivel." |

### Padrao de Tratamento

```typescript
try {
  const patient = await apiClient.patients.get('invalid-id')
} catch (error) {
  if (error instanceof ApiError) {
    // Mostrar mensagem amigavel
    toast.error(error.userFriendlyMessage)

    // Tratamento especifico por status
    switch (error.status) {
      case 401:
        navigate('/login')
        break
      case 403:
        toast.error('Acesso negado')
        break
      case 422:
        setFormErrors(error.data.detail)
        break
    }

    // Verificar se pode retentar
    if (error.retryable) {
      // Implementar logica de retry
    }
  }
}
```

### Error Boundary

```typescript
export class ErrorBoundary extends React.Component {
  state = { hasError: false, error: null }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    if (error instanceof ApiError) {
      toast.error(error.userFriendlyMessage)
    }
  }

  render() {
    if (this.state.hasError) {
      return <ErrorFallback error={this.state.error} />
    }
    return this.props.children
  }
}
```

---

## Boas Praticas

### 1. Use Custom Hooks

```typescript
// Evite
const Component = () => {
  const [patients, setPatients] = useState([])
  useEffect(() => {
    apiClient.patients.list().then(setPatients)
  }, [])
}

// Prefira
const Component = () => {
  const { data: patients, isLoading } = usePatients()
}
```

### 2. Centralize Query Keys

```typescript
// lib/query-keys.ts
export const queryKeys = {
  patients: {
    all: ['patients'] as const,
    lists: () => [...queryKeys.patients.all, 'list'] as const,
    list: (filters: PatientFilters) => [...queryKeys.patients.lists(), filters] as const,
    detail: (id: string) => [...queryKeys.patients.all, 'detail', id] as const,
  },
  quiz: {
    all: ['quiz'] as const,
    sessions: (patientId: string) => [...queryKeys.quiz.all, 'sessions', patientId] as const,
  },
}
```

### 3. Debounce em Buscas

```typescript
import { useDebounce } from '@/hooks/useDebounce'

const [search, setSearch] = useState('')
const debouncedSearch = useDebounce(search, 300)

const { data } = usePatients({ search: debouncedSearch })
```

### 4. Prefetch para Melhor UX

```typescript
const queryClient = useQueryClient()

const handleMouseEnter = (patientId: string) => {
  queryClient.prefetchQuery({
    queryKey: ['patient', patientId],
    queryFn: () => apiClient.patients.getById(patientId),
  })
}
```

### 5. Loading e Error States

```typescript
const { data, isLoading, isFetching, error } = usePatients()

if (isLoading) return <Spinner />
if (error) return <ErrorMessage error={error} />

return (
  <div>
    {isFetching && <RefreshIndicator />}
    <PatientList patients={data.items} />
  </div>
)
```

### 6. Tipagem Completa

```typescript
import type {
  Patient,
  PatientCreate,
  PatientUpdate,
  PaginatedResponse
} from '@/lib/api-client/types'

const handleCreatePatient = async (data: PatientCreate): Promise<Patient> => {
  return await apiClient.patients.create(data)
}
```

---

## Exemplos de Codigo

### Dashboard de Pacientes

```typescript
function PatientDashboard() {
  const [filters, setFilters] = useState<PatientFilters>({ status: 'active' })
  const { data, isLoading, error } = usePatients(filters)

  if (isLoading) return <Spinner />
  if (error) return <ErrorMessage error={error} />

  return (
    <div>
      <FilterBar filters={filters} onChange={setFilters} />
      <PatientList patients={data.items} />
      <Pagination
        total={data.total}
        page={data.page}
        hasMore={data.has_more}
      />
    </div>
  )
}
```

### Agendador de Consultas

```typescript
function AppointmentScheduler() {
  const createAppointment = async (data: AppointmentCreate) => {
    try {
      // Verificar conflitos primeiro
      const conflicts = await apiClient.appointments.checkConflicts(
        data.practitioner_id!,
        data.scheduled_at,
        data.duration_minutes || 60
      )

      if (conflicts.has_conflicts) {
        toast.warning('Conflito detectado com outro agendamento')
        return
      }

      const appointment = await apiClient.appointments.create(data)
      toast.success('Agendamento criado com sucesso!')
      return appointment
    } catch (error) {
      if (error instanceof ApiError) {
        toast.error(error.userFriendlyMessage)
      }
    }
  }

  return <AppointmentForm onSubmit={createAppointment} />
}
```

### Tracker de Tratamento

```typescript
function TreatmentTracker({ patientId }: { patientId: string }) {
  const { data: treatments, refetch } = useQuery({
    queryKey: ['treatments', patientId],
    queryFn: () => apiClient.treatments.getByPatient(patientId),
  })

  const completeMutation = useMutation({
    mutationFn: (treatmentId: string) => apiClient.treatments.complete(treatmentId),
    onSuccess: () => {
      toast.success('Tratamento concluido!')
      refetch()
    },
  })

  return (
    <TreatmentList
      treatments={treatments}
      onComplete={(id) => completeMutation.mutate(id)}
    />
  )
}
```

### Formulario com Validacao

```typescript
function PatientForm() {
  const [formData, setFormData] = useState<PatientCreate>({})
  const [errors, setErrors] = useState<Record<string, string>>({})

  const createMutation = useMutation({
    mutationFn: (data: PatientCreate) => apiClient.patients.create(data),
    onSuccess: (patient) => {
      toast.success('Paciente criado!')
      navigate(`/patients/${patient.id}`)
    },
    onError: (error: ApiError) => {
      if (error.status === 422 && error.data?.detail) {
        // Mapear erros de validacao para campos
        const fieldErrors = {}
        error.data.detail.forEach((err: any) => {
          fieldErrors[err.loc[1]] = err.msg
        })
        setErrors(fieldErrors)
      } else {
        toast.error(error.userFriendlyMessage)
      }
    },
  })

  return (
    <form onSubmit={() => createMutation.mutate(formData)}>
      <Input
        name="name"
        value={formData.name}
        error={errors.name}
        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
      />
      <Button loading={createMutation.isPending}>Salvar</Button>
    </form>
  )
}
```

---

## Tipos Principais

### Paginacao

```typescript
interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  size: number
  pages?: number
  has_more?: boolean
  next_cursor?: string
}
```

### Filtros

```typescript
interface PatientFilters {
  search?: string
  status?: 'active' | 'inactive' | 'archived' | 'paused' | 'completed'
  doctor_id?: string
  treatment_type?: string
}

interface AppointmentFilters {
  patient_id?: string
  practitioner_id?: string
  status?: 'scheduled' | 'completed' | 'cancelled'
  date_from?: string
  date_to?: string
}

interface TreatmentFilters {
  patient_id?: string
  doctor_id?: string
  status?: 'active' | 'completed' | 'suspended'
  treatment_type?: string
}
```

### Entidades

```typescript
interface Patient {
  id: string
  name: string
  email?: string
  phone?: string
  cpf?: string
  birth_date?: string
  treatment_type?: string
  status?: 'active' | 'inactive' | 'archived' | 'paused' | 'completed'
  doctor_id?: string
  current_day?: number
  flow_state?: string
  created_at?: string
  updated_at?: string
}

interface Appointment {
  id: string
  patient_id: string
  practitioner_id: string
  scheduled_at: string
  duration_minutes: number
  status: 'scheduled' | 'completed' | 'cancelled'
  notes?: string
}

interface Treatment {
  id: string
  patient_id: string
  doctor_id: string
  treatment_type: string
  start_date: string
  status: 'active' | 'completed' | 'suspended'
  planned_sessions?: string
  completed_sessions?: string
}
```

---

## Troubleshooting

### "Network Error" (Status 0)

**Causa**: Nao consegue conectar ao servidor

**Solucoes**:
1. Verificar se backend esta rodando
2. Verificar URL da API nas variaveis de ambiente
3. Verificar configuracao CORS
4. Testar conectividade de rede

### "CSRF Token Missing"

**Causa**: Protecao CSRF bloqueando requisicao

**Solucoes**:
1. Garantir que CSRF token foi buscado na inicializacao
2. Verificar se cookies estao habilitados
3. Verificar `withCredentials: true` nas requisicoes

### "Session Expired" (401)

**Causa**: Sessao de autenticacao invalida

**Solucoes**:
1. Redirecionar para login
2. Implementar refresh automatico de token
3. Tratar expiracao graciosamente

### "Rate Limited" (429)

**Causa**: Muitas requisicoes

**Solucoes**:
1. Implementar debounce em buscas
2. Adicionar loading states para evitar duplicatas
3. Mostrar countdown de retry para usuario

---

## Referencias

- **Codigo-fonte**: `src/lib/api-client/`
- **Tipos**: `src/lib/api-client/types.ts`
- **React Query**: https://tanstack.com/query/latest
- **Documentacao Backend**: `backend-hormonia/docs/`

---

**Versao**: 2.1.0
**Mantido por**: Equipe de Desenvolvimento Frontend
