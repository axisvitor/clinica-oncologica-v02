# API Integration Guide - Frontend Hormonia

Este guia explica como integrar com as APIs do backend no frontend Hormonia, usando o cliente API centralizado, React Query e WebSockets.

## Índice

1. [Arquitetura do Cliente API](#arquitetura-do-cliente-api)
2. [Fazendo Requisições HTTP](#fazendo-requisições-http)
3. [React Query Integration](#react-query-integration)
4. [Autenticação](#autenticação)
5. [Error Handling](#error-handling)
6. [WebSocket Integration](#websocket-integration)
7. [Testing API Integration](#testing-api-integration)
8. [Best Practices](#best-practices)

---

## Arquitetura do Cliente API

### Estrutura Modular

O cliente API é organizado em módulos independentes:

```
src/lib/api-client/
├── index.ts          # Re-exports e tipos principais
├── core.ts           # Cliente HTTP base com retry logic
├── auth.ts           # Endpoints de autenticação
├── patients.ts       # Endpoints de pacientes
├── monthly-quiz.ts   # Endpoints de questionários mensais
└── analytics.ts      # Endpoints de analytics
```

### Cliente Base

Toda comunicação HTTP passa pelo `ApiClientCore`:

```typescript
// src/lib/api-client/core.ts
export class ApiClientCore {
  private baseURL: string
  private authToken: string | null
  private csrfToken: string | null

  // Métodos HTTP
  async get<T>(endpoint: string, params?: Record<string, any>): Promise<T>
  async post<T>(endpoint: string, data?: any): Promise<T>
  async put<T>(endpoint: string, data?: any): Promise<T>
  async delete<T>(endpoint: string): Promise<T>
  async patch<T>(endpoint: string, data?: any): Promise<T>
}
```

**Features do cliente base**:
- ✅ Automatic retry with exponential backoff
- ✅ Request timeout handling (30s padrão)
- ✅ CSRF token management
- ✅ JWT token injection
- ✅ Cookie-based session support
- ✅ Comprehensive error handling
- ✅ Type-safe responses

### Módulos Especializados

Cada módulo expõe métodos específicos de domínio:

```typescript
// src/lib/api-client/patients.ts
export class PatientsApi {
  constructor(private core: ApiClientCore) {}

  async list(filters?: PatientFilters): Promise<PaginatedResponse<Patient>>
  async getById(id: string): Promise<Patient>
  async create(data: PatientCreate): Promise<Patient>
  async update(id: string, data: PatientUpdate): Promise<Patient>
  async delete(id: string): Promise<void>
}
```

---

## Fazendo Requisições HTTP

### Setup Inicial

O cliente API é inicializado automaticamente:

```typescript
// src/lib/api-client/index.ts
import { apiClient } from '@/lib/api-client'

// Cliente já configurado e pronto para uso
// Base URL vem de VITE_API_BASE_URL
```

### GET Requests

#### Exemplo 1: Listar Pacientes

```typescript
import { apiClient } from '@/lib/api-client'

// Sem filtros
const response = await apiClient.patients.list()

// Com filtros
const filtered = await apiClient.patients.list({
  search: 'Maria',
  status: 'active',
  treatment_type: 'Terapia Hormonal',
  page: 1,
  size: 20
})

// Resposta tipada
console.log(filtered.items)  // Patient[]
console.log(filtered.total)  // number
console.log(filtered.has_more) // boolean
```

**Tipo de resposta**:
```typescript
interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  size: number
  has_more: boolean
  next_cursor?: string
}
```

#### Exemplo 2: Buscar Por ID

```typescript
// Buscar paciente específico
const patient = await apiClient.patients.getById('patient-123')

// Type-safe
console.log(patient.nome)          // string
console.log(patient.email)         // string
console.log(patient.treatment_type) // string
```

#### Exemplo 3: Dashboard Stats

```typescript
import { apiClient } from '@/lib/api-client'

const stats = await apiClient.analytics.getDashboardMetrics({
  timeframe: 'week' // 'week' | 'month' | 'year'
})

console.log(stats.total_patients)
console.log(stats.active_flows)
console.log(stats.quiz_completion_rate)
```

---

### POST Requests

#### Exemplo 1: Criar Paciente

```typescript
import { apiClient } from '@/lib/api-client'
import type { PatientCreate } from '@/lib/api-client'

const newPatient: PatientCreate = {
  nome: 'Maria Silva',
  email: 'maria@example.com',
  telefone: '+5511999999999',
  data_nascimento: '1980-05-15',
  treatment_type: 'Terapia Hormonal Feminina',
  consentimento_whatsapp: true
}

try {
  const patient = await apiClient.patients.create(newPatient)
  console.log('Paciente criado:', patient.id)
} catch (error) {
  if (error instanceof ApiError) {
    console.error('Erro ao criar:', error.userFriendlyMessage)
  }
}
```

#### Exemplo 2: Login

```typescript
import { apiClient } from '@/lib/api-client'

const credentials = {
  email: 'admin@hormonia.com.br',
  password: 'Admin@123'
}

try {
  const response = await apiClient.auth.login(credentials)

  // Resposta inclui tokens
  console.log(response.user)         // User object
  console.log(response.access_token) // JWT token
  console.log(response.expires_in)   // Expiration time

  // Token é automaticamente armazenado no cliente
} catch (error) {
  // Trata erro de autenticação
  console.error('Login falhou:', error.userFriendlyMessage)
}
```

#### Exemplo 3: Criar Quiz Link

```typescript
import { apiClient } from '@/lib/api-client'

const linkData = {
  patient_id: 'patient-123',
  month: 1,
  year: 2025,
  expiration_days: 30
}

const quizLink = await apiClient.monthlyQuiz.createLink(linkData)

console.log('Link gerado:', quizLink.link_url)
console.log('Token:', quizLink.token)
console.log('Expira em:', quizLink.expiration_date)
```

---

### PUT/PATCH Requests

#### Exemplo 1: Atualizar Paciente (PUT - full update)

```typescript
import { apiClient } from '@/lib/api-client'

const updates = {
  nome: 'Maria Silva Santos',
  email: 'maria.santos@example.com',
  telefone: '+5511988888888',
  treatment_type: 'Terapia Hormonal Avançada'
}

const updated = await apiClient.patients.update('patient-123', updates)
console.log('Paciente atualizado:', updated)
```

#### Exemplo 2: Atualizar Parcial (PATCH)

```typescript
// Atualizar apenas email
const patched = await apiClient.patients.patch('patient-123', {
  email: 'novo-email@example.com'
})
```

---

### DELETE Requests

#### Exemplo: Deletar Paciente

```typescript
import { apiClient } from '@/lib/api-client'

try {
  await apiClient.patients.delete('patient-123')
  console.log('Paciente deletado com sucesso')
} catch (error) {
  if (error instanceof ApiError && error.status === 404) {
    console.error('Paciente não encontrado')
  }
}
```

---

## React Query Integration

### Por Que React Query?

React Query gerencia **server state** (dados da API):

- ✅ Cache automático
- ✅ Refetch em background
- ✅ Invalidação inteligente
- ✅ Loading/error states
- ✅ Pagination support
- ✅ Optimistic updates

### Setup do QueryClient

```typescript
// src/lib/react-query/queryClient.ts
import { QueryClient } from '@tanstack/react-query'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,     // 5 minutos
      gcTime: 10 * 60 * 1000,       // 10 minutos (cacheTime)
      retry: 2,                      // 2 tentativas
      refetchOnWindowFocus: false,   // Não refaz em focus
    },
  },
})
```

### Fetching Data (useQuery)

#### Exemplo 1: Hook Customizado

```typescript
// src/hooks/usePatients.ts
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'

export function usePatients(filters?: PatientFilters) {
  return useQuery({
    queryKey: ['patients', filters],
    queryFn: () => apiClient.patients.list(filters),
    staleTime: 5 * 60 * 1000, // 5 min cache
  })
}

// Uso no componente
const { data, isLoading, error } = usePatients({ status: 'active' })

if (isLoading) return <Spinner />
if (error) return <ErrorMessage error={error} />

return <PatientList patients={data.items} />
```

#### Exemplo 2: Query com Dependência

```typescript
// Hook que depende de ID (pode ser null)
export function usePatient(patientId: string | null) {
  return useQuery({
    queryKey: ['patient', patientId],
    queryFn: () => apiClient.patients.getById(patientId!),
    enabled: !!patientId, // Só executa se ID existir
  })
}

// Uso
const { data: patient } = usePatient(selectedPatientId)
```

#### Exemplo 3: Múltiplas Queries Paralelas

```typescript
import { useQueries } from '@tanstack/react-query'

const results = useQueries({
  queries: [
    {
      queryKey: ['patients'],
      queryFn: () => apiClient.patients.list(),
    },
    {
      queryKey: ['stats'],
      queryFn: () => apiClient.analytics.getDashboardMetrics(),
    },
    {
      queryKey: ['quiz-templates'],
      queryFn: () => apiClient.monthlyQuiz.listTemplates(),
    },
  ],
})

const [patientsQuery, statsQuery, templatesQuery] = results
```

---

### Mutating Data (useMutation)

#### Exemplo 1: Criar Paciente

```typescript
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import { toast } from 'sonner'

export function useCreatePatient() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: PatientCreate) => apiClient.patients.create(data),

    onSuccess: (newPatient) => {
      // Invalida cache para forçar refetch
      queryClient.invalidateQueries({ queryKey: ['patients'] })

      // Feedback visual
      toast.success('Paciente criado com sucesso!')
    },

    onError: (error: ApiError) => {
      toast.error(error.userFriendlyMessage)
    },
  })
}

// Uso no componente
const createPatient = useCreatePatient()

const handleSubmit = async (formData: PatientCreate) => {
  await createPatient.mutateAsync(formData)
}
```

#### Exemplo 2: Atualizar com Optimistic Update

```typescript
export function useUpdatePatient() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: PatientUpdate }) =>
      apiClient.patients.update(id, data),

    // Atualização otimista (UI atualiza antes da resposta)
    onMutate: async ({ id, data }) => {
      // Cancela queries em andamento
      await queryClient.cancelQueries({ queryKey: ['patient', id] })

      // Snapshot do estado anterior
      const previousPatient = queryClient.getQueryData(['patient', id])

      // Atualiza UI otimisticamente
      queryClient.setQueryData(['patient', id], (old: Patient) => ({
        ...old,
        ...data,
      }))

      // Retorna contexto para rollback
      return { previousPatient }
    },

    // Rollback em caso de erro
    onError: (err, variables, context) => {
      queryClient.setQueryData(
        ['patient', variables.id],
        context?.previousPatient
      )
      toast.error('Erro ao atualizar paciente')
    },

    // Sempre refaz a query no final
    onSettled: (data, error, variables) => {
      queryClient.invalidateQueries({ queryKey: ['patient', variables.id] })
    },
  })
}
```

#### Exemplo 3: Deletar com Confirmação

```typescript
export function useDeletePatient() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (patientId: string) => apiClient.patients.delete(patientId),

    onSuccess: (_, patientId) => {
      // Remove do cache imediatamente
      queryClient.removeQueries({ queryKey: ['patient', patientId] })

      // Invalida lista
      queryClient.invalidateQueries({ queryKey: ['patients'] })

      toast.success('Paciente removido com sucesso')
    },
  })
}

// Uso com confirmação
const deletePatient = useDeletePatient()

const handleDelete = async (id: string) => {
  if (confirm('Tem certeza que deseja deletar este paciente?')) {
    await deletePatient.mutateAsync(id)
  }
}
```

---

### Pagination

#### Exemplo: Paginação com Cursor

```typescript
export function usePatients(filters?: PatientFilters) {
  const [cursorsByPage, setCursorsByPage] = useState<Record<number, string>>({})
  const page = filters?.page || 1

  const query = useQuery({
    queryKey: ['patients', filters, page],
    queryFn: async () => {
      const cursor = cursorsByPage[page]
      const response = await apiClient.patients.list({
        ...filters,
        cursor,
        limit: filters?.size || 20,
      })

      // Armazena cursor da próxima página
      if (response.next_cursor) {
        setCursorsByPage(prev => ({
          ...prev,
          [page + 1]: response.next_cursor,
        }))
      }

      return response
    },
  })

  return {
    ...query,
    hasMore: query.data?.has_more,
    nextCursor: query.data?.next_cursor,
  }
}
```

---

## Autenticação

### Flow de Autenticação

```typescript
// 1. Login
const { access_token, user } = await apiClient.auth.login({
  email: 'user@example.com',
  password: 'password123',
})

// 2. Token é automaticamente armazenado
apiClient.setAuthToken(access_token)

// 3. Todas as requisições agora incluem o token
// Header: Authorization: Bearer <token>

// 4. Token é renovado automaticamente 5min antes de expirar
// (gerenciado pelo AuthContext)
```

### Integração com AuthContext

```typescript
// src/contexts/AuthContext.tsx
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)

  const login = async (credentials: LoginCredentials) => {
    const response = await apiClient.auth.login(credentials)

    // Armazena token no cliente
    apiClient.setAuthToken(response.access_token)

    // Armazena usuário no state
    setUser(response.user)

    // Persiste no localStorage
    localStorage.setItem('auth_token', response.access_token)
  }

  const logout = async () => {
    await apiClient.auth.logout()
    apiClient.setAuthToken(null)
    setUser(null)
    localStorage.removeItem('auth_token')
  }

  // Auto-refresh token
  useEffect(() => {
    const interval = setInterval(async () => {
      const token = localStorage.getItem('auth_token')
      if (token) {
        try {
          const refreshed = await apiClient.auth.refreshToken()
          apiClient.setAuthToken(refreshed.access_token)
        } catch {
          logout()
        }
      }
    }, 5 * 60 * 1000) // A cada 5 minutos

    return () => clearInterval(interval)
  }, [])

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}
```

### Protected Routes

```typescript
import { Navigate } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth()

  if (isLoading) {
    return <LoadingSpinner />
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

// Uso nas rotas
<Route
  path="/dashboard"
  element={
    <ProtectedRoute>
      <DashboardPage />
    </ProtectedRoute>
  }
/>
```

---

## Error Handling

### ApiError Class

```typescript
export class ApiError extends Error {
  constructor(
    public status: number,           // HTTP status code
    public data: unknown,             // Error data from API
    message?: string,                 // Technical message
    public userFriendlyMessage?: string  // User-facing message
  ) {
    super(message || `API Error: ${status}`)
    this.name = 'ApiError'
  }
}
```

### Error Handling Patterns

#### Pattern 1: Try-Catch

```typescript
try {
  const patient = await apiClient.patients.create(data)
  toast.success('Paciente criado!')
} catch (error) {
  if (error instanceof ApiError) {
    // Usar mensagem amigável
    toast.error(error.userFriendlyMessage)

    // Log técnico para debug
    console.error('[API Error]', {
      status: error.status,
      message: error.message,
      data: error.data,
    })

    // Tratamento específico por status
    switch (error.status) {
      case 401:
        // Redirecionar para login
        navigate('/login')
        break
      case 403:
        // Mostrar mensagem de permissão
        toast.error('Você não tem permissão para esta ação')
        break
      case 422:
        // Validação falhou - mostrar erros de campo
        setFormErrors(error.data.detail)
        break
    }
  }
}
```

#### Pattern 2: React Query Error

```typescript
const { data, error } = useQuery({
  queryKey: ['patients'],
  queryFn: () => apiClient.patients.list(),
  retry: (failureCount, error) => {
    // Não fazer retry em erros 4xx (client errors)
    if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
      return false
    }
    // Retry até 3 vezes em erros 5xx
    return failureCount < 3
  },
})

if (error instanceof ApiError) {
  return <ErrorAlert message={error.userFriendlyMessage} />
}
```

#### Pattern 3: Error Boundary

```typescript
// src/components/error/ErrorBoundary.tsx
export class ErrorBoundary extends React.Component {
  state = { hasError: false, error: null }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    // Log para Sentry ou outro serviço
    console.error('Error Boundary caught:', error, errorInfo)

    if (error instanceof ApiError) {
      // Tratamento específico para erros de API
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

// Uso
<ErrorBoundary>
  <App />
</ErrorBoundary>
```

---

## WebSocket Integration

### WebSocket Manager

```typescript
// src/lib/websocket.ts
import { WebSocketManager } from '@/lib/websocket'

const ws = new WebSocketManager()

// Conectar (usa VITE_WS_URL)
await ws.connect(authToken)

// Subscrever a eventos
ws.on('quiz:update', (data) => {
  console.log('Quiz atualizado:', data)
  queryClient.invalidateQueries({ queryKey: ['quiz', data.quiz_id] })
})

ws.on('patient:status_change', (data) => {
  console.log('Status mudou:', data)
  toast.info(`Paciente ${data.patient_name} mudou para ${data.status}`)
})

// Enviar mensagem
ws.send('subscribe:patient', { patient_id: 'patient-123' })

// Desconectar
ws.disconnect()
```

### React Hook para WebSocket

```typescript
// src/hooks/useWebSocket.ts
import { useEffect } from 'react'
import { useWebSocketManager } from '@/lib/websocket'

export function usePatientWebSocket(patientId: string) {
  const ws = useWebSocketManager()

  useEffect(() => {
    if (!patientId) return

    // Subscrever ao patient room
    ws.send('join:patient', { patient_id: patientId })

    // Listener para atualizações
    const handleUpdate = (data: any) => {
      console.log('Patient updated via WS:', data)
      // Invalidar cache do React Query
      queryClient.invalidateQueries({ queryKey: ['patient', patientId] })
    }

    ws.on('patient:update', handleUpdate)

    // Cleanup
    return () => {
      ws.off('patient:update', handleUpdate)
      ws.send('leave:patient', { patient_id: patientId })
    }
  }, [patientId, ws])
}

// Uso no componente
const PatientDetail = ({ id }: { id: string }) => {
  usePatientWebSocket(id) // Auto-subscribe/unsubscribe

  const { data: patient } = useQuery({
    queryKey: ['patient', id],
    queryFn: () => apiClient.patients.getById(id),
  })

  return <div>{patient?.nome}</div>
}
```

---

## Testing API Integration

### Mock API Responses

```typescript
// tests/mocks/handlers.ts
import { rest } from 'msw'

export const handlers = [
  // Mock GET /api/v2/patients
  rest.get('/api/v2/patients', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        items: [
          { id: '1', nome: 'Patient 1', email: 'p1@example.com' },
          { id: '2', nome: 'Patient 2', email: 'p2@example.com' },
        ],
        total: 2,
        page: 1,
        size: 20,
        has_more: false,
      })
    )
  }),

  // Mock POST /api/v2/patients
  rest.post('/api/v2/patients', async (req, res, ctx) => {
    const body = await req.json()
    return res(
      ctx.status(201),
      ctx.json({
        id: 'new-id',
        ...body,
      })
    )
  }),

  // Mock error
  rest.get('/api/v2/patients/:id', (req, res, ctx) => {
    const { id } = req.params
    if (id === 'error') {
      return res(
        ctx.status(404),
        ctx.json({
          detail: 'Patient not found',
          user_message: 'Paciente não encontrado',
        })
      )
    }
    return res(ctx.status(200), ctx.json({ id, nome: 'Test Patient' }))
  }),
]
```

### Setup MSW

```typescript
// tests/setup.ts
import { setupServer } from 'msw/node'
import { handlers } from './mocks/handlers'

export const server = setupServer(...handlers)

beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
```

### Test Hook

```typescript
// tests/hooks/usePatients.test.ts
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { usePatients } from '@/hooks/usePatients'

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  )
}

test('fetches patients', async () => {
  const { result } = renderHook(() => usePatients(), {
    wrapper: createWrapper(),
  })

  expect(result.current.isLoading).toBe(true)

  await waitFor(() => {
    expect(result.current.isLoading).toBe(false)
  })

  expect(result.current.patients).toHaveLength(2)
  expect(result.current.patients[0].nome).toBe('Patient 1')
})
```

---

## Best Practices

### 1. Use Custom Hooks

❌ **Evite** usar API client diretamente nos componentes:
```typescript
// Ruim
const Component = () => {
  const [patients, setPatients] = useState([])

  useEffect(() => {
    apiClient.patients.list().then(setPatients)
  }, [])
}
```

✅ **Prefira** hooks customizados com React Query:
```typescript
// Bom
const Component = () => {
  const { data: patients, isLoading } = usePatients()
}
```

### 2. Centralize Query Keys

```typescript
// src/lib/query-keys.ts
export const queryKeys = {
  patients: {
    all: ['patients'] as const,
    lists: () => [...queryKeys.patients.all, 'list'] as const,
    list: (filters: PatientFilters) =>
      [...queryKeys.patients.lists(), filters] as const,
    details: () => [...queryKeys.patients.all, 'detail'] as const,
    detail: (id: string) => [...queryKeys.patients.details(), id] as const,
  },
  quiz: {
    all: ['quiz'] as const,
    sessions: (patientId: string) =>
      [...queryKeys.quiz.all, 'sessions', patientId] as const,
  },
}

// Uso
useQuery({
  queryKey: queryKeys.patients.detail(patientId),
  queryFn: () => apiClient.patients.getById(patientId),
})
```

### 3. Handle Loading States

```typescript
const { data, isLoading, isFetching, error } = usePatients()

if (isLoading) {
  return <Spinner />  // Primeira carga
}

if (error) {
  return <ErrorMessage error={error} />
}

return (
  <div>
    {isFetching && <RefreshIndicator />}  {/* Background refresh */}
    <PatientList patients={data.items} />
  </div>
)
```

### 4. Optimistic Updates

Use para melhorar UX em ações rápidas:

```typescript
const mutation = useMutation({
  mutationFn: updatePatient,
  onMutate: async (newData) => {
    // Atualiza UI imediatamente
    await queryClient.cancelQueries({ queryKey: ['patient', id] })
    const previous = queryClient.getQueryData(['patient', id])
    queryClient.setQueryData(['patient', id], newData)
    return { previous }
  },
  onError: (err, newData, context) => {
    // Reverte em caso de erro
    queryClient.setQueryData(['patient', id], context.previous)
  },
})
```

### 5. Debounce Search

```typescript
import { useDebounce } from '@/hooks/useDebounce'

const [search, setSearch] = useState('')
const debouncedSearch = useDebounce(search, 300)

const { data } = usePatients({
  search: debouncedSearch,  // Só busca 300ms após parar de digitar
})
```

### 6. Prefetch for Better UX

```typescript
const queryClient = useQueryClient()

const handleMouseEnter = (patientId: string) => {
  // Prefetch ao passar mouse
  queryClient.prefetchQuery({
    queryKey: ['patient', patientId],
    queryFn: () => apiClient.patients.getById(patientId),
  })
}

<PatientCard onMouseEnter={() => handleMouseEnter(patient.id)} />
```

### 7. Type Everything

```typescript
// Sempre defina tipos explícitos
const { data } = useQuery<Patient>({
  queryKey: ['patient', id],
  queryFn: () => apiClient.patients.getById(id),
})

// `data` é automaticamente tipado como Patient | undefined
```

---

## Referências

- **[API Client Source](../src/lib/api-client/)** - Código-fonte do cliente
- **[React Query Docs](https://tanstack.com/query/latest)** - Documentação oficial
- **[Environment Variables](ENVIRONMENT_VARIABLES.md)** - Configuração de URLs
- **[Type Safety Guidelines](TYPE_SAFETY_GUIDELINES.md)** - Padrões TypeScript

---

*Última atualização: 2025-11-13*
*Mantido por: Equipe Hormonia*
