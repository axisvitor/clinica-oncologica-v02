# Design Document

## Overview

This design document outlines the systematic approach to resolving all remaining TypeScript errors in the frontend-hormonia application. The solution employs a phased approach targeting high-priority build blockers first, followed by medium and low-priority issues. The design emphasizes type safety, maintainability, and consistency across the codebase while leveraging TypeScript's strict mode configuration.

## Architecture

### Current State Analysis

The frontend application uses:
- **TypeScript 5.9.3** with strict mode enabled
- **React 19.0.0** with TypeScript JSX support
- **Strict compiler options**: `noImplicitAny`, `exactOptionalPropertyTypes`, `noUncheckedIndexedAccess`
- **Path aliases**: `@/*` for src directory imports
- **Centralized type definitions**: `@/types/api.ts` and `@/types/shared.ts`

Current error distribution:
- **High Priority**: ~23 errors (build blockers)
- **Medium Priority**: ~44 errors (implicit any in components)
- **Low Priority**: ~73-83 errors (flow engine, mocks, utilities)

### Design Principles

1. **Type-First Approach**: Fix type definitions at the source before fixing consumers
2. **Incremental Resolution**: Address errors in priority order to unblock builds quickly
3. **Consistency Over Duplication**: Use centralized type definitions from `@/types/api`
4. **Explicit Over Implicit**: Prefer explicit type annotations for public APIs
5. **Validation-Driven**: Ensure `npm run typecheck` passes after each phase

## Components and Interfaces

### Phase 1: High Priority Fixes (Build Blockers)

#### Component 1.1: QuizLinkStatus Type Correction

**Problem**: `useMonthlyQuizStatus` hook returns array but consumers expect object

**Solution**:
```typescript
// File: src/hooks/useMonthlyQuizStatus.ts

export interface QuizLinkStatus {
  patient_id: string
  quiz_id: string
  status: QuizSessionStatus
  link_url?: string
  expires_at?: string
  created_at: string
}

// Change return type from QuizLinkStatus[] to QuizLinkStatus | null
export function useMonthlyQuizStatus(patientId: string): {
  quizStatus: QuizLinkStatus | null
  isLoading: boolean
  error: Error | null
  refetch: () => void
}
```

**Impact**: Fixes ~18 errors in PatientDetailPage.tsx

#### Component 1.2: Report Filter Type Annotations

**Problem**: Implicit any in filter callback parameters

**Solution**:
```typescript
// File: src/pages/ReportsPage.tsx

import type { Report } from '@/types/api'

// Add explicit type to filter parameters
const completedReports = reports.filter((r: Report) => r.status === 'completed')
const pendingReports = reports.filter((r: Report) => r.status === 'pending')
const failedReports = reports.filter((r: Report) => r.status === 'failed')
```

**Impact**: Fixes 3 errors in ReportsPage.tsx

#### Component 1.3: AdminLoginForm Props Interface

**Problem**: Missing `onLogin` prop in AdminLoginForm component usage

**Solution**:
```typescript
// File: src/components/admin/AdminLoginForm.tsx

export interface AdminLoginFormProps {
  onLogin: (credentials: LoginCredentials) => Promise<void>
  isLoading?: boolean
  error?: string | null
}

export function AdminLoginForm({ onLogin, isLoading, error }: AdminLoginFormProps) {
  // Implementation
}

// File: src/routes/AdminRoutes.lazy.tsx
<AdminLoginForm onLogin={handleAdminLogin} />
```

**Impact**: Fixes 1 error in AdminRoutes.lazy.tsx

#### Component 1.4: MedicoAuth State Property

**Problem**: `useMedicoAuth()` return type doesn't include `state` property

**Solution**:
```typescript
// File: src/contexts/MedicoAuthContext.tsx

export interface MedicoAuthState {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  error: Error | null
}

export interface MedicoAuthContextValue extends MedicoAuthState {
  login: (credentials: LoginCredentials) => Promise<void>
  logout: () => Promise<void>
  refreshToken: () => Promise<void>
}

// File: src/routes/MedicoRoutes.tsx
const { user, isAuthenticated, isLoading } = useMedicoAuth()
// Instead of: const { state } = useMedicoAuth()
```

**Impact**: Fixes 1 error in MedicoRoutes.tsx

### Phase 2: Medium Priority Fixes (Component Type Safety)

#### Component 2.1: UserAdminDashboard Type Annotations

**Problem**: Implicit any in callback parameters and event handlers

**Solution**:
```typescript
// File: src/components/admin/UserAdminDashboard.tsx

import type { User } from '@/types/api'

interface ActivityLog {
  id: string
  user_id: string
  action: string
  timestamp: string
  metadata?: Record<string, any>
}

// Add explicit types to all parameters
const handleUserUpdate = (user: User) => { /* ... */ }
const handleActivityFilter = (activity: ActivityLog) => { /* ... */ }
const renderUserRow = (user: User, index: number) => { /* ... */ }
```

**Impact**: Fixes 7 errors in UserAdminDashboard.tsx

#### Component 2.2: AI Component Type Definitions

**Problem**: Missing type annotations in AIChatInterface and AIAnalyticsDashboard

**Solution**:
```typescript
// File: src/components/ai/AIChatInterface.tsx

import type { AIChatMessage, ChatSession } from '@/types/api'

interface AIChatInterfaceProps {
  sessionId: string
  onMessageSend: (message: string) => Promise<void>
  onSessionUpdate: (session: ChatSession) => void
}

interface MessageInputProps {
  value: string
  onChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void
  onSubmit: (e: React.FormEvent<HTMLFormElement>) => void
  disabled?: boolean
}

// File: src/components/ai/AIAnalyticsDashboard.tsx

interface AnalyticsData {
  insights: AIInsight[]
  metrics: Record<string, number>
  trends: Array<{ date: string; value: number }>
}

const processAnalytics = (data: AnalyticsData): ProcessedAnalytics => { /* ... */ }
```

**Impact**: Fixes 12 errors across AI components

#### Component 2.3: Monthly Quiz Hooks Type Consistency

**Problem**: Return types don't match expected interfaces in consuming components

**Solution**:
```typescript
// File: src/hooks/useMonthlyQuiz.ts

export interface QuizHistory {
  session_id: string
  quiz_template_id: string
  completed_at: string
  score: number
  responses: Record<string, any>
}

export interface UseMonthlyQuizReturn {
  currentQuiz: QuizSession | null
  quizHistory: QuizHistory[]
  isLoading: boolean
  error: Error | null
  startQuiz: (templateId: string) => Promise<void>
  submitAnswer: (questionId: string, answer: string) => Promise<void>
  completeQuiz: () => Promise<void>
}

export function useMonthlyQuiz(patientId: string): UseMonthlyQuizReturn {
  // Implementation with explicit return type
}
```

**Impact**: Fixes 25 errors across quiz-related hooks

### Phase 3: Low Priority Fixes (Internal Systems)

#### Component 3.1: Flow Engine Type Definitions

**Problem**: Missing or incomplete type definitions in flow engine internals

**Solution**:
```typescript
// File: src/lib/flow-engine/types.ts

export interface FlowNode {
  id: string
  type: 'message' | 'condition' | 'action' | 'delay'
  config: FlowNodeConfig
  next?: string | string[]
}

export interface FlowNodeConfig {
  [key: string]: unknown
}

export interface FlowExecutionContext {
  patient_id: string
  flow_id: string
  current_node: string
  variables: Record<string, any>
  history: FlowExecutionStep[]
}

export interface FlowExecutionStep {
  node_id: string
  executed_at: string
  result: 'success' | 'failure' | 'skipped'
  metadata?: Record<string, any>
}

// File: src/lib/flow-engine/executor.ts
export class FlowExecutor {
  execute(context: FlowExecutionContext, node: FlowNode): Promise<FlowExecutionStep> {
    // Implementation
  }
}
```

**Impact**: Fixes 13 errors in flow engine files

#### Component 3.2: Mock Handler Type Safety

**Problem**: Implicit any in mock data structures

**Solution**:
```typescript
// File: src/lib/mock-handlers.ts

import type { Patient, Message, Report } from '@/types/api'

export const mockPatients: Patient[] = [
  {
    id: '1',
    name: 'Test Patient',
    email: 'test@example.com',
    status: 'active',
    created_at: new Date().toISOString()
  }
]

export const mockMessages: Message[] = [
  // Typed mock data
]

export function createMockPatient(overrides?: Partial<Patient>): Patient {
  return {
    id: crypto.randomUUID(),
    name: 'Mock Patient',
    status: 'active',
    created_at: new Date().toISOString(),
    ...overrides
  }
}
```

**Impact**: Fixes 1-2 errors in mock files

## Data Models

### Core Type Hierarchy

```
@/types/api.ts (Source of Truth)
├── Entity Types
│   ├── Patient
│   ├── Message
│   ├── Flow
│   ├── Alert
│   ├── Report
│   ├── QuizTemplate
│   └── QuizSession
├── Enum Types
│   ├── PatientStatus
│   ├── MessageDirection
│   ├── MessageType
│   ├── MessageStatus
│   ├── AlertType
│   ├── ReportType
│   ├── ReportStatus
│   ├── QuestionType
│   ├── ScoringMethod
│   └── QuizSessionStatus
├── Request/Response Types
│   ├── CreatePatientRequest
│   ├── UpdatePatientRequest
│   ├── SendMessageRequest
│   ├── GenerateReportRequest
│   └── QueryParams interfaces
└── Utility Types
    ├── TimelineEvent
    ├── PatientTimeline
    ├── CursorPage<T>
    └── ApiClient interface
```

### Type Import Strategy

All components and hooks should import types from centralized locations:

```typescript
// ✅ Correct
import type { Patient, Message, Report } from '@/types/api'
import type { Priority } from '@/types/shared'

// ❌ Incorrect
import type { Patient } from '../../types/api'
import type { Patient } from '../lib/types'
```

## Error Handling

### Type Error Categories

1. **Implicit Any Errors**: Add explicit type annotations
2. **Type Mismatch Errors**: Align types between producer and consumer
3. **Missing Property Errors**: Add optional properties or update interfaces
4. **Union Type Errors**: Use type guards or discriminated unions
5. **Generic Type Errors**: Add proper type constraints

### Error Resolution Pattern

```typescript
// Step 1: Identify the error source
// Error: Parameter 'user' implicitly has an 'any' type

// Step 2: Find the correct type definition
import type { User } from '@/types/api'

// Step 3: Apply explicit type annotation
const handleUser = (user: User) => {
  // Now type-safe
}

// Step 4: Verify with typecheck
// npm run typecheck
```

## Testing Strategy

### Type Testing Approach

1. **Compilation Tests**: Ensure `npm run typecheck` passes
2. **IDE Validation**: Verify IntelliSense shows correct types
3. **Runtime Tests**: Existing unit tests should continue passing
4. **Integration Tests**: E2E tests validate type-safe data flow

### Validation Commands

```bash
# Phase 1 validation
cd frontend-hormonia
npm run typecheck

# Full validation
cd ..
.\scripts\validate-release.ps1

# Continuous validation during development
npm run typecheck -- --watch
```

### Type Coverage Metrics

Track progress using error counts:

```
Initial:  196 errors in 46 files
Current:  ~140-150 errors in ~40 files (25% reduction)
Phase 1:  ~117-127 errors (23 errors fixed)
Phase 2:  ~73-83 errors (44 errors fixed)
Phase 3:  0 errors (100% type safety achieved)
```

## Implementation Phases

### Phase 1: High Priority (Estimated: 2-3 hours)
- Fix QuizLinkStatus return type
- Add Report filter type annotations
- Add AdminLoginForm onLogin prop
- Fix MedicoAuth state property access
- **Validation**: `npm run typecheck` shows ~117-127 errors

### Phase 2: Medium Priority (Estimated: 3-4 hours)
- Add types to UserAdminDashboard callbacks
- Type AI component handlers and props
- Align monthly quiz hook return types
- **Validation**: `npm run typecheck` shows ~73-83 errors

### Phase 3: Low Priority (Estimated: 2-3 hours)
- Complete flow engine type definitions
- Type mock handlers and test utilities
- **Validation**: `npm run typecheck` passes with 0 errors

### Phase 4: Documentation and Validation (Estimated: 1-2 hours)
- Add JSDoc comments to complex types
- Update type documentation
- Run full validation suite
- **Validation**: All CI/CD checks pass

## Performance Considerations

### TypeScript Compiler Performance

- **Current**: Type checking completes in ~15-20 seconds
- **Target**: Maintain or improve to <30 seconds after all fixes
- **Strategy**: Use `skipLibCheck: true` for node_modules

### Build Performance

- **Impact**: Type fixes should not affect runtime bundle size
- **Monitoring**: Track build times before and after changes
- **Optimization**: Ensure no circular dependencies introduced

## Security Considerations

### Type Safety as Security

- Strict typing prevents runtime type errors
- `exactOptionalPropertyTypes` prevents undefined/null confusion
- `noUncheckedIndexedAccess` prevents array out-of-bounds errors

### Sensitive Data Handling

- Ensure PHI (Protected Health Information) types are properly marked
- Use type guards for user input validation
- Maintain type safety in authentication flows

## Migration Strategy

### Backward Compatibility

- All type fixes maintain existing runtime behavior
- No breaking changes to component APIs
- Existing tests continue to pass

### Rollout Plan

1. Create feature branch: `fix/typescript-errors-resolution`
2. Implement Phase 1 fixes and validate
3. Implement Phase 2 fixes and validate
4. Implement Phase 3 fixes and validate
5. Run full test suite (unit + E2E)
6. Create PR with detailed change summary
7. Merge after review and CI passes

## Monitoring and Maintenance

### Continuous Type Safety

- Enable TypeScript checking in CI/CD pipeline
- Add pre-commit hook for type checking
- Monitor type error trends in code reviews

### Type Definition Updates

- Keep `@/types/api.ts` synchronized with backend API
- Document breaking changes in type definitions
- Version type definitions alongside API versions

### Developer Experience

- Provide clear error messages in type definitions
- Add JSDoc examples for complex types
- Maintain type definition documentation
