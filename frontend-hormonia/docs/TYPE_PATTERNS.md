# TypeScript Type Patterns Guide

## Overview

This document provides comprehensive guidance on TypeScript type patterns used throughout the frontend-hormonia codebase. It includes common patterns, error resolution strategies, and before/after examples to help maintain type safety and consistency.

## Table of Contents

1. [Type Import Patterns](#type-import-patterns)
2. [Component Type Patterns](#component-type-patterns)
3. [Hook Type Patterns](#hook-type-patterns)
4. [API Client Type Patterns](#api-client-type-patterns)
5. [Error Resolution Patterns](#error-resolution-patterns)
6. [Advanced Type Patterns](#advanced-type-patterns)

---

## Type Import Patterns

### Pattern 1: Centralized Type Imports

**Rule**: Always import types from centralized type definition files.

**✅ Correct**:
```typescript
import type { Patient, Message, Report } from '@/types/api'
import type { Priority, Status } from '@/types/shared'
```

**❌ Incorrect**:
```typescript
import type { Patient } from '../../types/api'
import type { Patient } from '../lib/types'
import { Patient } from '@/types/api' // Missing 'type' keyword
```

**Why**: Centralized imports ensure consistency, enable tree-shaking, and make refactoring easier.

---

### Pattern 2: Type-Only Imports

**Rule**: Use `import type` for type-only imports to avoid runtime overhead.

**✅ Correct**:
```typescript
import type { User } from '@/types/api'
import { useState } from 'react'

const MyComponent = () => {
  const [user, setUser] = useState<User | null>(null)
  return <div>{user?.name}</div>
}
```

**❌ Incorrect**:
```typescript
import { User } from '@/types/api' // Runtime import for type-only usage
```

**Why**: Type-only imports are erased at compile time, reducing bundle size.

---

## Component Type Patterns

### Pattern 3: Component Props Interface

**Rule**: Define explicit props interfaces for all components.

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
  return (
    <div className={className} onClick={() => onSelect?.(patient)}>
      {patient.name}
    </div>
  )
}
```

**❌ Incorrect**:
```typescript
// No props interface
export function PatientCard({ patient, onSelect, isSelected, className }) {
  // Implicit any errors
}
```

**Why**: Explicit props interfaces provide IntelliSense, type safety, and documentation.

---

### Pattern 4: Event Handler Types

**Rule**: Use React's built-in event types for event handlers.

**✅ Correct**:
```typescript
interface FormProps {
  onSubmit: (data: FormData) => void
}

function MyForm({ onSubmit }: FormProps) {
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    console.log(e.target.value)
  }
  
  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    onSubmit(new FormData(e.currentTarget))
  }
  
  return (
    <form onSubmit={handleSubmit}>
      <input onChange={handleChange} />
    </form>
  )
}
```

**❌ Incorrect**:
```typescript
function MyForm({ onSubmit }) {
  const handleChange = (e) => { // Implicit any
    console.log(e.target.value)
  }
  
  const handleSubmit = (e) => { // Implicit any
    e.preventDefault()
  }
}
```

**Why**: React event types provide proper type checking for event properties.

---

### Pattern 5: Callback Parameter Types

**Rule**: Add explicit types to all callback parameters in array methods.

**✅ Correct**:
```typescript
import type { Report } from '@/types/api'

function ReportsPage() {
  const [reports, setReports] = useState<Report[]>([])
  
  const completedReports = reports.filter((r: Report) => r.status === 'completed')
  const reportIds = reports.map((r: Report) => r.id)
  const totalScore = reports.reduce((sum: number, r: Report) => sum + r.score, 0)
  
  return <div>{completedReports.length} completed</div>
}
```

**❌ Incorrect**:
```typescript
function ReportsPage() {
  const [reports, setReports] = useState([])
  
  const completedReports = reports.filter(r => r.status === 'completed') // Implicit any
  const reportIds = reports.map(r => r.id) // Implicit any
}
```

**Why**: Explicit types prevent implicit any errors and enable proper type checking.

---

## Hook Type Patterns

### Pattern 6: Custom Hook Return Types

**Rule**: Define explicit return type interfaces for custom hooks.

**✅ Correct**:
```typescript
import type { Patient } from '@/types/api'

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
  
  const refetch = async () => {
    // Implementation
  }
  
  const update = async (data: Partial<Patient>) => {
    // Implementation
  }
  
  return { patient, isLoading, error, refetch, update }
}
```

**❌ Incorrect**:
```typescript
export function usePatient(patientId: string) {
  // No explicit return type
  const [patient, setPatient] = useState(null) // Inferred as null
  const [isLoading, setIsLoading] = useState(false)
  
  return { patient, isLoading }
}
```

**Why**: Explicit return types ensure consistency across hook consumers and provide better IntelliSense.

---

### Pattern 7: Hook State Initialization

**Rule**: Provide explicit type parameters to useState when initial value is null or ambiguous.

**✅ Correct**:
```typescript
import type { User, Message } from '@/types/api'

function useAuth() {
  const [user, setUser] = useState<User | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [count, setCount] = useState(0) // Type inferred correctly
  
  return { user, messages, count }
}
```

**❌ Incorrect**:
```typescript
function useAuth() {
  const [user, setUser] = useState(null) // Type inferred as null only
  const [messages, setMessages] = useState([]) // Type inferred as never[]
}
```

**Why**: Explicit type parameters prevent type narrowing issues and enable proper type checking.

---

## API Client Type Patterns

### Pattern 8: API Response Types

**Rule**: Define explicit response types for all API calls.

**✅ Correct**:
```typescript
import type { Patient, CursorPage } from '@/types/api'

interface ApiClient {
  getPatient(id: string): Promise<Patient>
  listPatients(params?: QueryParams): Promise<CursorPage<Patient>>
  createPatient(data: CreatePatientRequest): Promise<Patient>
}

class ApiClientImpl implements ApiClient {
  async getPatient(id: string): Promise<Patient> {
    const response = await fetch(`/api/patients/${id}`)
    return response.json()
  }
  
  async listPatients(params?: QueryParams): Promise<CursorPage<Patient>> {
    const response = await fetch('/api/patients')
    return response.json()
  }
  
  async createPatient(data: CreatePatientRequest): Promise<Patient> {
    const response = await fetch('/api/patients', {
      method: 'POST',
      body: JSON.stringify(data)
    })
    return response.json()
  }
}
```

**❌ Incorrect**:
```typescript
class ApiClient {
  async getPatient(id: string) { // No return type
    const response = await fetch(`/api/patients/${id}`)
    return response.json() // Returns Promise<any>
  }
}
```

**Why**: Explicit return types ensure type safety throughout the data flow.

---

### Pattern 9: Request/Response Type Pairs

**Rule**: Define paired request and response types for API operations.

**✅ Correct**:
```typescript
// Request types
export interface CreatePatientRequest {
  name: string
  email: string
  phone?: string
  metadata?: Record<string, unknown>
}

export interface UpdatePatientRequest {
  name?: string
  email?: string
  phone?: string
  status?: PatientStatus
}

// Response types
export interface Patient {
  id: string
  name: string
  email: string
  phone?: string
  status: PatientStatus
  created_at: string
  updated_at: string
  metadata?: Record<string, unknown>
}

// Usage
async function createPatient(data: CreatePatientRequest): Promise<Patient> {
  // Implementation
}
```

**Why**: Paired types clearly distinguish between input and output data structures.

---

## Error Resolution Patterns

### Pattern 10: Fixing Implicit Any in Callbacks

**Problem**: Parameter 'x' implicitly has an 'any' type.

**Before**:
```typescript
const users = await fetchUsers()
const activeUsers = users.filter(u => u.status === 'active') // Error: 'u' has implicit any
```

**After**:
```typescript
import type { User } from '@/types/api'

const users = await fetchUsers()
const activeUsers = users.filter((u: User) => u.status === 'active')
```

**Solution**: Add explicit type annotation to the callback parameter.

---

### Pattern 11: Fixing Array/Object Type Mismatches

**Problem**: Type 'X[]' is not assignable to type 'X'.

**Before**:
```typescript
interface UseQuizStatusReturn {
  quizStatus: QuizLinkStatus[] // Returns array
}

function useQuizStatus(): UseQuizStatusReturn {
  const [status, setStatus] = useState<QuizLinkStatus[]>([])
  return { quizStatus: status }
}

// Consumer expects single object
function PatientDetail() {
  const { quizStatus } = useQuizStatus()
  return <div>{quizStatus.link_url}</div> // Error: Property doesn't exist on array
}
```

**After**:
```typescript
interface UseQuizStatusReturn {
  quizStatus: QuizLinkStatus | null // Returns single object or null
}

function useQuizStatus(): UseQuizStatusReturn {
  const [status, setStatus] = useState<QuizLinkStatus | null>(null)
  return { quizStatus: status }
}

// Consumer works correctly
function PatientDetail() {
  const { quizStatus } = useQuizStatus()
  return <div>{quizStatus?.link_url}</div>
}
```

**Solution**: Align the return type with consumer expectations.

---

### Pattern 12: Fixing Missing Properties

**Problem**: Property 'x' does not exist on type 'Y'.

**Before**:
```typescript
interface Report {
  id: string
  title: string
}

const reports: Report[] = []
const completed = reports.filter(r => r.status === 'completed') // Error: Property 'status' doesn't exist
```

**After**:
```typescript
interface Report {
  id: string
  title: string
  status: ReportStatus // Add missing property
  type: ReportType
  created_at: string
}

const reports: Report[] = []
const completed = reports.filter((r: Report) => r.status === 'completed')
```

**Solution**: Add missing properties to the interface definition.

---

### Pattern 13: Fixing Optional Property Types

**Problem**: Type 'undefined' is not assignable to type 'X' with exactOptionalPropertyTypes.

**Before**:
```typescript
interface User {
  id: string
  name: string
  email?: string // Optional but doesn't include undefined
}

const user: User = {
  id: '1',
  name: 'John',
  email: undefined // Error with exactOptionalPropertyTypes
}
```

**After**:
```typescript
interface User {
  id: string
  name: string
  email?: string | undefined // Explicitly include undefined
}

const user: User = {
  id: '1',
  name: 'John',
  email: undefined // Now valid
}
```

**Solution**: Add `| undefined` to optional properties when using `exactOptionalPropertyTypes`.

---

### Pattern 14: Fixing State Property Access

**Problem**: Property 'state' does not exist on type 'X'.

**Before**:
```typescript
interface AuthContextValue {
  login: () => void
  logout: () => void
}

function useMedicoAuth(): AuthContextValue {
  // Implementation
}

// Consumer tries to access state
function MedicoRoutes() {
  const { state } = useMedicoAuth() // Error: Property 'state' doesn't exist
  return <div>{state.user.name}</div>
}
```

**After**:
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

function useMedicoAuth(): AuthContextValue {
  // Implementation returns all properties
}

// Consumer destructures directly
function MedicoRoutes() {
  const { user, isAuthenticated, isLoading } = useMedicoAuth()
  return <div>{user?.name}</div>
}
```

**Solution**: Flatten the context value interface to expose all properties directly.

---

## Advanced Type Patterns

### Pattern 15: Discriminated Unions

**Rule**: Use discriminated unions for type-safe polymorphic data.

**✅ Correct**:
```typescript
type FlowNode = 
  | { type: 'message'; content: string; next: string }
  | { type: 'condition'; expression: string; trueNext: string; falseNext: string }
  | { type: 'action'; actionType: string; params: Record<string, unknown>; next: string }
  | { type: 'delay'; duration: number; next: string }

function processNode(node: FlowNode) {
  switch (node.type) {
    case 'message':
      return sendMessage(node.content, node.next)
    case 'condition':
      return evaluateCondition(node.expression, node.trueNext, node.falseNext)
    case 'action':
      return executeAction(node.actionType, node.params, node.next)
    case 'delay':
      return scheduleDelay(node.duration, node.next)
  }
}
```

**Why**: Discriminated unions enable exhaustive type checking and prevent invalid property access.

---

### Pattern 16: Generic Type Constraints

**Rule**: Use generic constraints to enforce type relationships.

**✅ Correct**:
```typescript
interface Entity {
  id: string
  created_at: string
}

interface CursorPage<T extends Entity> {
  items: T[]
  next_cursor: string | null
  has_more: boolean
}

function processCursorPage<T extends Entity>(page: CursorPage<T>): string[] {
  return page.items.map(item => item.id) // Type-safe: id exists on all entities
}
```

**Why**: Generic constraints ensure type safety while maintaining flexibility.

---

### Pattern 17: Utility Type Patterns

**Rule**: Use TypeScript utility types for common transformations.

**✅ Correct**:
```typescript
interface Patient {
  id: string
  name: string
  email: string
  status: PatientStatus
  created_at: string
}

// Partial for updates
type PatientUpdate = Partial<Patient>

// Pick for specific fields
type PatientSummary = Pick<Patient, 'id' | 'name' | 'status'>

// Omit for excluding fields
type CreatePatientRequest = Omit<Patient, 'id' | 'created_at'>

// Required for making all optional fields required
type CompletePatient = Required<Patient>

// Usage
async function updatePatient(id: string, data: PatientUpdate): Promise<Patient> {
  // Implementation
}
```

**Why**: Utility types reduce duplication and maintain consistency with source types.

---

### Pattern 18: Type Guards

**Rule**: Use type guards for runtime type checking.

**✅ Correct**:
```typescript
interface SuccessResponse<T> {
  success: true
  data: T
}

interface ErrorResponse {
  success: false
  error: string
}

type ApiResponse<T> = SuccessResponse<T> | ErrorResponse

function isSuccessResponse<T>(response: ApiResponse<T>): response is SuccessResponse<T> {
  return response.success === true
}

async function fetchPatient(id: string): Promise<Patient> {
  const response: ApiResponse<Patient> = await api.get(`/patients/${id}`)
  
  if (isSuccessResponse(response)) {
    return response.data // Type narrowed to SuccessResponse
  } else {
    throw new Error(response.error) // Type narrowed to ErrorResponse
  }
}
```

**Why**: Type guards enable safe runtime type narrowing.

---

## Best Practices Summary

1. **Always use centralized type imports** from `@/types/api` and `@/types/shared`
2. **Use `import type`** for type-only imports to reduce bundle size
3. **Define explicit props interfaces** for all React components
4. **Add explicit return types** to all custom hooks and API methods
5. **Type all callback parameters** in array methods (map, filter, reduce)
6. **Use React's built-in event types** for event handlers
7. **Initialize useState with explicit types** when initial value is null or ambiguous
8. **Use discriminated unions** for polymorphic data structures
9. **Apply generic constraints** to enforce type relationships
10. **Create type guards** for runtime type checking

## Common Pitfalls to Avoid

1. ❌ Using relative imports for types instead of path aliases
2. ❌ Omitting return types on public API methods
3. ❌ Using `any` type as a quick fix
4. ❌ Forgetting to add `| undefined` to optional properties with `exactOptionalPropertyTypes`
5. ❌ Not typing callback parameters in array methods
6. ❌ Using runtime imports for type-only usage
7. ❌ Creating duplicate type definitions across files
8. ❌ Accessing properties without type guards on union types

## Validation Checklist

Before committing code, ensure:

- [ ] All imports use `@/` path aliases
- [ ] All type imports use `import type` syntax
- [ ] All component props have explicit interfaces
- [ ] All custom hooks have explicit return types
- [ ] All callback parameters have explicit types
- [ ] All API methods have explicit return types
- [ ] `npm run typecheck` passes with 0 errors
- [ ] No `any` types used (except in Record<string, any> for truly dynamic data)

---

## Additional Resources

- [TypeScript Handbook](https://www.typescriptlang.org/docs/handbook/intro.html)
- [React TypeScript Cheatsheet](https://react-typescript-cheatsheet.netlify.app/)
- [Type Usage Guide](./TYPE_USAGE_GUIDE.md)
- [Type Consolidation Summary](./TYPE_CONSOLIDATION_SUMMARY.md)

---

*Last Updated: 2025-10-24*
*Maintained by: Frontend Development Team*
