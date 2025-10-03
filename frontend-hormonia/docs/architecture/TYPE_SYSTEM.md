# Type System Documentation

## Overview

The Frontend-v2 project has been refactored to use a centralized, highly efficient type system that provides maximum type safety and developer experience. This document explains the new structure and how to use it effectively.

## 🎯 Key Benefits

- **Centralized Types**: All types are organized in a single `/types` directory
- **Enhanced Type Safety**: Comprehensive interfaces with readonly properties and strict typing
- **Better IntelliSense**: Rich type information and autocomplete support
- **Utility Types**: Advanced TypeScript utilities for complex type operations
- **Backward Compatibility**: Legacy imports still work during migration
- **Performance**: Optimized type definitions reduce compilation time

## 📁 Directory Structure

```
/types/
├── index.ts          # Central export hub
├── shared.ts         # Base types and utilities
├── auth.ts           # Authentication types
├── api.ts            # API entities and client types
├── websocket.ts      # Real-time communication types
└── flow-designer.ts  # Flow designer specific types (existing)

/lib/types/           # Legacy location (deprecated)
├── api.ts            # Re-exports from /types/api
├── ai.ts             # Re-exports from /types/api
├── flow.ts           # Re-exports from /types/api
└── websocket.ts      # Re-exports from /types/websocket

/hooks/auth/
└── types.ts          # Re-exports from /types/auth
```

## 🚀 Usage Guide

### Importing Types

**✅ Recommended: Import from centralized types**
```typescript
// Import specific types
import type { User, Patient, ApiResponse } from '@/types'

// Import specific categories
import type { AuthState, LoginCredentials } from '@/types/auth'
import type { WebSocketEventType, WebSocketMessage } from '@/types/websocket'

// Import everything (not recommended for large imports)
import * as Types from '@/types'
```

**⚠️ Legacy: Still works but deprecated**
```typescript
// These still work during migration
import type { User } from '@/hooks/auth/types'
import type { Patient } from '@/lib/types/api'
```

### Type Categories

#### 1. Shared Types (`/types/shared.ts`)

Base types used throughout the application:

```typescript
// Core interfaces
interface BaseEntity {
  readonly id: string
  readonly created_at: string
  readonly updated_at: string
}

// Utility types
type DeepPartial<T> = { [P in keyof T]?: T[P] extends object ? DeepPartial<T[P]> : T[P] }
type PartialBy<T, K extends keyof T> = Omit<T, K> & Partial<Pick<T, K>>

// Common enums
enum Status {
  ACTIVE = 'active',
  INACTIVE = 'inactive',
  PENDING = 'pending'
}

// Query parameters
interface PaginationParams {
  readonly page?: number
  readonly size?: number
}
```

#### 2. Authentication Types (`/types/auth.ts`)

Comprehensive auth system types:

```typescript
// Main user interface
interface User extends BaseEntity {
  readonly email: string
  readonly full_name: string
  readonly role: UserRole
  readonly permissions: readonly string[]
  readonly is_active: boolean
}

// Auth state management
interface AuthState {
  readonly user: User | null
  readonly token: string | null
  readonly isAuthenticated: boolean
  readonly isLoading: boolean
}

// Hook return types
interface UseAuthReturn {
  readonly user: User | null
  readonly login: (email: string, password: string) => Promise<LoginResponse>
  readonly logout: () => Promise<void>
  // ... more methods
}
```

#### 3. API Types (`/types/api.ts`)

Domain entities and API client types:

```typescript
// Core entities
interface Patient extends BaseEntity {
  readonly name: string
  readonly email?: string
  readonly phone: string
  readonly status: PatientStatus
}

interface Message extends BaseEntity {
  readonly patient_id: string
  readonly content: string
  readonly direction: MessageDirection
  readonly type: MessageType
  readonly status: MessageStatus
}

// API client interface
interface ApiClient {
  readonly patients: {
    readonly list: (params?: PatientQueryParams) => Promise<PaginatedResponse<Patient>>
    readonly get: (id: string) => Promise<Patient>
    readonly create: (data: CreatePatientRequest) => Promise<Patient>
    // ... more methods
  }
  // ... more endpoints
}
```

#### 4. WebSocket Types (`/types/websocket.ts`)

Real-time communication types:

```typescript
// Event types
enum WebSocketEventType {
  PATIENT_UPDATED = 'patient_updated',
  MESSAGE_SENT = 'message_sent',
  FLOW_COMPLETED = 'flow_completed'
}

// Message structure
interface WebSocketMessage<T = unknown> extends BaseEvent<T> {
  readonly type: WebSocketEventType
  readonly data: T
  readonly timestamp: string
}

// Manager interface
interface IWebSocketManager {
  connect(token: string): Promise<void>
  on<T>(event: WebSocketEventType, handler: (data: T) => void): string
  emit(event: WebSocketEventType, data: unknown): void
}
```

## 🛠️ Advanced Features

### Type Guards

Built-in type checking functions:

```typescript
import { isDefined, isApiError, isPaginatedResponse } from '@/types'

// Check if value exists
if (isDefined(user)) {
  // user is guaranteed to be non-null/undefined
  console.log(user.email)
}

// Check API error type
if (isApiError(error)) {
  // error is typed as ApiErrorResponse
  console.log(error.status_code)
}
```

### Utility Functions

Type-safe helper functions:

```typescript
import { createEventHandler, createQueryBuilder, createMetadata } from '@/types'

// Type-safe event handlers
const handler = createEventHandler('patient_updated', (data) => {
  // data is automatically typed based on event type
  console.log(data.patient.name)
})

// Query builder
const query = createQueryBuilder<PatientQueryParams>()
  .with('status', 'active')
  .with('page', 1)
  .build({ size: 20 })

// Metadata creation
const metadata = createMetadata({
  source: 'webapp',
  version: '2.0.0'
})
```

### Branded Types

Prevent ID confusion with branded types:

```typescript
import { PatientId, UserId, createPatientId } from '@/types'

// These prevent accidental ID mix-ups
const patientId: PatientId = createPatientId('patient-123')
const userId: UserId = createUserId('user-456')

// This would cause a TypeScript error
// function getPatient(id: PatientId) { ... }
// getPatient(userId) // Error: UserId is not assignable to PatientId
```

### Conditional Types

Advanced type operations:

```typescript
// Extract event data type from event type
type EventData = ExtractEventData<WebSocketEventType.PATIENT_UPDATED>
// EventData is now PatientEventData

// Create typed WebSocket messages
type TypedMessage = TypedWebSocketMessage<WebSocketEventType.MESSAGE_SENT>
// TypedMessage has properly typed data property

// Entity API methods
type PatientAPI = EntityApiMethods<Patient>
// PatientAPI has list, get, create, update, delete methods
```

## 🔄 Migration Guide

### Step 1: Update Imports

**Before:**
```typescript
import { User } from '@/hooks/auth/types'
import { Patient } from '@/lib/types/api'
import { WebSocketEventType } from '@/lib/types/websocket'
```

**After:**
```typescript
import type { User, Patient, WebSocketEventType } from '@/types'
```

### Step 2: Use New Type Features

**Before:**
```typescript
interface Props {
  user: User | null
  loading: boolean
  error: any
}
```

**After:**
```typescript
import type { User, BaseComponentProps, StateProps } from '@/types'

interface Props extends BaseComponentProps, StateProps {
  readonly user: User | null
}
```

### Step 3: Leverage Type Safety

**Before:**
```typescript
const handleError = (error: any) => {
  if (error.status) {
    // No type safety
  }
}
```

**After:**
```typescript
import { isApiError } from '@/types'

const handleError = (error: unknown) => {
  if (isApiError(error)) {
    // error is properly typed as ApiErrorResponse
    console.log(error.status_code, error.message)
  }
}
```

## 📋 Best Practices

### 1. Use Readonly Properties

```typescript
// ✅ Good: Immutable by design
interface User {
  readonly id: string
  readonly email: string
}

// ❌ Avoid: Mutable properties
interface User {
  id: string
  email: string
}
```

### 2. Prefer Type Imports

```typescript
// ✅ Good: Type-only imports
import type { User, Patient } from '@/types'

// ❌ Avoid: Value imports for types
import { User, Patient } from '@/types'
```

### 3. Use Specific Types

```typescript
// ✅ Good: Specific return type
const getPatients = (): Promise<PaginatedResponse<Patient>> => {
  return apiClient.patients.list()
}

// ❌ Avoid: Generic any type
const getPatients = (): Promise<any> => {
  return apiClient.patients.list()
}
```

### 4. Leverage Union Types

```typescript
// ✅ Good: Discriminated unions
type ApiResult<T> = 
  | { success: true; data: T }
  | { success: false; error: string }

// ❌ Avoid: Ambiguous types
interface ApiResult<T> {
  success: boolean
  data?: T
  error?: string
}
```

### 5. Document Complex Types

```typescript
/**
 * Represents a patient's flow state with comprehensive tracking
 * @example
 * ```typescript
 * const flow: FlowState = {
 *   id: 'flow-123',
 *   patient_id: 'patient-456',
 *   flow_type: FlowType.INITIAL_15_DAYS,
 *   current_day: 5
 * }
 * ```
 */
interface FlowState extends BaseEntity {
  readonly patient_id: string
  readonly flow_type: FlowType
  readonly current_day: number
  readonly is_paused: boolean
}
```

## 🐛 Common Issues & Solutions

### Issue: "Cannot find module '@/types'"

**Solution:** Update your TypeScript path mapping in `tsconfig.json`:

```json
{
  "compilerOptions": {
    "paths": {
      "@/types": ["./types"],
      "@/types/*": ["./types/*"]
    }
  }
}
```

### Issue: "Type 'X' is not assignable to type 'Y'"

**Solution:** Check if you're mixing legacy and new types:

```typescript
// ❌ Mixing types
import { User } from '@/hooks/auth/types' // Legacy
import type { Patient } from '@/types' // New

// ✅ Consistent imports
import type { User, Patient } from '@/types'
```

### Issue: Circular dependency errors

**Solution:** Use the index file for cross-module type references:

```typescript
// ❌ Direct import causing circular dependency
import type { User } from './auth'

// ✅ Import from index
import type { User } from './index'
```

## 🎯 Performance Considerations

### 1. Type-Only Imports

Always use `import type` for type-only imports to reduce bundle size:

```typescript
// ✅ Type-only import (no runtime cost)
import type { User } from '@/types'

// ❌ Value import (includes in bundle)
import { User } from '@/types'
```

### 2. Lazy Type Loading

For large applications, consider lazy type loading:

```typescript
// Lazy load complex types
type LazyComplexType = import('@/types/complex').ComplexType
```

### 3. Avoid Deep Nesting

Keep type hierarchies shallow for better compilation performance:

```typescript
// ✅ Good: Flat structure
interface PatientSummary {
  readonly basic_info: PatientBasicInfo
  readonly medical_info: PatientMedicalInfo
}

// ❌ Avoid: Deep nesting
interface Patient {
  readonly info: {
    readonly basic: {
      readonly personal: {
        readonly name: string
      }
    }
  }
}
```

## 📚 Additional Resources

- [TypeScript Handbook](https://www.typescriptlang.org/docs/)
- [Advanced TypeScript Patterns](https://github.com/microsoft/TypeScript/wiki/Advanced-Types)
- [Type-Level Programming](https://type-level-typescript.com/)
- [Branded Types in TypeScript](https://egghead.io/blog/using-branded-types-in-typescript)

---

**Note**: This type system is designed to evolve with the application. Regular reviews and updates ensure it continues to provide maximum value to the development team.