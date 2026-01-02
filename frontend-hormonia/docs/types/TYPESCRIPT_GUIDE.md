# Guia TypeScript - Frontend Hormonia

## Visao Geral do Sistema de Tipos

Este guia consolida as diretrizes de tipagem TypeScript para o frontend-hormonia. Cobre definicoes centralizadas, padroes de tipo, seguranca de tipos e melhores praticas.

### Estrutura de Arquivos de Tipos

```
src/types/
├── api.ts          # Fonte principal - entidades, enums, requests/responses
├── shared.ts       # Utilitarios compartilhados, paginacao, roles
├── api-responses.ts # LEGADO - re-exporta de api.ts (deprecated)
└── quiz.ts         # LEGADO - re-exporta de api.ts (deprecated)
```

### Fontes Primarias

- **`@/types/api.ts`** - Todas as entidades API (Patient, Message, Flow, Alert, Report, Quiz)
- **`@/types/shared.ts`** - Roles, paginacao, interfaces base

---

## Padroes de Tipo

### 1. Imports Centralizados

**Regra**: Sempre importe tipos de arquivos centralizados usando path aliases.

```typescript
// CORRETO
import type { Patient, Message, Report } from '@/types/api'
import type { Priority, Status } from '@/types/shared'

// Enums precisam import de valor (nao type-only)
import { PatientStatus, MessageType } from '@/types/api'

// INCORRETO
import type { Patient } from '../../types/api'  // Import relativo
import type { Patient } from '../lib/types'      // Definicao local
```

### 2. Import Type-Only

**Regra**: Use `import type` para imports apenas de tipo.

```typescript
// Imports type-only (removidos em compilacao)
import type { User, Patient, Message } from '@/types/api'
import type { ComponentProps } from 'react'

// Imports de valor (incluidos no bundle)
import { useState, useEffect } from 'react'
import { PatientStatus } from '@/types/api'  // Enum precisa import de valor

// Import misto
import { type Patient, PatientStatus } from '@/types/api'
```

### 3. Organizacao de Imports

```typescript
// 1. Dependencias externas
import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'

// 2. Types externos
import type { ComponentProps } from 'react'

// 3. Types internos
import type { Patient, Message } from '@/types/api'
import type { Priority } from '@/types/shared'

// 4. Valores internos (enums, constantes)
import { PatientStatus, MessageType } from '@/types/api'

// 5. Componentes
import { Button } from '@/components/ui/button'

// 6. Hooks
import { usePatient } from '@/hooks/usePatient'

// 7. Utilitarios
import { formatDate } from '@/lib/utils'
```

---

## Diretrizes de Seguranca de Tipos

### Quando Usar Tipos Explicitos

#### 1. Return Types de Funcoes (SEMPRE)

```typescript
// CORRETO - Return type explicito
export function getPatient(id: string): Promise<Patient> {
  return apiClient.patients.get(id)
}

export function usePatient(patientId: string): UsePatientReturn {
  const [patient, setPatient] = useState<Patient | null>(null)
  return { patient, isLoading, error, refetch }
}

// INCORRETO - Sem return type
export function getPatient(id: string) {
  return apiClient.patients.get(id)  // Inferido como any
}
```

#### 2. Parametros de Callback

```typescript
// CORRETO
const activePatients = patients.filter((p: Patient) => p.status === 'active')
const patientIds = patients.map((p: Patient) => p.id)
const totalScore = reports.reduce((sum: number, r: Report) => sum + r.score, 0)

const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
  console.log(e.target.value)
}

// INCORRETO
const activePatients = patients.filter(p => p.status === 'active')  // any implicito
```

#### 3. State com Null ou Tipos Complexos

```typescript
// CORRETO
const [user, setUser] = useState<User | null>(null)
const [patients, setPatients] = useState<Patient[]>([])
const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle')

// INCORRETO
const [user, setUser] = useState(null)      // Inferido como null
const [patients, setPatients] = useState([]) // Inferido como never[]
```

#### 4. Props de Componentes

```typescript
interface PatientCardProps {
  patient: Patient
  onSelect?: (patient: Patient) => void
  isSelected?: boolean
  className?: string
}

export function PatientCard({
  patient,
  onSelect,
  isSelected = false,
  className
}: PatientCardProps): JSX.Element {
  return <div className={className}>{patient.name}</div>
}
```

### Quando Usar Tipos Inferidos

```typescript
// Variaveis simples - tipo obvio
const name = 'John Doe'  // string
const age = 30           // number
const isActive = true    // boolean

// Destructuring de fonte tipada
const { patient, isLoading, error } = usePatient(patientId)

// Retorno de funcao tipada
const patient = await getPatient('patient-123')  // Type: Patient
```

---

## Padroes de Tipos Genericos

### 1. Estruturas de Dados Reutilizaveis

```typescript
// Resposta paginada
interface CursorPage<T> {
  data: T[]
  next_cursor: string | null
  has_more: boolean
  total?: number
}

// Uso
const patientPage: CursorPage<Patient> = await api.patients.list()
const messagePage: CursorPage<Message> = await api.messages.list()

// Response wrapper
interface ApiResponse<TData, TError = Error> {
  success: boolean
  data?: TData
  error?: TError
}
```

### 2. Funcoes Genericas

```typescript
function findById<T extends { id: string }>(items: T[], id: string): T | undefined {
  return items.find(item => item.id === id)
}

function sortBy<T, K extends keyof T>(items: T[], key: K, order: 'asc' | 'desc' = 'asc'): T[] {
  return [...items].sort((a, b) => {
    const aVal = a[key]
    const bVal = b[key]
    if (aVal < bVal) return order === 'asc' ? -1 : 1
    if (aVal > bVal) return order === 'asc' ? 1 : -1
    return 0
  })
}

// Uso
const patient = findById<Patient>(patients, 'patient-123')
const sortedPatients = sortBy(patients, 'name', 'asc')
```

### 3. Hooks Genericos

```typescript
interface UseQueryResult<TData, TError = Error> {
  data: TData | undefined
  error: TError | null
  isLoading: boolean
  refetch: () => Promise<void>
}

function useQuery<TData, TError = Error>(
  options: UseQueryOptions<TData>
): UseQueryResult<TData, TError> {
  // Implementacao
}
```

### 4. Constraints de Tipo

```typescript
// Constraint extends
function getEntityId<T extends { id: string }>(entity: T): string {
  return entity.id
}

// Constraint keyof
function getProperty<T, K extends keyof T>(obj: T, key: K): T[K] {
  return obj[key]
}

// Multiplos parametros
function transform<TInput, TOutput>(
  input: TInput,
  transformer: (input: TInput) => TOutput
): TOutput {
  return transformer(input)
}
```

---

## Exemplos de Uso

### Component Props Interface

```typescript
interface UsePatientReturn {
  patient: Patient | null
  isLoading: boolean
  error: Error | null
  refetch: () => Promise<void>
  update: (data: Partial<Patient>) => Promise<void>
}

export function usePatient(patientId: string): UsePatientReturn {
  const [patient, setPatient] = useState<Patient | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  const refetch = async () => { /* ... */ }
  const update = async (data: Partial<Patient>) => { /* ... */ }

  return { patient, isLoading, error, refetch, update }
}
```

### API Client Types

```typescript
interface ApiClient {
  getPatient(id: string): Promise<Patient>
  listPatients(params?: QueryParams): Promise<CursorPage<Patient>>
  createPatient(data: CreatePatientRequest): Promise<Patient>
}

// Request/Response pairs
export interface CreatePatientRequest {
  name: string
  email: string
  phone?: string
  metadata?: Record<string, unknown>
}

export interface Patient {
  id: string
  name: string
  email: string
  phone?: string
  status: PatientStatus
  created_at: string
  updated_at: string
}
```

### Discriminated Unions

```typescript
type ApiResult<T> =
  | { status: 'success'; data: T }
  | { status: 'error'; error: string }
  | { status: 'loading' }

function handleResult<T>(result: ApiResult<T>): void {
  switch (result.status) {
    case 'success':
      console.log(result.data)  // Type: T
      break
    case 'error':
      console.error(result.error)  // Type: string
      break
    case 'loading':
      console.log('Loading...')
      break
  }
}

// Flow nodes
type FlowNode =
  | { type: 'message'; content: string; next: string }
  | { type: 'condition'; expression: string; trueNext: string; falseNext: string }
  | { type: 'action'; actionType: string; params: Record<string, unknown>; next: string }
  | { type: 'delay'; duration: number; next: string }
```

### Type Guards

```typescript
function isPatient(value: unknown): value is Patient {
  return (
    typeof value === 'object' &&
    value !== null &&
    'id' in value &&
    'name' in value &&
    typeof (value as Patient).id === 'string' &&
    typeof (value as Patient).name === 'string'
  )
}

function isSuccessResponse<T>(
  response: ApiResponse<T>
): response is { status: 'success'; data: T } {
  return response.status === 'success'
}

// Uso
if (isPatient(data)) {
  console.log(data.name)  // Type-safe
}
```

---

## Melhores Praticas

### Evitar `any`

```typescript
// INCORRETO
function processData(data: any) {
  return data.value  // Sem type checking
}

// CORRETO - Use unknown
function processApiResponse(data: unknown): Patient | null {
  if (isPatient(data)) {
    return data
  }
  return null
}

// CORRETO - Use generics
function processData<T>(data: T): T {
  return data
}

// CORRETO - Use Record para objetos dinamicos
const metadata: Record<string, string | number> = {
  version: '1.0',
  count: 42
}
```

### Usar Readonly

```typescript
interface Patient {
  readonly id: string  // ID nunca muda
  name: string
  readonly created_at: string  // Imutavel
  updated_at: string
}

// Arrays readonly
const VALID_STATUSES: readonly string[] = ['active', 'inactive', 'pending']

// Const assertion
const CONFIG = {
  apiUrl: 'https://api.example.com',
  timeout: 5000
} as const
```

### Utility Types

```typescript
interface Patient {
  id: string
  name: string
  email: string
  status: PatientStatus
  created_at: string
}

// Partial - todas propriedades opcionais
type PatientUpdate = Partial<Patient>

// Pick - selecionar propriedades
type PatientSummary = Pick<Patient, 'id' | 'name' | 'status'>

// Omit - excluir propriedades
type CreatePatientRequest = Omit<Patient, 'id' | 'created_at'>

// Required - todas obrigatorias
type CompletePatient = Required<Patient>

// Record - tipo de objeto
type PatientMap = Record<string, Patient>

// ReturnType - extrair return type
type FetchPatientResult = ReturnType<typeof fetchPatient>
```

### Documentacao JSDoc

```typescript
/**
 * Patient entity representing a patient in the healthcare system.
 *
 * @example
 * ```typescript
 * const patient: Patient = {
 *   id: 'patient-123',
 *   name: 'John Doe',
 *   email: 'john@example.com',
 *   status: PatientStatus.ACTIVE
 * }
 * ```
 */
export interface Patient {
  /** Unique identifier (UUID) */
  id: string

  /** Full name of the patient */
  name: string

  /** Email address (optional) */
  email?: string

  /** Current patient status */
  status: PatientStatus
}
```

---

## Erros Comuns e Solucoes

### Implicit Any em Callbacks

```typescript
// ERRO
const activePatients = patients.filter(p => p.status === 'active')

// SOLUCAO
const activePatients = patients.filter((p: Patient) => p.status === 'active')
```

### Array/Object Type Mismatch

```typescript
// ERRO - Retorna array mas espera objeto
interface UseQuizStatusReturn {
  quizStatus: QuizLinkStatus[]
}
// Consumer: quizStatus.link_url  // Erro: nao existe em array

// SOLUCAO
interface UseQuizStatusReturn {
  quizStatus: QuizLinkStatus | null
}
// Consumer: quizStatus?.link_url  // OK
```

### Propriedades Ausentes

```typescript
// ERRO
interface Report { id: string; title: string }
const completed = reports.filter(r => r.status === 'completed')  // status nao existe

// SOLUCAO
interface Report {
  id: string
  title: string
  status: ReportStatus  // Adicionar propriedade
}
```

### Optional com exactOptionalPropertyTypes

```typescript
// ERRO com exactOptionalPropertyTypes
interface User {
  email?: string  // Nao inclui undefined
}
const user: User = { email: undefined }  // Erro

// SOLUCAO
interface User {
  email?: string | undefined  // Inclui explicitamente
}
```

---

## Configuracao TypeScript

```json
{
  "compilerOptions": {
    "strict": true,
    "noImplicitAny": true,
    "noImplicitReturns": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "noPropertyAccessFromIndexSignature": true
  }
}
```

### Impacto das Configuracoes

- **noImplicitAny**: Erro em parametros sem tipo explicito
- **noUncheckedIndexedAccess**: `items[0]` retorna `T | undefined`
- **exactOptionalPropertyTypes**: `?` nao inclui `undefined` automaticamente
- **noPropertyAccessFromIndexSignature**: Requer `obj['key']` ao inves de `obj.key`

---

## Validacao

```bash
# Type checking
npm run typecheck

# Watch mode
npm run typecheck -- --watch
```

### Checklist Pre-Commit

- [ ] Funcoes exportadas tem return types explicitos
- [ ] Props de componentes tem interfaces explicitas
- [ ] Hooks customizados tem return types explicitos
- [ ] Parametros de callback tem tipos explicitos
- [ ] useState com null/tipos complexos tem type parameter
- [ ] Imports usam `@/` path aliases
- [ ] Type imports usam `import type`
- [ ] Nenhum uso de `any`
- [ ] `npm run typecheck` passa sem erros

---

## Recursos

### Documentacao Interna
- [API Types Reference](../../src/types/api.ts)
- [Shared Types](../../src/types/shared.ts)

### Recursos Externos
- [TypeScript Handbook](https://www.typescriptlang.org/docs/handbook/intro.html)
- [React TypeScript Cheatsheet](https://react-typescript-cheatsheet.netlify.app/)
- [Type Challenges](https://github.com/type-challenges/type-challenges)

---

## Historico de Consolidacao

### 2024-10-24

**Tipos Consolidados:**
- User e AuthTokens centralizados em `@/types/api.ts`
- QuizLinkStatus unificado com `QuizLinkStatusValue` type alias
- Report adicionado propriedades: `file_path`, `content`, `metadata`, `completed_at`
- PaginatedResponse movido para `@/types/shared.ts`

**Arquivos Atualizados:**
- `src/types/api.ts` - JSDoc adicionado, propriedades ausentes
- `src/types/api-responses.ts` - Convertido para re-exports
- `src/types/quiz.ts` - Convertido para re-exports
- `src/hooks/auth/types.ts` - Re-exporta tipos centralizados
- `src/services/firebase-auth.ts` - Usa User centralizado

---

*Ultima Atualizacao: 2024-10-24*
*Mantido por: Equipe de Desenvolvimento Frontend*
