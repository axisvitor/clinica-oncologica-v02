# TypeScript Type Safety Guidelines

## Overview

This document provides comprehensive guidelines for maintaining type safety in the frontend-hormonia application. It covers when to use explicit vs inferred types, type import conventions, generic type usage patterns, and best practices for writing type-safe TypeScript code.

## Table of Contents

1. [Explicit vs Inferred Types](#explicit-vs-inferred-types)
2. [Type Import Conventions](#type-import-conventions)
3. [Generic Type Usage Patterns](#generic-type-usage-patterns)
4. [Type Safety Best Practices](#type-safety-best-practices)
5. [Common Pitfalls and Solutions](#common-pitfalls-and-solutions)
6. [TypeScript Configuration](#typescript-configuration)

---

## Explicit vs Inferred Types

### When to Use Explicit Types

#### 1. Function Return Types (ALWAYS)

**Rule**: Always specify explicit return types for all exported functions, methods, and hooks.

**✅ Correct**:
```typescript
// Public API functions
export function getPatient(id: string): Promise<Patient> {
  return apiClient.patients.get(id)
}

// Custom hooks
export function usePatient(patientId: string): UsePatientReturn {
  const [patient, setPatient] = useState<Patient | null>(null)
  // ...
  return { patient, isLoading, error, refetch }
}

// Component functions
export function PatientCard({ patient }: PatientCardProps): JSX.Element {
  return <div>{patient.name}</div>
}
```

**❌ Incorrect**:
```typescript
// Missing return type - inferred as any or unknown
export function getPatient(id: string) {
  return apiClient.patients.get(id)
}

// Missing return type - harder to catch breaking changes
export function usePatient(patientId: string) {
  const [patient, setPatient] = useState(null)
  return { patient }
}
```

**Why**: Explicit return types:
- Provide clear API contracts
- Catch breaking changes at compile time
- Improve IDE autocomplete and documentation
- Make refactoring safer
- Prevent accidental type widening

---

#### 2. Function Parameters with Ambiguous Types

**Rule**: Add explicit types when the parameter type cannot be clearly inferred or when it's a callback.

**✅ Correct**:
```typescript
// Callback parameters
const activePatients = patients.filter((p: Patient) => p.status === 'active')
const patientIds = patients.map((p: Patient) => p.id)
const totalScore = reports.reduce((sum: number, r: Report) => sum + r.score, 0)

// Event handlers
const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
  console.log(e.target.value)
}

const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
  e.preventDefault()
}
```

**❌ Incorrect**:
```typescript
// Implicit any errors
const activePatients = patients.filter(p => p.status === 'active')
const handleChange = (e) => console.log(e.target.value)
```


**Why**: Explicit parameter types:
- Prevent implicit any errors
- Enable proper type checking in callbacks
- Provide better error messages
- Work correctly with strict TypeScript settings

---

#### 3. State Initialization with Null or Complex Types

**Rule**: Provide explicit type parameters to useState when the initial value is null, undefined, or when the type is complex.

**✅ Correct**:
```typescript
// Null initial value - needs explicit type
const [user, setUser] = useState<User | null>(null)

// Array of complex types
const [patients, setPatients] = useState<Patient[]>([])

// Union types
const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle')

// Complex objects
const [formData, setFormData] = useState<PatientFormData>({
  name: '',
  email: '',
  phone: ''
})
```

**❌ Incorrect**:
```typescript
// Type inferred as null only - can't assign User later
const [user, setUser] = useState(null)

// Type inferred as never[] - can't add items
const [patients, setPatients] = useState([])

// Type inferred as string - loses union constraint
const [status, setStatus] = useState('idle')
```

**Why**: Explicit state types:
- Prevent type narrowing issues
- Enable proper type checking on setState calls
- Support union types correctly
- Make component behavior clearer

---

#### 4. Component Props Interfaces

**Rule**: Always define explicit props interfaces for all components, even simple ones.

**✅ Correct**:
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
}: PatientCardProps) {
  return <div className={className}>{patient.name}</div>
}

// For simple components, inline is acceptable
export function LoadingSpinner({ size = 'md' }: { size?: 'sm' | 'md' | 'lg' }) {
  return <div className={`spinner-${size}`} />
}
```

**❌ Incorrect**:
```typescript
// No props interface - implicit any
export function PatientCard({ patient, onSelect, isSelected, className }) {
  return <div>{patient.name}</div>
}
```

**Why**: Explicit props interfaces:
- Provide clear component API documentation
- Enable IntelliSense and autocomplete
- Catch prop type errors at compile time
- Make component usage self-documenting

---

### When to Use Inferred Types

#### 1. Simple Variable Assignments

**Rule**: Let TypeScript infer types for simple, obvious assignments.

**✅ Correct**:
```typescript
// Primitives - type is obvious
const name = 'John Doe'  // string
const age = 30  // number
const isActive = true  // boolean

// Simple objects with clear structure
const config = {
  apiUrl: 'https://api.example.com',
  timeout: 5000,
  retries: 3
}

// Array literals with clear types
const colors = ['red', 'green', 'blue']  // string[]
const numbers = [1, 2, 3, 4, 5]  // number[]
```


**❌ Unnecessary Explicit Types**:
```typescript
// Over-specification - type is obvious
const name: string = 'John Doe'
const age: number = 30
const isActive: boolean = true
```

**Why**: Type inference:
- Reduces code verbosity
- Maintains type safety
- Automatically updates when values change
- Is the TypeScript default behavior

---

#### 2. Destructured Values from Typed Sources

**Rule**: When destructuring from a well-typed source, let TypeScript infer the types.

**✅ Correct**:
```typescript
// Destructuring from typed hook
const { patient, isLoading, error } = usePatient(patientId)

// Destructuring from typed props
function PatientCard({ patient, onSelect }: PatientCardProps) {
  const { name, email, status } = patient  // Types inferred from Patient
}

// Destructuring from API response
const { data, error } = await apiClient.patients.get(id)
```

**Why**: Destructured types:
- Are automatically inferred from source
- Stay in sync with source type changes
- Reduce redundant type annotations
- Keep code clean and readable

---

#### 3. Return Values from Typed Functions

**Rule**: When calling a function with an explicit return type, let TypeScript infer the result type.

**✅ Correct**:
```typescript
// Function has explicit return type
async function getPatient(id: string): Promise<Patient> {
  return apiClient.patients.get(id)
}

// Caller doesn't need explicit type
const patient = await getPatient('patient-123')  // Type: Patient
```

**Why**: Inferred return types:
- Automatically match function signature
- Update when function changes
- Reduce redundant annotations
- Maintain type safety

---

## Type Import Conventions

### Centralized Type Imports

**Rule**: Always import types from centralized type definition files using path aliases.

#### Primary Type Sources

```typescript
// ✅ CORRECT: Import from centralized locations
import type { Patient, Message, Report } from '@/types/api'
import type { Priority, Status } from '@/types/shared'

// ✅ CORRECT: Import enums as values (not type-only)
import { PatientStatus, MessageType, AlertType } from '@/types/api'

// ❌ INCORRECT: Relative imports
import type { Patient } from '../../types/api'
import type { Patient } from '../lib/types'

// ❌ INCORRECT: Local duplicate definitions
interface Patient {
  id: string
  name: string
}

// ❌ INCORRECT: Importing from legacy files
import type { Patient } from '@/types/api-responses'  // Use @/types/api
```

**Type File Structure**:
```
src/types/
├── api.ts          # Primary source - all API entities, enums, requests/responses
├── shared.ts       # Shared utilities, pagination, roles, common types
├── api-responses.ts # LEGACY - re-exports from api.ts (deprecated)
└── quiz.ts         # LEGACY - re-exports from api.ts (deprecated)
```

---

### Type-Only Imports

**Rule**: Use `import type` for type-only imports to enable better tree-shaking and reduce bundle size.

**✅ Correct**:
```typescript
// Type-only imports (erased at compile time)
import type { User, Patient, Message } from '@/types/api'
import type { ComponentProps } from 'react'

// Value imports (included in bundle)
import { useState, useEffect } from 'react'
import { PatientStatus } from '@/types/api'  // Enum needs value import

// Mixed imports
import { type Patient, PatientStatus } from '@/types/api'
```


**❌ Incorrect**:
```typescript
// Missing 'type' keyword - includes in bundle unnecessarily
import { User, Patient } from '@/types/api'

// Importing enum as type-only - won't work at runtime
import type { PatientStatus } from '@/types/api'
const status = PatientStatus.ACTIVE  // Error: PatientStatus is not defined
```

**Why**: Type-only imports:
- Reduce bundle size (types are erased at compile time)
- Make it clear what's used at runtime vs compile time
- Enable better tree-shaking
- Follow TypeScript best practices

---

### Import Organization

**Rule**: Organize imports in a consistent order for better readability.

**✅ Correct**:
```typescript
// 1. External dependencies (React, libraries)
import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'

// 2. Type imports from external dependencies
import type { ComponentProps } from 'react'

// 3. Internal type imports
import type { Patient, Message, Report } from '@/types/api'
import type { Priority } from '@/types/shared'

// 4. Internal value imports (enums, constants)
import { PatientStatus, MessageType } from '@/types/api'

// 5. Component imports
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'

// 6. Hook imports
import { usePatient } from '@/hooks/usePatient'

// 7. Utility imports
import { formatDate } from '@/lib/utils'

// 8. Style imports
import './PatientCard.css'
```

**Why**: Organized imports:
- Improve code readability
- Make dependencies clear
- Easier to spot missing imports
- Consistent across the codebase

---

### Import Patterns by File Type

#### Components
```typescript
import type { Patient, Message } from '@/types/api'
import type { ComponentProps } from 'react'
import { PatientStatus } from '@/types/api'
```

#### Hooks
```typescript
import type { User, AuthTokens } from '@/types/api'
import type { UseQueryResult } from '@tanstack/react-query'
```

#### Services/API Clients
```typescript
import type { 
  Patient, 
  CreatePatientRequest, 
  UpdatePatientRequest,
  CursorPage 
} from '@/types/api'
```

#### Utilities
```typescript
import type { Patient, Report } from '@/types/api'
```

---

## Generic Type Usage Patterns

### When to Use Generics

**Rule**: Use generics when you need type-safe reusable code that works with multiple types.

#### 1. Reusable Data Structures

**✅ Correct**:
```typescript
// Paginated response wrapper
interface CursorPage<T> {
  data: T[]
  next_cursor: string | null
  has_more: boolean
  total?: number
}

// Usage with different entity types
const patientPage: CursorPage<Patient> = await api.patients.list()
const messagePage: CursorPage<Message> = await api.messages.list()
const reportPage: CursorPage<Report> = await api.reports.list()

// API response wrapper
interface ApiResponse<TData, TError = Error> {
  success: boolean
  data?: TData
  error?: TError
  timestamp: string
}

// Usage
const response: ApiResponse<Patient> = await createPatient(data)
if (response.success && response.data) {
  console.log(response.data.name)
}
```


**Why**: Generic data structures:
- Work with any entity type
- Maintain type safety
- Reduce code duplication
- Provide consistent patterns

---

#### 2. Generic Functions and Utilities

**✅ Correct**:
```typescript
// Generic array utilities
function findById<T extends { id: string }>(items: T[], id: string): T | undefined {
  return items.find(item => item.id === id)
}

// Works with any entity that has an id
const patient = findById<Patient>(patients, 'patient-123')
const message = findById<Message>(messages, 'msg-456')

// Generic sorting
function sortBy<T, K extends keyof T>(items: T[], key: K, order: 'asc' | 'desc' = 'asc'): T[] {
  return [...items].sort((a, b) => {
    const aVal = a[key]
    const bVal = b[key]
    if (aVal < bVal) return order === 'asc' ? -1 : 1
    if (aVal > bVal) return order === 'asc' ? 1 : -1
    return 0
  })
}

// Usage
const sortedPatients = sortBy(patients, 'name', 'asc')
const sortedReports = sortBy(reports, 'created_at', 'desc')

// Generic data transformation
function mapToOptions<T extends { id: string; name: string }>(
  items: T[]
): Array<{ value: string; label: string }> {
  return items.map(item => ({
    value: item.id,
    label: item.name
  }))
}

// Usage
const patientOptions = mapToOptions(patients)
const doctorOptions = mapToOptions(doctors)
```

**Why**: Generic functions:
- Reusable across different types
- Type-safe transformations
- Reduce code duplication
- Maintain IntelliSense support

---

#### 3. Generic React Hooks

**✅ Correct**:
```typescript
// Generic data fetching hook
interface UseQueryOptions<TData> {
  queryKey: string[]
  queryFn: () => Promise<TData>
  enabled?: boolean
}

interface UseQueryResult<TData, TError = Error> {
  data: TData | undefined
  error: TError | null
  isLoading: boolean
  refetch: () => Promise<void>
}

function useQuery<TData, TError = Error>(
  options: UseQueryOptions<TData>
): UseQueryResult<TData, TError> {
  const [data, setData] = useState<TData | undefined>(undefined)
  const [error, setError] = useState<TError | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  // Implementation...

  return { data, error, isLoading, refetch }
}

// Usage with different data types
const { data: patients } = useQuery<Patient[]>({
  queryKey: ['patients'],
  queryFn: fetchPatients
})

const { data: report } = useQuery<Report>({
  queryKey: ['report', reportId],
  queryFn: () => fetchReport(reportId)
})

// Generic form hook
interface UseFormReturn<TFormData> {
  values: TFormData
  errors: Partial<Record<keyof TFormData, string>>
  handleChange: (field: keyof TFormData, value: any) => void
  handleSubmit: (e: React.FormEvent) => void
  reset: () => void
}

function useForm<TFormData extends Record<string, any>>(
  initialValues: TFormData,
  onSubmit: (values: TFormData) => void | Promise<void>
): UseFormReturn<TFormData> {
  // Implementation...
}

// Usage
interface PatientFormData {
  name: string
  email: string
  phone: string
}

const form = useForm<PatientFormData>(
  { name: '', email: '', phone: '' },
  async (values) => {
    await createPatient(values)
  }
)
```


**Why**: Generic hooks:
- Reusable across different data types
- Type-safe state management
- Consistent API patterns
- Better developer experience

---

### Generic Type Constraints

**Rule**: Use constraints to limit what types can be used with generics.

#### 1. Extends Constraint

**✅ Correct**:
```typescript
// Constraint: T must have an id property
function getEntityId<T extends { id: string }>(entity: T): string {
  return entity.id
}

// Works with any entity that has id
const patientId = getEntityId(patient)  // ✅
const messageId = getEntityId(message)  // ✅
const invalidId = getEntityId({ name: 'test' })  // ❌ Error: missing id

// Constraint: T must be an entity type
interface BaseEntity {
  id: string
  created_at: string
  updated_at: string
}

function trackEntityChanges<T extends BaseEntity>(entity: T): void {
  console.log(`Entity ${entity.id} updated at ${entity.updated_at}`)
}

// Constraint: T must be a specific union
type EntityType = Patient | Message | Report | Alert

function processEntity<T extends EntityType>(entity: T): void {
  // Type-safe processing
}
```

**Why**: Constraints:
- Ensure generic types have required properties
- Provide better type safety
- Enable property access in generic code
- Catch errors at compile time

---

#### 2. Keyof Constraint

**✅ Correct**:
```typescript
// Generic property accessor
function getProperty<T, K extends keyof T>(obj: T, key: K): T[K] {
  return obj[key]
}

// Usage - type-safe property access
const patient: Patient = { id: '1', name: 'John', email: 'john@example.com' }
const name = getProperty(patient, 'name')  // Type: string
const id = getProperty(patient, 'id')  // Type: string
const invalid = getProperty(patient, 'invalid')  // ❌ Error: invalid key

// Generic property setter
function setProperty<T, K extends keyof T>(obj: T, key: K, value: T[K]): T {
  return { ...obj, [key]: value }
}

// Usage
const updatedPatient = setProperty(patient, 'name', 'Jane')  // ✅
const invalidUpdate = setProperty(patient, 'name', 123)  // ❌ Error: wrong type

// Generic sorting by key
function sortByKey<T, K extends keyof T>(
  items: T[],
  key: K,
  order: 'asc' | 'desc' = 'asc'
): T[] {
  return [...items].sort((a, b) => {
    const aVal = a[key]
    const bVal = b[key]
    if (aVal < bVal) return order === 'asc' ? -1 : 1
    if (aVal > bVal) return order === 'asc' ? 1 : -1
    return 0
  })
}

// Usage - autocomplete for valid keys
const sorted = sortByKey(patients, 'name', 'asc')  // ✅
const invalid = sortByKey(patients, 'invalid', 'asc')  // ❌ Error
```

**Why**: Keyof constraints:
- Enable type-safe property access
- Provide autocomplete for object keys
- Prevent invalid property access
- Maintain type relationships

---

#### 3. Multiple Type Parameters

**✅ Correct**:
```typescript
// Multiple related type parameters
interface ApiClient<TRequest, TResponse> {
  send(request: TRequest): Promise<TResponse>
}

// Usage
const patientClient: ApiClient<CreatePatientRequest, Patient> = {
  send: async (request) => {
    // Implementation
  }
}

// Generic transformation with input/output types
function transform<TInput, TOutput>(
  input: TInput,
  transformer: (input: TInput) => TOutput
): TOutput {
  return transformer(input)
}

// Usage
const patientDto = transform<Patient, PatientDTO>(
  patient,
  (p) => ({ id: p.id, name: p.name })
)
```


// Generic map with key/value types
function createMap<K extends string | number, V>(
  items: V[],
  keyFn: (item: V) => K
): Map<K, V> {
  const map = new Map<K, V>()
  items.forEach(item => map.set(keyFn(item), item))
  return map
}

// Usage
const patientMap = createMap<string, Patient>(
  patients,
  (p) => p.id
)
```

**Why**: Multiple type parameters:
- Model complex type relationships
- Maintain type safety across transformations
- Enable flexible generic APIs
- Support advanced type patterns

---

### Generic Best Practices

#### 1. Meaningful Type Parameter Names

**✅ Correct**:
```typescript
// Descriptive names for clarity
interface UseQueryResult<TData, TError> { }
interface ApiResponse<TRequest, TResponse> { }
interface FormState<TFormData> { }

// Single letter for simple cases
function identity<T>(value: T): T { return value }
function first<T>(items: T[]): T | undefined { return items[0] }
```

**❌ Incorrect**:
```typescript
// Unclear single letters in complex cases
interface UseQueryResult<A, B> { }  // What are A and B?
interface ApiResponse<X, Y> { }  // Unclear purpose
```

---

#### 2. Default Type Parameters

**✅ Correct**:
```typescript
// Provide sensible defaults
interface ApiResponse<TData, TError = Error> {
  data?: TData
  error?: TError
}

// Usage - error defaults to Error
const response: ApiResponse<Patient> = await fetchPatient()

// Can override default if needed
const customResponse: ApiResponse<Patient, CustomError> = await fetchPatient()
```

**Why**: Default type parameters:
- Reduce boilerplate in common cases
- Maintain flexibility when needed
- Improve developer experience
- Follow principle of least surprise

---

## Type Safety Best Practices

### 1. Avoid `any` Type

**Rule**: Never use `any` unless absolutely necessary. Use `unknown` instead.

**✅ Correct**:
```typescript
// Use unknown for truly unknown data
function processApiResponse(data: unknown): Patient | null {
  if (isPatient(data)) {
    return data
  }
  return null
}

// Use type guards
function isPatient(value: unknown): value is Patient {
  return (
    typeof value === 'object' &&
    value !== null &&
    'id' in value &&
    'name' in value &&
    typeof (value as any).id === 'string' &&
    typeof (value as any).name === 'string'
  )
}

// Use generics for flexible types
function processData<T>(data: T): T {
  return data
}

// Use Record for dynamic objects
const metadata: Record<string, string | number> = {
  version: '1.0',
  count: 42
}
```

**❌ Incorrect**:
```typescript
// Loses all type safety
function processData(data: any) {
  return data.value  // No type checking
}

// Disables type checking
const patient: any = await fetchPatient()
patient.invalidProperty  // No error
```

**Why**: Avoiding `any`:
- Maintains type safety
- Catches errors at compile time
- Enables IntelliSense
- Prevents runtime errors

---

### 2. Use Discriminated Unions

**Rule**: Use discriminated unions for type-safe polymorphic data.

**✅ Correct**:
```typescript
// Define discriminated union
type ApiResult<T> =
  | { status: 'success'; data: T }
  | { status: 'error'; error: string }
  | { status: 'loading' }

// Type-safe handling
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
```


// Flow node types
type FlowNode =
  | { type: 'message'; content: string; next: string }
  | { type: 'condition'; expression: string; trueNext: string; falseNext: string }
  | { type: 'action'; actionType: string; params: Record<string, unknown>; next: string }
  | { type: 'delay'; duration: number; next: string }

function processNode(node: FlowNode): void {
  if (node.type === 'message') {
    console.log(node.content)  // Type narrowed to message node
  } else if (node.type === 'condition') {
    console.log(node.expression)  // Type narrowed to condition node
  }
  // TypeScript ensures all cases are handled
}
```

**Why**: Discriminated unions:
- Enable exhaustive type checking
- Provide type narrowing
- Prevent invalid property access
- Make code self-documenting

---

### 3. Use Readonly for Immutable Data

**Rule**: Mark properties as readonly when they shouldn't be modified.

**✅ Correct**:
```typescript
interface Patient {
  readonly id: string  // ID should never change
  name: string
  readonly created_at: string  // Creation time is immutable
  updated_at: string
}

// Readonly arrays
const VALID_STATUSES: readonly string[] = ['active', 'inactive', 'pending']

// Readonly objects
const CONFIG = {
  apiUrl: 'https://api.example.com',
  timeout: 5000
} as const

// Readonly function parameters
function processPatients(patients: readonly Patient[]): void {
  // Cannot modify the array
  // patients.push(newPatient)  // ❌ Error
}
```

**Why**: Readonly:
- Prevents accidental mutations
- Makes intent clear
- Enables compiler optimizations
- Catches bugs at compile time

---

### 4. Use Utility Types

**Rule**: Leverage TypeScript's built-in utility types to reduce duplication.

**✅ Correct**:
```typescript
interface Patient {
  id: string
  name: string
  email: string
  phone: string
  status: PatientStatus
  created_at: string
  updated_at: string
}

// Partial - all properties optional
type PatientUpdate = Partial<Patient>

// Pick - select specific properties
type PatientSummary = Pick<Patient, 'id' | 'name' | 'status'>

// Omit - exclude specific properties
type CreatePatientRequest = Omit<Patient, 'id' | 'created_at' | 'updated_at'>

// Required - make all properties required
type CompletePatient = Required<Patient>

// Record - create object type
type PatientMap = Record<string, Patient>

// ReturnType - extract function return type
type FetchPatientResult = ReturnType<typeof fetchPatient>

// Parameters - extract function parameters
type FetchPatientParams = Parameters<typeof fetchPatient>

// Awaited - unwrap Promise type
type PatientData = Awaited<ReturnType<typeof fetchPatient>>
```

**Why**: Utility types:
- Reduce code duplication
- Stay in sync with source types
- Provide consistent patterns
- Improve maintainability

---

### 5. Use Type Guards

**Rule**: Create type guards for runtime type checking.

**✅ Correct**:
```typescript
// Type predicate function
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

// Usage
function processData(data: unknown): void {
  if (isPatient(data)) {
    // data is Patient here
    console.log(data.name)
  }
}

// Discriminated union type guard
function isSuccessResponse<T>(
  response: ApiResponse<T>
): response is { status: 'success'; data: T } {
  return response.status === 'success'
}

// Usage
const response = await fetchPatient()
if (isSuccessResponse(response)) {
  console.log(response.data.name)  // Type-safe
}
```


**Why**: Type guards:
- Enable safe runtime type checking
- Provide type narrowing
- Prevent runtime errors
- Make code more robust

---

### 6. Document Complex Types

**Rule**: Add JSDoc comments to complex types for better documentation.

**✅ Correct**:
```typescript
/**
 * Patient entity representing a patient in the healthcare system.
 * 
 * Patients are the primary entities that receive care, complete quizzes,
 * and have associated medical reports.
 * 
 * @example
 * ```typescript
 * const patient: Patient = {
 *   id: 'patient-123',
 *   name: 'John Doe',
 *   email: 'john@example.com',
 *   status: PatientStatus.ACTIVE,
 *   created_at: '2024-01-01T00:00:00Z',
 *   updated_at: '2024-01-01T00:00:00Z'
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
  
  /** Timestamp when patient was created */
  created_at: string
  
  /** Timestamp when patient was last updated */
  updated_at: string
}

/**
 * Generic paginated response wrapper.
 * 
 * @template T - The type of items in the page
 */
export interface CursorPage<T> {
  /** Array of items in this page */
  data: T[]
  
  /** Cursor for the next page, null if no more pages */
  next_cursor: string | null
  
  /** Whether there are more pages available */
  has_more: boolean
  
  /** Total count of items (optional) */
  total?: number
}
```

**Why**: Documentation:
- Improves developer experience
- Provides context and examples
- Shows up in IDE tooltips
- Makes code self-documenting

---

## Common Pitfalls and Solutions

### 1. Implicit Any in Callbacks

**Problem**: Parameter implicitly has an 'any' type.

**❌ Problem**:
```typescript
const activePatients = patients.filter(p => p.status === 'active')  // Error: 'p' has implicit any
```

**✅ Solution**:
```typescript
const activePatients = patients.filter((p: Patient) => p.status === 'active')
```

---

### 2. Array/Object Type Mismatches

**Problem**: Type 'X[]' is not assignable to type 'X'.

**❌ Problem**:
```typescript
interface UseQuizStatusReturn {
  quizStatus: QuizLinkStatus[]  // Returns array
}

function PatientDetail() {
  const { quizStatus } = useQuizStatus()
  return <div>{quizStatus.link_url}</div>  // Error: Property doesn't exist on array
}
```

**✅ Solution**:
```typescript
interface UseQuizStatusReturn {
  quizStatus: QuizLinkStatus | null  // Returns single object or null
}

function PatientDetail() {
  const { quizStatus } = useQuizStatus()
  return <div>{quizStatus?.link_url}</div>  // ✅ Optional chaining
}
```

---

### 3. Missing Properties

**Problem**: Property 'x' does not exist on type 'Y'.

**❌ Problem**:
```typescript
interface Report {
  id: string
  title: string
}

const completed = reports.filter(r => r.status === 'completed')  // Error: Property 'status' doesn't exist
```

**✅ Solution**:
```typescript
interface Report {
  id: string
  title: string
  status: ReportStatus  // Add missing property
  type: ReportType
  created_at: string
}

const completed = reports.filter((r: Report) => r.status === 'completed')
```

---

### 4. Optional Property Types with exactOptionalPropertyTypes

**Problem**: Type 'undefined' is not assignable to type 'X'.

**❌ Problem**:
```typescript
interface User {
  id: string
  name: string
  email?: string  // Optional but doesn't include undefined
}

const user: User = {
  id: '1',
  name: 'John',
  email: undefined  // Error with exactOptionalPropertyTypes
}
```

**✅ Solution**:
```typescript
interface User {
  id: string
  name: string
  email?: string | undefined  // Explicitly include undefined
}

const user: User = {
  id: '1',
  name: 'John',
  email: undefined  // ✅ Now valid
}
```

---

### 5. State Property Access

**Problem**: Property 'state' does not exist on type 'X'.

**❌ Problem**:
```typescript
interface AuthContextValue {
  login: () => void
  logout: () => void
}

function MedicoRoutes() {
  const { state } = useMedicoAuth()  // Error: Property 'state' doesn't exist
  return <div>{state.user.name}</div>
}
```

**✅ Solution**:
```typescript
interface MedicoAuthState {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
}

interface AuthContextValue extends MedicoAuthState {
  login: () => void
  logout: () => void
}

function MedicoRoutes() {
  const { user, isAuthenticated, isLoading } = useMedicoAuth()  // Destructure directly
  return <div>{user?.name}</div>
}
```

---

### 6. Type Assertion Overuse

**Problem**: Overusing type assertions loses type safety.

**❌ Problem**:
```typescript
const data = response as any  // Loses all type safety
const patient = data as Patient  // Unsafe assertion
```

**✅ Solution**:
```typescript
// Use type guards instead
if (isPatient(data)) {
  const patient = data  // Type narrowed safely
}

// Or validate with schema
const patient = PatientSchema.parse(data)  // Runtime validation
```

---

## TypeScript Configuration

### Strict Mode Settings

Our `tsconfig.json` uses strict mode for maximum type safety:

```json
{
  "compilerOptions": {
    "strict": true,                           // Enable all strict checks
    "noImplicitAny": true,                    // Error on implicit any
    "noImplicitReturns": true,                // Error on missing return statements
    "noImplicitThis": true,                   // Error on implicit this
    "noUncheckedIndexedAccess": true,         // Add undefined to index access
    "exactOptionalPropertyTypes": true,       // Strict optional property checking
    "noPropertyAccessFromIndexSignature": true // Require bracket notation for index access
  }
}
```

### What These Settings Mean

#### `noImplicitAny`
```typescript
// ❌ Error with noImplicitAny
function process(data) {  // Error: Parameter 'data' implicitly has an 'any' type
  return data
}

// ✅ Must add explicit type
function process(data: unknown) {
  return data
}
```

#### `noUncheckedIndexedAccess`
```typescript
const items: string[] = ['a', 'b', 'c']

// With noUncheckedIndexedAccess
const item = items[0]  // Type: string | undefined (not just string)

// Must check for undefined
if (item !== undefined) {
  console.log(item.toUpperCase())  // ✅ Safe
}
```

#### `exactOptionalPropertyTypes`
```typescript
interface User {
  name: string
  email?: string  // ❌ Error: must be string | undefined
}

// ✅ Correct
interface User {
  name: string
  email?: string | undefined
}
```

#### `noPropertyAccessFromIndexSignature`
```typescript
interface Config {
  [key: string]: string
}

const config: Config = { apiUrl: 'https://api.example.com' }

// ❌ Error with noPropertyAccessFromIndexSignature
const url = config.apiUrl

// ✅ Must use bracket notation
const url = config['apiUrl']
```

---

## Validation and Testing

### Type Checking Commands

```bash
# Run type checking
npm run typecheck

# Run type checking in watch mode
npm run typecheck -- --watch

# Run type checking in CI
npm run typecheck:ci
```

### Pre-Commit Validation

Ensure type checking passes before committing:

```bash
# Add to .husky/pre-commit
npm run typecheck
```

### IDE Integration

#### VSCode Settings

```json
{
  "typescript.tsdk": "node_modules/typescript/lib",
  "typescript.enablePromptUseWorkspaceTsdk": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": true
  }
}
```

#### Recommended Extensions

- **TypeScript and JavaScript Language Features** (built-in)
- **ESLint** - For linting
- **Prettier** - For formatting
- **Error Lens** - Inline error display

---

## Quick Reference

### Type Safety Checklist

Before committing code, verify:

- [ ] All exported functions have explicit return types
- [ ] All component props have explicit interfaces
- [ ] All custom hooks have explicit return types
- [ ] All callback parameters have explicit types
- [ ] All useState calls with null/complex types have explicit type parameters
- [ ] All imports use `@/` path aliases
- [ ] All type imports use `import type` syntax
- [ ] No `any` types used (except Record<string, any> for truly dynamic data)
- [ ] Optional properties include `| undefined` with exactOptionalPropertyTypes
- [ ] `npm run typecheck` passes with 0 errors

---

### Common Type Patterns Quick Reference

```typescript
// Component Props
interface MyComponentProps {
  data: DataType
  onAction?: (item: DataType) => void
}

// Custom Hook Return
interface UseMyHookReturn {
  data: DataType | null
  isLoading: boolean
  error: Error | null
  refetch: () => Promise<void>
}

// API Function
export function fetchData(id: string): Promise<DataType> {
  return apiClient.get(id)
}

// Generic Function
function process<T extends BaseType>(item: T): T {
  return item
}

// Type Guard
function isDataType(value: unknown): value is DataType {
  return typeof value === 'object' && value !== null && 'id' in value
}

// Discriminated Union
type Result<T> =
  | { status: 'success'; data: T }
  | { status: 'error'; error: string }
```

---

## Additional Resources

### Internal Documentation

- [Type Patterns Guide](./TYPE_PATTERNS.md) - Detailed type patterns with examples
- [Type Usage Guide](./TYPE_USAGE_GUIDE.md) - Type usage conventions
- [Type Consolidation Summary](./TYPE_CONSOLIDATION_SUMMARY.md) - Type refactoring history
- [API Types Reference](../src/types/api.ts) - Centralized type definitions

### External Resources

- [TypeScript Handbook](https://www.typescriptlang.org/docs/handbook/intro.html) - Official TypeScript documentation
- [TypeScript Deep Dive](https://basarat.gitbook.io/typescript/) - Comprehensive TypeScript guide
- [React TypeScript Cheatsheet](https://react-typescript-cheatsheet.netlify.app/) - React-specific TypeScript patterns
- [Type Challenges](https://github.com/type-challenges/type-challenges) - Practice TypeScript skills

### Contributing

When adding new types or patterns:

1. Follow the guidelines in this document
2. Add examples to [TYPE_PATTERNS.md](./TYPE_PATTERNS.md)
3. Update [TYPE_USAGE_GUIDE.md](./TYPE_USAGE_GUIDE.md) if needed
4. Run `npm run typecheck` to verify
5. Document any new patterns or conventions

---

## Changelog

### 2024-10-24
- Initial creation of Type Safety Guidelines
- Documented explicit vs inferred types
- Added type import conventions
- Included generic type usage patterns
- Added best practices and common pitfalls
- Documented TypeScript configuration
- Added validation and testing guidelines

---

**Last Updated**: 2024-10-24  
**Maintained by**: Frontend Development Team  
**Version**: 1.0.0

