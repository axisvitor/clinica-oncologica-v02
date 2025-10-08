# Quiz Error Handling & Testing Architecture Analysis

**Project:** quiz-mensal-interface
**Date:** October 7, 2025
**Reviewer:** System Architecture Designer
**Scope:** Error handling patterns, testing infrastructure, and resilience mechanisms

---

## Executive Summary

This document provides a deep-dive analysis of error handling and testing architecture for the quiz-mensal-interface application. The analysis reveals a **mature error handling strategy** with global error boundaries, API retry logic, and user-friendly fallbacks, but **critical gaps in test coverage** and error monitoring.

### Overall Scores

| Category | Score | Status |
|----------|-------|--------|
| Error Boundary Implementation | 9/10 | ✅ Excellent |
| API Error Handling | 9/10 | ✅ Excellent |
| User Error Feedback | 8.5/10 | ✅ Very Good |
| Test Coverage | 6/10 | ⚠️ Needs Improvement |
| Error Monitoring | 3/10 | ❌ Critical Gap |
| Overall Resilience | 7.5/10 | ✅ Good |

---

## 1. Error Boundary Architecture

### 1.1 Global Error Boundary

**Location:** `components/error/ErrorBoundary.tsx`
**Implementation Quality:** ✅ Excellent

```typescript
export class ErrorBoundary extends Component<ErrorBoundaryProps, State> {
  // Uses getDerivedStateFromError for immediate state update
  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error }
  }

  // Comprehensive error logging
  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error('Error Boundary caught an error:', {
      error,
      errorInfo,
      componentStack: errorInfo.componentStack,
      timestamp: new Date().toISOString(),
    })

    // Custom error handler hook
    this.props.onError?.(error, errorInfo)
  }
}
```

**Strengths:**
1. ✅ Follows React best practices (getDerivedStateFromError + componentDidCatch)
2. ✅ Comprehensive error context logging (timestamp, componentStack)
3. ✅ Custom error handler support via onError prop
4. ✅ Graceful fallback UI with ErrorFallback component
5. ✅ Reset functionality with page reload

**Weaknesses:**
1. ❌ TODO comment for Sentry integration not implemented
2. ⚠️ Page reload on reset might lose unsaved quiz progress
3. ⚠️ No error categorization (network, validation, system)

### 1.2 Error Fallback UI

**Location:** `components/error/ErrorFallback.tsx`
**Implementation Quality:** ✅ Excellent

**Features:**
- ✅ Development vs Production modes (shows stack trace only in dev)
- ✅ Inline styles (survives CSS loading errors)
- ✅ User-friendly error messages in Portuguese
- ✅ Two action buttons: "Tentar novamente" and "Ir para início"
- ✅ Support contact information
- ✅ Accessible UI with proper semantic HTML

**Critical Issue - Page Reload Impact:**
```typescript
const handleReset = (): void => {
  this.setState({ hasError: false, error: null, errorInfo: null })
  window.location.reload() // ⚠️ Loses quiz state!
}
```

**Recommendation:** Implement state persistence before reload:
```typescript
const handleReset = (): void => {
  // Save current quiz progress to localStorage
  const quizState = {
    questionIndex: this.props.currentQuestionIndex,
    answers: Array.from(this.props.answers.entries()),
    timestamp: Date.now()
  }
  localStorage.setItem('quiz-recovery', JSON.stringify(quizState))

  this.setState({ hasError: false, error: null, errorInfo: null })
  window.location.reload()
}
```

### 1.3 Error Boundary Integration

**Location:** `app/layout.tsx`

```typescript
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pt-BR">
      <body className={`font-sans ${GeistSans.variable} ${GeistMono.variable}`}>
        <ErrorBoundary>
          {children}
          <Toaster />
          <Analytics />
        </ErrorBoundary>
      </body>
    </html>
  )
}
```

**Analysis:**
- ✅ Correct placement at root layout level
- ✅ Wraps all children, Toaster, and Analytics
- ✅ Catches errors from entire component tree
- ⚠️ No granular error boundaries for specific features

**Recommendation:** Add feature-level error boundaries:
```typescript
// In QuizContainer
<ErrorBoundary
  fallback={<QuizErrorFallback onRestart={handleRestart} />}
  onError={(error) => {
    // Send to analytics
    trackError('quiz-error', { error, context: 'quiz-flow' })
  }}
>
  <QuizContent />
</ErrorBoundary>
```

---

## 2. API Error Handling Architecture

### 2.1 Custom Error Class

**Location:** `lib/api.ts`

```typescript
class QuizAPIError extends Error {
  status?: number
  code?: string
  retryable: boolean

  constructor(message: string, status?: number, retryable: boolean = false) {
    super(message)
    this.name = "QuizAPIError"
    this.status = status
    this.retryable = retryable
  }
}
```

**Strengths:**
1. ✅ Custom error type with HTTP status
2. ✅ Retryable flag for smart retry logic
3. ✅ Error code support (not currently used)
4. ✅ Extends native Error class

**Enhancement Opportunity:**
```typescript
class QuizAPIError extends Error {
  status?: number
  code?: string
  retryable: boolean
  category: 'network' | 'validation' | 'auth' | 'server' | 'client' // ADD THIS
  userMessage: string // ADD THIS - friendly message for users

  constructor(
    message: string,
    status?: number,
    retryable: boolean = false,
    category?: 'network' | 'validation' | 'auth' | 'server' | 'client'
  ) {
    super(message)
    this.name = "QuizAPIError"
    this.status = status
    this.retryable = retryable
    this.category = category || this.categorizeError(status)
    this.userMessage = this.generateUserMessage()
  }

  private categorizeError(status?: number): string {
    if (!status) return 'network'
    if (status >= 500) return 'server'
    if (status === 401 || status === 403) return 'auth'
    if (status >= 400 && status < 500) return 'validation'
    return 'client'
  }

  private generateUserMessage(): string {
    switch (this.category) {
      case 'network': return 'Erro de conexão. Verifique sua internet.'
      case 'auth': return 'Sessão expirada. Solicite um novo link.'
      case 'validation': return 'Por favor, verifique suas respostas.'
      case 'server': return 'Erro no servidor. Tente novamente.'
      default: return 'Erro inesperado. Tente novamente.'
    }
  }
}
```

### 2.2 Timeout Handling

**Implementation Quality:** ✅ Excellent

```typescript
async function fetchWithTimeout(
  url: string,
  options: RequestInit = {},
  timeout: number = DEFAULT_TIMEOUT
): Promise<Response> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeout)

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal
    })
    clearTimeout(timeoutId)
    return response
  } catch (error) {
    clearTimeout(timeoutId)
    if (error instanceof Error && error.name === 'AbortError') {
      throw new QuizAPIError('Request timeout - please check your connection', 408, true)
    }
    throw error
  }
}
```

**Strengths:**
1. ✅ Uses AbortController (modern approach)
2. ✅ Proper cleanup with clearTimeout
3. ✅ 408 status code for timeout errors
4. ✅ Timeout errors marked as retryable
5. ✅ Configurable timeout via DEFAULT_TIMEOUT (30s)

### 2.3 Retry Logic with Exponential Backoff

**Implementation Quality:** ✅ Excellent

```typescript
async function withRetry<T>(
  fn: () => Promise<T>,
  retries: number = DEFAULT_RETRY_ATTEMPTS,
  delay: number = 1000
): Promise<T> {
  let lastError: Error | null = null

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      return await fn()
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error))

      // Don't retry if error is not retryable
      if (error instanceof QuizAPIError && !error.retryable) {
        throw error
      }

      // Don't retry on last attempt
      if (attempt === retries) {
        break
      }

      // Exponential backoff: 1s, 2s, 4s
      await new Promise(resolve => setTimeout(resolve, delay * Math.pow(2, attempt)))
    }
  }

  throw lastError || new QuizAPIError('Maximum retry attempts reached')
}
```

**Analysis:**

| Feature | Implementation | Quality |
|---------|---------------|---------|
| Retry Attempts | 3 (configurable) | ✅ Good |
| Backoff Strategy | Exponential (1s → 2s → 4s) | ✅ Excellent |
| Retryable Check | Based on error.retryable flag | ✅ Smart |
| Debug Logging | Conditional via DEBUG_MODE | ✅ Good |
| Max Delay | 4 seconds (2^2 * 1s) | ✅ Reasonable |

**Strengths:**
1. ✅ Exponential backoff prevents server overload
2. ✅ Smart retry decisions (only retry network/server errors)
3. ✅ Configurable retry count and delay
4. ✅ Type-safe generic implementation
5. ✅ Proper error propagation

**Enhancement Opportunity - Jitter:**
```typescript
// Add random jitter to prevent thundering herd
await new Promise(resolve =>
  setTimeout(
    resolve,
    (delay * Math.pow(2, attempt)) + Math.random() * 1000
  )
)
```

### 2.4 API Error Response Handling

**accessQuiz() Error Handling:**
```typescript
if (!response.ok) {
  const error = await response.json().catch(() => ({ detail: "Failed to access quiz" }))

  // Determine if error is retryable
  const retryable = response.status >= 500 || response.status === 408

  throw new QuizAPIError(
    error.detail || `HTTP ${response.status}: ${response.statusText}`,
    response.status,
    retryable
  )
}
```

**Strengths:**
1. ✅ Fallback error message if JSON parsing fails
2. ✅ Smart retryable determination (5xx + 408)
3. ✅ Includes HTTP status and statusText
4. ✅ Server error message prioritized (error.detail)

**Weaknesses:**
1. ⚠️ 4xx errors (except 408) are never retried (might miss transient issues)
2. ⚠️ No specific handling for 401 (token expired) vs 403 (forbidden)
3. ⚠️ No rate limiting detection (429 status code)

**Enhancement:**
```typescript
if (!response.ok) {
  const error = await response.json().catch(() => ({ detail: "Failed to access quiz" }))

  // Enhanced retryable determination
  const retryable =
    response.status >= 500 || // Server errors
    response.status === 408 || // Timeout
    response.status === 429 || // Rate limit (should use Retry-After header)
    response.status === 503    // Service unavailable

  // Special handling for auth errors
  if (response.status === 401) {
    throw new QuizAPIError(
      'Token expirado. Solicite um novo link.',
      401,
      false, // Don't retry auth errors
      'auth'
    )
  }

  throw new QuizAPIError(
    error.detail || `HTTP ${response.status}: ${response.statusText}`,
    response.status,
    retryable
  )
}
```

---

## 3. User Feedback Architecture

### 3.1 Loading States

**Implementation:** `app/page.tsx` (lines 86-96)

```typescript
if (isLoading) {
  return (
    <main className="min-h-screen bg-gradient-to-br from-background via-muted/30 to-accent/20 flex items-center justify-center p-4">
      <Card className="p-8 text-center space-y-4">
        <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto" />
        <p className="text-lg text-muted-foreground">Carregando questionário...</p>
      </Card>
    </main>
  )
}
```

**Quality:** ✅ Excellent
- Centered layout with gradient background
- Animated spinner (CSS animation)
- User-friendly Portuguese message
- Accessible Card component from shadcn/ui

### 3.2 Error States

**Implementation:** `app/page.tsx` (lines 98-126)

```typescript
if (error) {
  return (
    <main className="min-h-screen bg-gradient-to-br from-background via-muted/30 to-accent/20 flex items-center justify-center p-4">
      <Card className="p-8 max-w-md w-full space-y-6">
        <div className="text-center space-y-4">
          <AlertCircle className="w-16 h-16 text-destructive mx-auto" />
          <h2 className="text-2xl font-bold">Ops! Algo deu errado</h2>
          <p className="text-muted-foreground">{error.detail}</p>
        </div>

        {error.status !== 401 && (
          <Button onClick={initializeQuiz} className="w-full" size="lg">
            <RefreshCcw className="w-5 h-5 mr-2" />
            Tentar Novamente
          </Button>
        )}

        <div className="text-center text-sm text-muted-foreground">
          <p>Precisa de ajuda? Entre em contato com nossa equipe.</p>
        </div>
      </Card>
    </main>
  )
}
```

**Strengths:**
1. ✅ Conditional retry button (hidden for 401 errors)
2. ✅ Clear error icon (AlertCircle from lucide-react)
3. ✅ Server error message displayed (error.detail)
4. ✅ Support contact information
5. ✅ User-friendly layout

**Weaknesses:**
1. ⚠️ Generic error message for all error types
2. ⚠️ No error categorization (network, server, validation)
3. ⚠️ No suggestion of specific actions based on error type

**Enhancement:**
```typescript
const getErrorGuidance = (error: QuizError) => {
  if (error.status === 401) {
    return {
      title: 'Link Expirado',
      message: 'Este link de acesso expirou. Por favor, solicite um novo link ao seu médico.',
      icon: 'clock',
      actions: null
    }
  }

  if (error.status === 404) {
    return {
      title: 'Quiz Não Encontrado',
      message: 'Este questionário não foi encontrado. Verifique se o link está correto.',
      icon: 'search',
      actions: ['contactSupport']
    }
  }

  if (error.status && error.status >= 500) {
    return {
      title: 'Erro no Servidor',
      message: 'Nossos servidores estão temporariamente indisponíveis. Tente novamente em alguns minutos.',
      icon: 'server',
      actions: ['retry', 'contactSupport']
    }
  }

  // Network errors (no status)
  if (!error.status) {
    return {
      title: 'Erro de Conexão',
      message: 'Não foi possível conectar ao servidor. Verifique sua conexão com a internet.',
      icon: 'wifi-off',
      actions: ['retry', 'checkConnection']
    }
  }

  // Default
  return {
    title: 'Ops! Algo deu errado',
    message: error.detail || 'Erro inesperado. Tente novamente.',
    icon: 'alert-circle',
    actions: ['retry', 'contactSupport']
  }
}
```

### 3.3 Toast Notifications

**Implementation:** `hooks/quiz/useQuizNavigation.ts`

```typescript
const { toast } = useToast()

// Validation error
if (!validation.isValid) {
  toast({
    title: "Atenção",
    description: validation.error,
    variant: "destructive",
  })
  return
}

// Submit success
toast({
  title: "Resposta salva",
  description: "Sua resposta foi registrada com sucesso.",
})
```

**Quality:** ✅ Good
- Uses shadcn/ui toast component
- Descriptive titles and messages
- Variant support (destructive for errors)
- Non-blocking user experience

**Enhancement Opportunity:**
```typescript
// Add duration control
toast({
  title: "Resposta salva",
  description: "Sua resposta foi registrada com sucesso.",
  duration: 2000, // Auto-dismiss after 2s
})

// Add action buttons
toast({
  title: "Erro ao salvar",
  description: "Não foi possível salvar sua resposta.",
  variant: "destructive",
  action: {
    label: "Tentar Novamente",
    onClick: () => handleSubmitAnswer()
  },
  duration: Infinity // Don't auto-dismiss errors
})
```

---

## 4. Testing Infrastructure

### 4.1 Test Setup

**Location:** `tests/setup.ts`

```typescript
import '@testing-library/jest-dom';

// Mock console methods to reduce noise in tests
global.console = {
  ...console,
  error: jest.fn(),
  warn: jest.fn(),
  log: jest.fn(),
};

// Mock IntersectionObserver
global.IntersectionObserver = class IntersectionObserver {
  constructor() {}
  disconnect() {}
  observe() {}
  takeRecords() { return []; }
  unobserve() {}
} as any;

// Mock ResizeObserver
global.ResizeObserver = class ResizeObserver {
  constructor() {}
  disconnect() {}
  observe() {}
  unobserve() {}
} as any;

// Mock matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: jest.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: jest.fn(),
    removeListener: jest.fn(),
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    dispatchEvent: jest.fn(),
  })),
});
```

**Analysis:**

| Mock | Purpose | Quality |
|------|---------|---------|
| console.* | Reduce test noise | ✅ Good |
| IntersectionObserver | UI component support | ✅ Good |
| ResizeObserver | Responsive component support | ✅ Good |
| matchMedia | Media query testing | ✅ Good |

**Missing Mocks:**
- ❌ `fetch` (for API testing)
- ❌ `localStorage` (for token storage testing)
- ❌ `window.location` (for navigation testing)
- ❌ `URLSearchParams` (for token extraction testing)

**Enhanced Setup:**
```typescript
// Mock fetch
global.fetch = jest.fn()

// Mock localStorage
const localStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
}
global.localStorage = localStorageMock as any

// Mock window.location
delete (window as any).location
window.location = { href: '', reload: jest.fn() } as any

// Mock URLSearchParams
global.URLSearchParams = jest.fn().mockImplementation((params) => ({
  get: jest.fn((key) => params[key] || null),
})) as any
```

### 4.2 Test Coverage Analysis

**Jest Configuration:** `package.json` (lines 112-119)

```json
"coverageThreshold": {
  "global": {
    "branches": 75,
    "functions": 80,
    "lines": 80,
    "statements": 80
  }
}
```

**Current Test Files:**
1. `tests/quiz.test.tsx` - Basic quiz functionality
2. `tests/quiz-other-option.test.tsx` - "Outra" option handling
3. `tests/unit/quiz-interface.test.tsx` - Unit tests for main interface

**Coverage Gap Analysis:**

| Component/Module | Test File | Coverage Estimate | Priority |
|------------------|-----------|-------------------|----------|
| ErrorBoundary | ❌ None | 0% | 🔴 HIGH |
| ErrorFallback | ❌ None | 0% | 🔴 HIGH |
| lib/api.ts | ❌ None | 0% | 🔴 CRITICAL |
| useQuizState | ❌ None | 0% | 🔴 HIGH |
| useQuizNavigation | ❌ None | 0% | 🔴 HIGH |
| useQuizAnswer | ❌ None | 0% | 🔴 HIGH |
| QuizContainer | ⚠️ Partial | ~40% | 🟡 MEDIUM |
| QuestionRenderer | ⚠️ Partial | ~50% | 🟡 MEDIUM |
| app/page.tsx | ❌ None | 0% | 🔴 HIGH |

**Estimated Overall Coverage:** ~35-40% (based on test file count vs component count)

### 4.3 Missing Critical Tests

#### 4.3.1 Error Boundary Tests

**Priority:** 🔴 CRITICAL

**Required Tests:**
```typescript
// tests/unit/error-boundary.test.tsx
describe('ErrorBoundary', () => {
  it('should catch and display error when child throws', () => {
    const ThrowError = () => { throw new Error('Test error') }
    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    )
    expect(screen.getByText(/algo deu errado/i)).toBeInTheDocument()
  })

  it('should call onError handler when error occurs', () => {
    const onError = jest.fn()
    const ThrowError = () => { throw new Error('Test error') }
    render(
      <ErrorBoundary onError={onError}>
        <ThrowError />
      </ErrorBoundary>
    )
    expect(onError).toHaveBeenCalledWith(
      expect.any(Error),
      expect.objectContaining({ componentStack: expect.any(String) })
    )
  })

  it('should reset error state and reload page on reset', () => {
    const reloadSpy = jest.spyOn(window.location, 'reload')
    const ThrowError = () => { throw new Error('Test error') }
    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    )
    fireEvent.click(screen.getByText(/tentar novamente/i))
    expect(reloadSpy).toHaveBeenCalled()
  })

  it('should render custom fallback when provided', () => {
    const ThrowError = () => { throw new Error('Test error') }
    const CustomFallback = () => <div>Custom Error UI</div>
    render(
      <ErrorBoundary fallback={<CustomFallback />}>
        <ThrowError />
      </ErrorBoundary>
    )
    expect(screen.getByText('Custom Error UI')).toBeInTheDocument()
  })
})
```

#### 4.3.2 API Client Tests

**Priority:** 🔴 CRITICAL

**Required Tests:**
```typescript
// tests/unit/api.test.ts
describe('QuizAPI', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    global.fetch = jest.fn()
  })

  describe('accessQuiz', () => {
    it('should successfully access quiz with valid token', async () => {
      const mockSession = { quiz_session_id: '123', total_questions: 10 }
      ;(global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockSession
      })

      const result = await quizAPI.accessQuiz('valid-token')
      expect(result).toEqual(mockSession)
    })

    it('should retry on 500 error', async () => {
      ;(global.fetch as jest.Mock)
        .mockRejectedValueOnce(new Error('500 Server Error'))
        .mockRejectedValueOnce(new Error('500 Server Error'))
        .mockResolvedValueOnce({ ok: true, json: async () => ({}) })

      await quizAPI.accessQuiz('token')
      expect(global.fetch).toHaveBeenCalledTimes(3)
    })

    it('should not retry on 401 error', async () => {
      ;(global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: async () => ({ detail: 'Unauthorized' })
      })

      await expect(quizAPI.accessQuiz('invalid-token')).rejects.toThrow()
      expect(global.fetch).toHaveBeenCalledTimes(1)
    })

    it('should timeout after 30 seconds', async () => {
      ;(global.fetch as jest.Mock).mockImplementation(
        () => new Promise(resolve => setTimeout(resolve, 35000))
      )

      await expect(quizAPI.accessQuiz('token')).rejects.toThrow(/timeout/i)
    }, 35000)
  })

  describe('submitAnswer', () => {
    it('should handle token rotation', async () => {
      const mockResponse = {
        message: 'Success',
        new_token: 'rotated-token'
      }
      ;(global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse
      })

      const result = await quizAPI.submitAnswer('old-token', 'q1', 'answer')
      expect(result.new_token).toBe('rotated-token')
    })

    it('should send array answers without stringifying', async () => {
      ;(global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ message: 'Success' })
      })

      await quizAPI.submitAnswer('token', 'q1', ['option1', 'option2'])

      const callBody = JSON.parse(
        (global.fetch as jest.Mock).mock.calls[0][1].body
      )
      expect(Array.isArray(callBody.response_value)).toBe(true)
    })
  })
})
```

#### 4.3.3 Custom Hook Tests

**Priority:** 🔴 HIGH

**Required Tests:**
```typescript
// tests/unit/use-quiz-state.test.tsx
describe('useQuizState', () => {
  it('should initialize with correct default values', () => {
    const { result } = renderHook(() => useQuizState({
      session: mockSession,
      token: 'test-token'
    }))

    expect(result.current.currentQuestionIndex).toBe(0)
    expect(result.current.isCompleted).toBe(false)
    expect(result.current.progress).toBe(10) // 1/10 questions
  })

  it('should update token and sync to localStorage', () => {
    const onTokenUpdate = jest.fn()
    const { result } = renderHook(() => useQuizState({
      session: mockSession,
      token: 'old-token',
      onTokenUpdate
    }))

    act(() => {
      result.current.handleTokenUpdate('new-token')
    })

    expect(result.current.currentToken).toBe('new-token')
    expect(localStorage.setItem).toHaveBeenCalledWith('quiz_token', 'new-token')
    expect(onTokenUpdate).toHaveBeenCalledWith('new-token')
  })

  it('should calculate progress correctly', () => {
    const { result } = renderHook(() => useQuizState({
      session: mockSession,
      token: 'token'
    }))

    act(() => {
      result.current.setCurrentQuestionIndex(4) // Question 5 of 10
    })

    expect(result.current.progress).toBe(50)
  })
})

// tests/unit/use-quiz-navigation.test.tsx
describe('useQuizNavigation', () => {
  it('should validate answer before submission', async () => {
    const validateAnswer = jest.fn(() => ({
      isValid: false,
      error: 'Required'
    }))

    const { result } = renderHook(() => useQuizNavigation({
      ...defaultProps,
      validateAnswer
    }))

    await act(async () => {
      await result.current.handleSubmitAnswer()
    })

    expect(validateAnswer).toHaveBeenCalled()
    // Should not call API if validation fails
    expect(global.fetch).not.toHaveBeenCalled()
  })

  it('should call onComplete on last question', async () => {
    const onComplete = jest.fn()
    ;(global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ message: 'Success' })
    })

    const { result } = renderHook(() => useQuizNavigation({
      ...defaultProps,
      isLastQuestion: true,
      onComplete
    }))

    await act(async () => {
      await result.current.handleSubmitAnswer()
    })

    expect(onComplete).toHaveBeenCalled()
  })
})
```

---

## 5. Error Monitoring & Observability

### 5.1 Current State: Console Logging Only

**Analysis:** ❌ CRITICAL GAP

**Current Implementation:**
```typescript
// ErrorBoundary.tsx
componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
  console.error('Error Boundary caught an error:', {
    error,
    errorInfo,
    componentStack: errorInfo.componentStack,
    timestamp: new Date().toISOString(),
  })

  // TODO: Send to error tracking service (Sentry, LogRocket, etc.)
}
```

**Problems:**
1. ❌ Console logs are not persisted
2. ❌ No production error tracking
3. ❌ No error aggregation or analysis
4. ❌ No user session replay
5. ❌ No performance monitoring
6. ❌ No alerting on critical errors

### 5.2 Recommended: Sentry Integration

**Implementation Priority:** 🔴 CRITICAL

**Step 1: Install Sentry SDK**
```bash
npm install @sentry/nextjs
```

**Step 2: Initialize Sentry**
```typescript
// sentry.client.config.ts
import * as Sentry from "@sentry/nextjs";

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,

  // Performance Monitoring
  tracesSampleRate: 0.1, // 10% of transactions

  // Session Replay
  replaysSessionSampleRate: 0.1, // 10% of sessions
  replaysOnErrorSampleRate: 1.0, // 100% of sessions with errors

  // Environment
  environment: process.env.NEXT_PUBLIC_ENVIRONMENT || 'development',

  // Release tracking
  release: process.env.NEXT_PUBLIC_APP_VERSION,

  // Error filtering
  beforeSend(event, hint) {
    // Filter out known non-critical errors
    if (event.exception?.values?.[0]?.value?.includes('ResizeObserver')) {
      return null
    }
    return event
  },

  // Breadcrumbs configuration
  integrations: [
    new Sentry.BrowserTracing({
      tracePropagationTargets: ["localhost", /^https:\/\/api\.yourapp\.com/],
    }),
    new Sentry.Replay({
      maskAllText: true,
      blockAllMedia: true,
    }),
  ],
});
```

**Step 3: Integrate with ErrorBoundary**
```typescript
import * as Sentry from "@sentry/nextjs";

componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
  // Log to console (development)
  if (process.env.NODE_ENV === 'development') {
    console.error('Error Boundary caught an error:', {
      error,
      errorInfo,
      componentStack: errorInfo.componentStack,
      timestamp: new Date().toISOString(),
    })
  }

  // Send to Sentry (production)
  Sentry.captureException(error, {
    contexts: {
      react: {
        componentStack: errorInfo.componentStack,
      },
    },
    tags: {
      errorBoundary: 'global',
    },
  })

  // Call custom error handler
  this.props.onError?.(error, errorInfo)
}
```

**Step 4: API Error Tracking**
```typescript
// lib/api.ts
catch (error) {
  if (error instanceof QuizAPIError) {
    // Track API errors in Sentry
    Sentry.captureException(error, {
      tags: {
        errorType: 'api',
        endpoint: 'access-quiz',
        retryable: error.retryable,
      },
      extra: {
        status: error.status,
        token: token.substring(0, 10) + '...', // Partial token for debugging
      },
    })
    throw error
  }
  throw new QuizAPIError(...)
}
```

**Step 5: User Context**
```typescript
// After successful quiz access
Sentry.setUser({
  id: session.quiz_session_id,
  email: null, // Don't track PII
  username: session.patient_name,
})

Sentry.setContext("quiz", {
  sessionId: session.quiz_session_id,
  templateName: session.template_name,
  totalQuestions: session.total_questions,
  expiresAt: session.expires_at,
})
```

**Expected Benefits:**
1. ✅ Real-time error tracking
2. ✅ Stack traces with source maps
3. ✅ User session replay
4. ✅ Performance monitoring
5. ✅ Error aggregation and trends
6. ✅ Slack/email alerts on critical errors
7. ✅ Release tracking and regression detection

---

## 6. Resilience Patterns Summary

### 6.1 Implemented Patterns ✅

| Pattern | Location | Quality | Impact |
|---------|----------|---------|--------|
| Error Boundary | `components/error/` | 9/10 | High |
| Retry with Backoff | `lib/api.ts` | 9/10 | High |
| Timeout Handling | `lib/api.ts` | 9/10 | High |
| Graceful Degradation | `app/page.tsx` | 8/10 | Medium |
| User Feedback | Multiple | 8.5/10 | High |
| Loading States | `app/page.tsx` | 9/10 | Medium |

### 6.2 Missing Patterns ❌

| Pattern | Priority | Impact | Effort |
|---------|----------|--------|--------|
| Circuit Breaker | Medium | Medium | Low |
| Rate Limiting | Low | Low | Low |
| Offline Support | High | High | High |
| State Persistence | High | High | Medium |
| Error Recovery | High | High | Medium |

### 6.3 Recommended Implementations

#### 6.3.1 Circuit Breaker Pattern

**Purpose:** Prevent cascading failures by stopping requests to failing services

**Implementation:**
```typescript
// lib/circuit-breaker.ts
class CircuitBreaker {
  private failureCount = 0
  private lastFailureTime = 0
  private state: 'CLOSED' | 'OPEN' | 'HALF_OPEN' = 'CLOSED'

  private readonly threshold = 5 // failures before opening
  private readonly timeout = 60000 // 60s before half-open

  async execute<T>(fn: () => Promise<T>): Promise<T> {
    if (this.state === 'OPEN') {
      if (Date.now() - this.lastFailureTime < this.timeout) {
        throw new Error('Circuit breaker is OPEN')
      }
      this.state = 'HALF_OPEN'
    }

    try {
      const result = await fn()
      this.onSuccess()
      return result
    } catch (error) {
      this.onFailure()
      throw error
    }
  }

  private onSuccess() {
    this.failureCount = 0
    this.state = 'CLOSED'
  }

  private onFailure() {
    this.failureCount++
    this.lastFailureTime = Date.now()

    if (this.failureCount >= this.threshold) {
      this.state = 'OPEN'
    }
  }
}

// Usage in API client
const breaker = new CircuitBreaker()

async accessQuiz(token: string): Promise<QuizSession> {
  return breaker.execute(() =>
    withRetry(() => this._accessQuizInternal(token))
  )
}
```

#### 6.3.2 State Persistence for Error Recovery

**Purpose:** Preserve quiz progress across errors and page reloads

**Implementation:**
```typescript
// lib/quiz-persistence.ts
export class QuizPersistence {
  private static readonly STORAGE_KEY = 'quiz-state-backup'

  static save(state: {
    sessionId: string
    currentQuestionIndex: number
    answers: Map<string, any>
    token: string
    timestamp: number
  }) {
    try {
      const serialized = {
        ...state,
        answers: Array.from(state.answers.entries()),
        timestamp: Date.now(),
      }
      localStorage.setItem(this.STORAGE_KEY, JSON.stringify(serialized))
    } catch (error) {
      console.error('Failed to persist quiz state:', error)
    }
  }

  static restore(sessionId: string): typeof state | null {
    try {
      const stored = localStorage.getItem(this.STORAGE_KEY)
      if (!stored) return null

      const parsed = JSON.parse(stored)

      // Validate session ID matches
      if (parsed.sessionId !== sessionId) return null

      // Check if not too old (24 hours)
      if (Date.now() - parsed.timestamp > 86400000) {
        this.clear()
        return null
      }

      return {
        ...parsed,
        answers: new Map(parsed.answers),
      }
    } catch (error) {
      console.error('Failed to restore quiz state:', error)
      return null
    }
  }

  static clear() {
    localStorage.removeItem(this.STORAGE_KEY)
  }
}

// Usage in QuizContainer
useEffect(() => {
  // Auto-save state every 5 seconds
  const interval = setInterval(() => {
    QuizPersistence.save({
      sessionId: session.quiz_session_id,
      currentQuestionIndex,
      answers,
      token: currentToken,
      timestamp: Date.now(),
    })
  }, 5000)

  return () => clearInterval(interval)
}, [currentQuestionIndex, answers, currentToken])

// On mount, try to restore
useEffect(() => {
  const restored = QuizPersistence.restore(session.quiz_session_id)
  if (restored) {
    setCurrentQuestionIndex(restored.currentQuestionIndex)
    setAnswers(restored.answers)
    setCurrentToken(restored.token)

    toast({
      title: "Progresso Restaurado",
      description: "Continuando de onde você parou.",
    })
  }
}, [])
```

---

## 7. Recommendations & Action Plan

### 7.1 Critical Priorities (Week 1-2)

**Priority 1: Implement Error Monitoring 🔴**
- [ ] Install and configure Sentry
- [ ] Integrate with ErrorBoundary
- [ ] Add API error tracking
- [ ] Configure user context and breadcrumbs
- [ ] Set up alerting for critical errors

**Estimated Effort:** 8 hours
**Impact:** CRITICAL - Enables production error visibility

**Priority 2: Add Missing Tests 🔴**
- [ ] Write ErrorBoundary tests (8 tests)
- [ ] Write API client tests (12 tests)
- [ ] Write custom hook tests (15 tests)
- [ ] Run coverage report and identify gaps

**Estimated Effort:** 16 hours
**Impact:** HIGH - Increases coverage from ~40% to ~75%

**Priority 3: Implement State Persistence 🔴**
- [ ] Create QuizPersistence utility
- [ ] Auto-save quiz state every 5s
- [ ] Restore state on error recovery
- [ ] Add user notification on restore

**Estimated Effort:** 6 hours
**Impact:** HIGH - Prevents quiz progress loss

### 7.2 High Priorities (Week 3-4)

**Priority 4: Enhanced Error Categorization 🟡**
- [ ] Extend QuizAPIError with category field
- [ ] Add user-friendly error messages
- [ ] Implement context-specific error guidance
- [ ] Add error-specific action buttons

**Estimated Effort:** 8 hours
**Impact:** MEDIUM - Improved user experience

**Priority 5: Circuit Breaker Pattern 🟡**
- [ ] Implement CircuitBreaker class
- [ ] Integrate with API client
- [ ] Add status monitoring
- [ ] Configure thresholds

**Estimated Effort:** 6 hours
**Impact:** MEDIUM - Prevents cascading failures

### 7.3 Medium Priorities (Month 2)

**Priority 6: Offline Support 🟡**
- [ ] Implement service worker
- [ ] Cache quiz questions
- [ ] Queue answers for offline submission
- [ ] Add offline indicator UI

**Estimated Effort:** 20 hours
**Impact:** HIGH - Major UX improvement

**Priority 7: Enhanced Toast Notifications 🟡**
- [ ] Add duration control
- [ ] Add action buttons to toasts
- [ ] Implement toast queue
- [ ] Add accessibility features

**Estimated Effort:** 4 hours
**Impact:** LOW - Polish

### 7.4 Long-term Goals (Month 3+)

- [ ] Performance monitoring with Sentry
- [ ] User session replay
- [ ] A/B testing for error messaging
- [ ] Automated error report generation
- [ ] Error trend analysis dashboard

---

## 8. Testing Checklist

### 8.1 Error Boundary Testing ✅

- [ ] **Error Catching**
  - [ ] Catches synchronous errors
  - [ ] Catches asynchronous errors
  - [ ] Catches errors in event handlers
  - [ ] Catches errors in useEffect hooks

- [ ] **Fallback UI**
  - [ ] Displays error message
  - [ ] Shows stack trace in development
  - [ ] Hides stack trace in production
  - [ ] Shows reset button
  - [ ] Shows home button

- [ ] **Error Handler**
  - [ ] Calls onError callback
  - [ ] Passes correct error object
  - [ ] Passes errorInfo with componentStack

- [ ] **Reset Functionality**
  - [ ] Resets error state
  - [ ] Reloads page
  - [ ] Clears error from state

### 8.2 API Error Handling Testing ✅

- [ ] **Success Cases**
  - [ ] Successfully fetches quiz session
  - [ ] Successfully submits answer
  - [ ] Handles token rotation

- [ ] **Retry Logic**
  - [ ] Retries on 5xx errors
  - [ ] Retries on timeout (408)
  - [ ] Retries on network errors
  - [ ] Does not retry on 4xx errors (except 408)
  - [ ] Uses exponential backoff
  - [ ] Stops after max retries

- [ ] **Timeout Handling**
  - [ ] Aborts request after timeout
  - [ ] Throws timeout error
  - [ ] Marks timeout as retryable

- [ ] **Error Response Handling**
  - [ ] Parses error detail from response
  - [ ] Falls back to generic message
  - [ ] Includes HTTP status code
  - [ ] Includes statusText

### 8.3 User Feedback Testing ✅

- [ ] **Loading States**
  - [ ] Shows loading spinner
  - [ ] Displays loading message
  - [ ] Prevents user interaction

- [ ] **Error States**
  - [ ] Displays error message
  - [ ] Shows appropriate icon
  - [ ] Shows retry button (when applicable)
  - [ ] Hides retry for auth errors
  - [ ] Shows support contact info

- [ ] **Toast Notifications**
  - [ ] Shows success toast
  - [ ] Shows error toast
  - [ ] Shows warning toast
  - [ ] Auto-dismisses after duration
  - [ ] Can be manually dismissed

---

## 9. Metrics & KPIs

### 9.1 Error Metrics (Post-Sentry Integration)

**Target Metrics:**

| Metric | Target | Critical Threshold |
|--------|--------|-------------------|
| Error Rate | < 0.5% of sessions | > 2% |
| API Error Rate | < 1% of requests | > 5% |
| Average Response Time | < 2s | > 5s |
| Error Resolution Time | < 4 hours | > 24 hours |
| User-Reported Errors | < 5 per month | > 20 per month |

**Monitoring Frequency:** Real-time with daily aggregation

### 9.2 Test Coverage Metrics

**Current State:**
- Overall Coverage: ~40%
- Critical Paths: ~20%

**Target State:**
- Overall Coverage: 80%
- Critical Paths: 95%

**Coverage by Module:**

| Module | Current | Target | Priority |
|--------|---------|--------|----------|
| API Client | 0% | 95% | 🔴 CRITICAL |
| Error Boundaries | 0% | 90% | 🔴 CRITICAL |
| Custom Hooks | 0% | 85% | 🔴 HIGH |
| Components | 40% | 80% | 🟡 MEDIUM |
| Utils | 60% | 75% | 🟢 LOW |

### 9.3 Resilience Metrics

**Availability Targets:**
- Uptime: 99.5% (excluding planned maintenance)
- API Success Rate: 99%
- Quiz Completion Rate: 95%

**Performance Targets:**
- Time to Interactive: < 3s
- API Response Time (p95): < 2s
- Error Recovery Time: < 5s

---

## 10. Conclusion

### 10.1 Strengths Summary

1. **✅ Excellent Error Boundary Implementation**
   - Global error catching
   - User-friendly fallback UI
   - Development vs production modes

2. **✅ Robust API Error Handling**
   - Retry with exponential backoff
   - Timeout protection
   - Smart retryable error detection

3. **✅ Good User Feedback**
   - Loading states
   - Error states with context
   - Toast notifications

4. **✅ Solid Testing Infrastructure**
   - Jest + Testing Library setup
   - Proper mocks for browser APIs
   - Coverage thresholds configured

### 10.2 Critical Gaps

1. **❌ No Error Monitoring in Production**
   - TODO comment in ErrorBoundary for Sentry
   - No production error visibility
   - No alerting or error aggregation

2. **❌ Insufficient Test Coverage (~40%)**
   - No tests for API client
   - No tests for error boundaries
   - No tests for custom hooks
   - Missing critical path coverage

3. **❌ No State Persistence**
   - Page reload loses quiz progress
   - Error recovery resets user to beginning
   - No offline support

4. **❌ Limited Error Categorization**
   - Generic error messages
   - No context-specific guidance
   - Missing error recovery suggestions

### 10.3 Recommended Next Steps

**Immediate (This Week):**
1. Install and configure Sentry (8h)
2. Add API client tests (8h)
3. Implement state persistence (6h)

**Short-term (This Month):**
1. Add error boundary tests (4h)
2. Add custom hook tests (8h)
3. Enhanced error categorization (8h)
4. Circuit breaker pattern (6h)

**Medium-term (Next 3 Months):**
1. Offline support with service workers (20h)
2. Performance monitoring (8h)
3. User session replay (4h)
4. Error analytics dashboard (12h)

**Total Estimated Effort:** 92 hours (~2.5 weeks of dedicated work)

---

## Appendix A: Error Code Reference

### HTTP Status Codes

| Code | Category | Retryable | User Message |
|------|----------|-----------|--------------|
| 400 | Client Error | No | "Por favor, verifique suas respostas." |
| 401 | Auth Error | No | "Sessão expirada. Solicite um novo link." |
| 403 | Auth Error | No | "Acesso negado. Entre em contato com o suporte." |
| 404 | Client Error | No | "Quiz não encontrado. Verifique o link." |
| 408 | Timeout | Yes | "Tempo esgotado. Verifique sua conexão." |
| 429 | Rate Limit | Yes | "Muitas tentativas. Aguarde um momento." |
| 500 | Server Error | Yes | "Erro no servidor. Tente novamente." |
| 503 | Server Error | Yes | "Serviço temporariamente indisponível." |

### Application Error Codes

| Code | Category | Description |
|------|----------|-------------|
| QUIZ_TOKEN_INVALID | Auth | Invalid or malformed token |
| QUIZ_TOKEN_EXPIRED | Auth | Token has expired |
| QUIZ_NOT_FOUND | Client | Quiz session not found |
| QUIZ_ALREADY_COMPLETED | Client | Quiz already submitted |
| ANSWER_VALIDATION_FAILED | Validation | Answer validation error |
| NETWORK_ERROR | Network | Network connectivity issue |
| TIMEOUT_ERROR | Network | Request timeout |

---

## Appendix B: Example Sentry Configuration

```typescript
// sentry.client.config.ts
import * as Sentry from "@sentry/nextjs";

const SENTRY_DSN = process.env.NEXT_PUBLIC_SENTRY_DSN;
const ENVIRONMENT = process.env.NEXT_PUBLIC_ENVIRONMENT || 'development';
const APP_VERSION = process.env.NEXT_PUBLIC_APP_VERSION || 'unknown';

Sentry.init({
  dsn: SENTRY_DSN,
  environment: ENVIRONMENT,
  release: `quiz-app@${APP_VERSION}`,

  // Sampling
  tracesSampleRate: ENVIRONMENT === 'production' ? 0.1 : 1.0,
  replaysSessionSampleRate: 0.1,
  replaysOnErrorSampleRate: 1.0,

  // Integrations
  integrations: [
    new Sentry.BrowserTracing({
      tracePropagationTargets: [
        "localhost",
        /^https:\/\/quiz\.yourapp\.com/,
        /^https:\/\/api\.yourapp\.com/,
      ],
    }),
    new Sentry.Replay({
      maskAllText: true,
      blockAllMedia: true,
      maskAllInputs: true,
    }),
  ],

  // Error filtering
  beforeSend(event, hint) {
    // Filter out known browser errors
    const ignoredErrors = [
      'ResizeObserver loop limit exceeded',
      'Non-Error promise rejection captured',
      'Script error.',
    ];

    if (ignoredErrors.some(msg => event.message?.includes(msg))) {
      return null;
    }

    // Filter out errors from browser extensions
    if (event.exception?.values?.[0]?.stacktrace?.frames?.some(
      frame => frame.filename?.includes('chrome-extension://')
    )) {
      return null;
    }

    return event;
  },

  // Breadcrumbs configuration
  beforeBreadcrumb(breadcrumb, hint) {
    // Filter out sensitive data from breadcrumbs
    if (breadcrumb.category === 'console') {
      return null;
    }

    // Sanitize URLs
    if (breadcrumb.category === 'navigation' && breadcrumb.data?.from) {
      breadcrumb.data.from = sanitizeUrl(breadcrumb.data.from);
    }

    return breadcrumb;
  },
});

function sanitizeUrl(url: string): string {
  try {
    const parsed = new URL(url);
    parsed.searchParams.delete('token');
    return parsed.toString();
  } catch {
    return '[invalid-url]';
  }
}
```

---

**Document End**

**Next Review Date:** November 7, 2025
**Reviewers:** System Architect, QA Lead, DevOps Engineer
