# TypeScript Type Usage Guide

## Overview

This guide documents the TypeScript type patterns, conventions, and best practices used in the frontend-hormonia application. Following these guidelines ensures type safety, consistency, and maintainability across the codebase.

## Table of Contents

1. [Centralized Type Definitions](#centralized-type-definitions)
2. [Import Patterns](#import-patterns)
3. [Type vs Interface](#type-vs-interface)
4. [Discriminated Unions](#discriminated-unions)
5. [Generic Types](#generic-types)
6. [Common Patterns](#common-patterns)

---

## Centralized Type Definitions

All shared types are defined in centralized locations to avoid duplication and ensure consistency.

### Type File Structure

```
src/types/
├── api.ts          # API entities, requests, responses
├── shared.ts       # Common utilities, pagination, roles
├── api-responses.ts # Legacy (re-exports from api.ts)
└── quiz.ts         # Legacy (re-exports from api.ts)
```

### Primary Type Sources

- **`@/types/api.ts`** - Main source for all API-related types
  - Entity types (Patient, Message, Flow, Alert, Report, Quiz)
  - Enum types (PatientStatus, MessageType, AlertType, etc.)
  - Request/Response types
  - API client interface

- **`@/types/shared.ts`** - Shared utilities and common types
  - User roles and permissions
  - Pagination types
  - Base entity interfaces
  - API response wrappers

---

## Import Patterns

### ✅ Correct Import Patterns

Always import types from centralized locations using the `@/types` path alias:

```typescript
// ✅ Import from centralized types
import type { Patient, Message, Report } from '@/types/api'
import type { Priority, PaginatedResponse } from '@/types/shared'

// ✅ Import specific enums
import { PatientStatus, MessageType } from '@/types/api'

// ✅ Use type-only imports for better tree-shaking
import type { User } from '@/types/api'
```

### ❌ Incorrect Import Patterns

Avoid these patterns:

```typescript
// ❌ Relative imports from types directory
import type { Patient } from '../../types/api'

// ❌ Defining duplicate types locally
interface Patient {
  id: string
  name: string
}

// ❌ Importing from legacy type files
import type { Patient } from '@/types/api-responses'  // Use @/types/api instead
```

### Import Strategy by File Type

#### Components
```typescript
// Component imports
import type { Patient, Message } from '@/types/api'
import type { Priority } from '@/types/shared'
```

#### Hooks
```typescript
// Hook imports
import type { User, AuthTokens } from '@/types/api'
import type { LoadingState } from '@/types/shared'
```

#### Services
```typescript
// Service imports
import type { LoginCredentials, LoginResponse } from '@/types/api'
```

---

## Type vs Interface

### When to Use `type`

Use `type` for:

1. **Union types**
   ```typescript
   export type QuizLinkStatusValue = 'not_sent' | 'sent' | 'accessed' | 'completed' | 'expired'
   export type Priority = 'low' | 'medium' | 'high' | 'critical'
   ```

2. **Intersection types**
   ```typescript
   export type UserWithPermissions = User & { permissions: string[] }
   ```

3. **Mapped types**
   ```typescript
   export type Partial<T> = { [P in keyof T]?: T[P] }
   ```

4. **Tuple types**
   ```typescript
   export type Coordinate = [number, number]
   ```

### When to Use `interface`

Use `interface` for:

1. **Object shapes** (most common case)
   ```typescript
   export interface Patient {
     id: string
     name: string
     email?: string
   }
   ```

2. **Extendable contracts**
   ```typescript
   export interface BaseEntity {
     id: string
     created_at: string
   }
   
   export interface Patient extends BaseEntity {
     name: string
   }
   ```

3. **Declaration merging** (rare, but useful for extending third-party types)
   ```typescript
   interface Window {
     customProperty: string
   }
   ```

### General Rule

**Default to `interface` for object types, use `type` for everything else.**

---

## Discriminated Unions

Discriminated unions provide type-safe handling of different variants of a type.

### Pattern

```typescript
// Define discriminated union with a common discriminator property
export type FlowNode =
  | MessageFlowNode
  | ConditionFlowNode
  | ActionFlowNode
  | DelayFlowNode

export interface MessageFlowNode {
  type: 'message'  // Discriminator
  config: MessageNodeConfig
}

export interface ConditionFlowNode {
  type: 'condition'  // Discriminator
  config: ConditionNodeConfig
}
```

### Usage with Type Guards

```typescript
function processNode(node: FlowNode) {
  // TypeScript narrows the type based on the discriminator
  if (node.type === 'message') {
    // node is MessageFlowNode here
    console.log(node.config.content)
  } else if (node.type === 'condition') {
    // node is ConditionFlowNode here
    console.log(node.config.operator)
  }
}

// Or use type guard functions
function isMessageNode(node: FlowNode): node is MessageFlowNode {
  return node.type === 'message'
}

if (isMessageNode(node)) {
  // node is MessageFlowNode here
  console.log(node.config.content)
}
```

### Benefits

- **Type Safety**: TypeScript ensures you handle all cases
- **Autocomplete**: IDE provides accurate suggestions
- **Refactoring**: Adding new variants is safe and discoverable

---

## Generic Types

Generic types allow you to write reusable, type-safe code.

### Common Generic Patterns

#### 1. Paginated Response

```typescript
export interface CursorPage<T> {
  data: T[]
  next_cursor: string | null
  has_more: boolean
}

// Usage
const patientPage: CursorPage<Patient> = await api.patients.list()
const messagePage: CursorPage<Message> = await api.messages.list()
```

#### 2. API Response Wrapper

```typescript
export interface ApiResponse<T> {
  success: boolean
  data?: T
  error?: string
}

// Usage
const response: ApiResponse<Patient> = await createPatient(data)
if (response.success && response.data) {
  console.log(response.data.name)
}
```

#### 3. Query Result

```typescript
interface UseQueryResult<TData, TError> {
  data: TData | undefined
  error: TError | null
  isLoading: boolean
}

// Usage
const { data, error, isLoading } = useQuery<Patient[], Error>({
  queryKey: ['patients'],
  queryFn: fetchPatients
})
```

### Generic Constraints

Use constraints to limit what types can be used:

```typescript
// T must have an 'id' property
function findById<T extends { id: string }>(items: T[], id: string): T | undefined {
  return items.find(item => item.id === id)
}

// Works with any type that has an id
const patient = findById<Patient>(patients, 'patient-123')
const message = findById<Message>(messages, 'msg-456')
```

---

## Common Patterns

### 1. Optional Properties

Use `?` for optional properties:

```typescript
export interface Patient {
  id: string
  name: string
  email?: string  // Optional
  phone?: string  // Optional
}
```

With `exactOptionalPropertyTypes` enabled, optional properties must explicitly include `undefined`:

```typescript
// ✅ Correct with exactOptionalPropertyTypes
export interface User {
  avatar_url?: string | undefined
}

// ❌ Incorrect - missing undefined
export interface User {
  avatar_url?: string
}
```

### 2. Readonly Properties

Use `readonly` for immutable properties:

```typescript
export interface Patient {
  readonly id: string  // Cannot be reassigned
  name: string
}
```

### 3. Index Signatures

For dynamic property names:

```typescript
export interface QuizResponses {
  [questionId: string]: string
}

// Usage
const responses: QuizResponses = {
  'q1': 'Answer 1',
  'q2': 'Answer 2'
}
```

### 4. Utility Types

Leverage TypeScript's built-in utility types:

```typescript
// Partial - Make all properties optional
type PartialPatient = Partial<Patient>

// Pick - Select specific properties
type PatientSummary = Pick<Patient, 'id' | 'name' | 'email'>

// Omit - Exclude specific properties
type PatientWithoutId = Omit<Patient, 'id'>

// Required - Make all properties required
type RequiredPatient = Required<Patient>

// Record - Create object type with specific keys
type PatientMap = Record<string, Patient>
```

### 5. Type Assertions

Use type assertions sparingly and only when necessary:

```typescript
// ✅ Use when you know more than TypeScript
const element = document.getElementById('root') as HTMLDivElement

// ✅ Use with API responses when type is guaranteed
const patient = response.data as Patient

// ❌ Avoid using 'any'
const data = response as any  // Loses type safety
```

### 6. Type Guards

Create type guards for runtime type checking:

```typescript
function isPatient(value: unknown): value is Patient {
  return (
    typeof value === 'object' &&
    value !== null &&
    'id' in value &&
    'name' in value
  )
}

// Usage
if (isPatient(data)) {
  // data is Patient here
  console.log(data.name)
}
```

### 7. Const Assertions

Use `as const` for literal types:

```typescript
// Without const assertion
const colors = ['red', 'green', 'blue']  // string[]

// With const assertion
const colors = ['red', 'green', 'blue'] as const  // readonly ['red', 'green', 'blue']

// Useful for configuration objects
const config = {
  apiUrl: 'https://api.example.com',
  timeout: 5000
} as const
```

---

## Best Practices

### 1. Explicit Return Types

Always specify return types for public functions:

```typescript
// ✅ Explicit return type
export function getPatient(id: string): Promise<Patient> {
  return apiClient.patients.get(id)
}

// ❌ Implicit return type
export function getPatient(id: string) {
  return apiClient.patients.get(id)
}
```

### 2. Avoid `any`

Never use `any` unless absolutely necessary:

```typescript
// ❌ Avoid
function processData(data: any) {
  return data.value
}

// ✅ Use unknown and type guards
function processData(data: unknown) {
  if (typeof data === 'object' && data !== null && 'value' in data) {
    return (data as { value: string }).value
  }
  throw new Error('Invalid data')
}

// ✅ Or use generics
function processData<T extends { value: string }>(data: T) {
  return data.value
}
```

### 3. Consistent Naming

Follow consistent naming conventions:

- **Interfaces/Types**: PascalCase (`Patient`, `MessageType`)
- **Type parameters**: Single uppercase letter or PascalCase (`T`, `TData`, `TError`)
- **Enum values**: UPPER_SNAKE_CASE (`ACTIVE`, `IN_PROGRESS`)

### 4. Documentation

Add JSDoc comments to complex types:

```typescript
/**
 * Patient - Represents a patient in the system
 * 
 * Patients are the primary entities in the healthcare workflow.
 * They receive messages, complete quizzes, and have associated reports.
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
  /** Unique identifier */
  id: string
  /** Full name */
  name: string
  /** Email address (optional) */
  email?: string
  /** Current status */
  status: PatientStatus
}
```

---

## Migration Guide

### Updating Existing Code

When updating code to use centralized types:

1. **Find duplicate type definitions**
   ```bash
   # Search for local type definitions
   grep -r "interface Patient" src/
   ```

2. **Replace with centralized imports**
   ```typescript
   // Before
   interface Patient {
     id: string
     name: string
   }
   
   // After
   import type { Patient } from '@/types/api'
   ```

3. **Update all usages**
   - Remove local type definitions
   - Add import statement
   - Verify no breaking changes

4. **Run type checking**
   ```bash
   npm run typecheck
   ```

---

## Troubleshooting

### Common Type Errors

#### 1. "Property does not exist on type"

**Problem**: Accessing a property that doesn't exist on the type.

**Solution**: Check if the property is defined in the interface, or add it if missing.

```typescript
// Error: Property 'avatar_url' does not exist on type 'User'
console.log(user.avatar_url)

// Solution: Add to User interface
export interface User {
  id: string
  name: string
  avatar_url?: string  // Add missing property
}
```

#### 2. "Type 'X' is not assignable to type 'Y'"

**Problem**: Trying to assign incompatible types.

**Solution**: Ensure types match or use type assertions if you're certain.

```typescript
// Error: Type 'string' is not assignable to type 'PatientStatus'
const status: PatientStatus = 'active'

// Solution: Use enum value
const status: PatientStatus = PatientStatus.ACTIVE
```

#### 3. "Argument of type 'X' is not assignable to parameter of type 'Y'"

**Problem**: Function parameter type mismatch.

**Solution**: Ensure you're passing the correct type.

```typescript
// Error: Argument of type 'string' is not assignable to parameter of type 'Patient'
updatePatient('patient-123')

// Solution: Pass correct type
const patient: Patient = await getPatient('patient-123')
updatePatient(patient)
```

---

## Resources

- [TypeScript Handbook](https://www.typescriptlang.org/docs/handbook/intro.html)
- [TypeScript Deep Dive](https://basarat.gitbook.io/typescript/)
- [Type Challenges](https://github.com/type-challenges/type-challenges)

---

## Changelog

- **2024-10-24**: Initial documentation created
  - Documented centralized type structure
  - Added import patterns and best practices
  - Included discriminated unions and generic types
  - Added common patterns and troubleshooting guide
