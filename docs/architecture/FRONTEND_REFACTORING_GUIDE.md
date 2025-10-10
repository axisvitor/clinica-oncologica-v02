# Frontend Refactoring Guide - Implementation Examples

## 🎯 Component Refactoring Examples

### 1. AuthContext Refactoring (447 lines → 150 lines each)

#### Current Issue
The `AuthContext.tsx` (447 lines) handles multiple concerns:
- Authentication state
- Session management
- WebSocket connections
- Token refresh logic

#### Proposed Solution: Split into Focused Contexts

```typescript
// src/contexts/auth/AuthContext.tsx (Core auth state - ~150 lines)
interface AuthContextType {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (email: string, password: string, rememberMe?: boolean) => Promise<void>
  logout: () => void
  hasPermission: (permission: string) => boolean
  hasRole: (role: string) => boolean
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  // Core auth logic only
  // ... implementation

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}
```

```typescript
// src/contexts/session/SessionContext.tsx (Session management - ~150 lines)
interface SessionContextType {
  session: { access_token: string; session_id?: string } | null
  getFirebaseToken: () => Promise<string | null>
  refreshToken: () => Promise<void>
  sessionExpiry: number | null
  isSessionExpiring: boolean
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth() // Use core auth context
  const [session, setSession] = useState(null)

  // Session management logic only
  // ... implementation

  return (
    <SessionContext.Provider value={value}>
      {children}
    </SessionContext.Provider>
  )
}
```

```typescript
// src/contexts/websocket/WebSocketContext.tsx (WebSocket - ~150 lines)
interface WebSocketContextType {
  isConnected: boolean
  connectionStatus: 'connecting' | 'connected' | 'disconnected' | 'error'
  connect: (token: string) => void
  disconnect: () => void
  subscribe: (event: string, callback: Function) => () => void
}

export function WebSocketProvider({ children }: { children: ReactNode }) {
  const { session } = useSession() // Use session context
  const [isConnected, setIsConnected] = useState(false)

  // WebSocket logic only
  // ... implementation

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  )
}
```

```typescript
// src/contexts/AuthProvider.tsx (Composite provider - ~50 lines)
export function AuthProvider({ children }: { children: ReactNode }) {
  return (
    <AuthContextProvider>
      <SessionProvider>
        <WebSocketProvider>
          {children}
        </WebSocketProvider>
      </SessionProvider>
    </AuthContextProvider>
  )
}

// Custom hooks for easy access
export const useAuth = () => useContext(AuthContext)
export const useSession = () => useContext(SessionContext)
export const useWebSocket = () => useContext(WebSocketContext)
```

### 2. API Client Refactoring (938 lines → 150 lines each)

#### Current Issue
The `api-client.ts` (938 lines) contains all API endpoints in one monolithic class.

#### Proposed Solution: Domain-Separated Clients

```typescript
// src/lib/clients/base-client.ts (~100 lines)
export abstract class BaseApiClient {
  protected baseURL: string
  protected authToken: string | null = null
  protected csrfToken: string | null = null

  constructor(baseURL: string) {
    this.baseURL = baseURL
  }

  setAuthToken(token: string | null) {
    this.authToken = token
  }

  async request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
    // Core request logic with retry, error handling, etc.
    // ... implementation
  }

  // Core HTTP methods
  async get<T>(endpoint: string, options?: RequestOptions): Promise<T>
  async post<T>(endpoint: string, body?: any, options?: RequestOptions): Promise<T>
  async put<T>(endpoint: string, body?: any, options?: RequestOptions): Promise<T>
  async delete<T>(endpoint: string, options?: RequestOptions): Promise<T>
}
```

```typescript
// src/lib/clients/auth-client.ts (~150 lines)
export class AuthClient extends BaseApiClient {
  async login(credentials: { email: string; password: string }) {
    throw new ApiError(410, { message: 'Use Firebase Auth on client' })
  }

  async createSession(firebaseToken: string, deviceInfo?: Record<string, any>) {
    return this.request<SessionResponse>('/api/v1/session/', {
      method: 'POST',
      body: JSON.stringify({ firebase_token: firebaseToken, device_info: deviceInfo })
    })
  }

  async me() {
    const user = await this.request<UserResponse>('/api/v1/auth/me')
    return { data: user }
  }

  async logout() {
    const response = await this.request<{ message: string }>('/api/v1/auth/logout', {
      method: 'POST'
    })
    return { message: response.message }
  }
}
```

```typescript
// src/lib/clients/patients-client.ts (~150 lines)
export class PatientsClient extends BaseApiClient {
  async list(params: PatientsListParams) {
    const response = await this.request<PatientListResponse>('/api/v1/patients', { params })
    return transformPaginationResponse<Patient>(response, 'patients')
  }

  async get(id: string) {
    return this.request<Patient>(`/api/v1/patients/${id}`)
  }

  async create(patient: Partial<Patient>) {
    return this.request<Patient>('/api/v1/patients', {
      method: 'POST',
      body: JSON.stringify(patient)
    })
  }

  async update(id: string, patient: Partial<Patient>) {
    return this.request<Patient>(`/api/v1/patients/${id}`, {
      method: 'PUT',
      body: JSON.stringify(patient)
    })
  }

  async timeline(id: string) {
    return this.request<{ events: TimelineEvent[] }>(`/api/v1/patients/${id}/timeline`)
  }
}
```

```typescript
// src/lib/clients/quiz-client.ts (~150 lines)
export class QuizClient extends BaseApiClient {
  async templates() {
    return this.request<{ items: any[]; total: number }>('/api/v1/quiz/templates')
  }

  async start(patientId: string, quizTemplateId: string) {
    return this.request<any>('/api/v1/quiz/sessions', {
      method: 'POST',
      body: JSON.stringify({ patient_id: patientId, quiz_template_id: quizTemplateId })
    })
  }

  async getSession(sessionId: string) {
    return this.request<any>(`/api/v1/quiz/sessions/${sessionId}`)
  }

  async submitResponse(sessionId: string, responses: any) {
    return this.request<void>(`/api/v1/quiz/sessions/${sessionId}/submit`, {
      method: 'POST',
      body: JSON.stringify({ responses })
    })
  }
}
```

```typescript
// src/lib/clients/index.ts (Composed client - ~100 lines)
export class ApiClient extends BaseApiClient {
  auth: AuthClient
  patients: PatientsClient
  quiz: QuizClient
  messages: MessagesClient
  flows: FlowsClient
  analytics: AnalyticsClient
  alerts: AlertsClient
  reports: ReportsClient
  adminUsers: AdminUsersClient
  ai: AiClient
  physician: PhysicianClient
  monthlyQuiz: MonthlyQuizClient

  constructor(baseURL: string) {
    super(baseURL)

    // Initialize domain clients
    this.auth = new AuthClient(baseURL)
    this.patients = new PatientsClient(baseURL)
    this.quiz = new QuizClient(baseURL)
    // ... other clients
  }

  setAuthToken(token: string | null) {
    super.setAuthToken(token)
    // Propagate to all domain clients
    this.auth.setAuthToken(token)
    this.patients.setAuthToken(token)
    this.quiz.setAuthToken(token)
    // ... other clients
  }
}

export const apiClient = new ApiClient(getApiUrl())
```

## 🧪 Test Coverage Improvement Strategy

### Current Coverage: ~30% → Target: 80%+

#### 1. Hook Testing Examples

```typescript
// tests/hooks/auth/useAuth.test.ts
import { renderHook, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider, useAuth } from '../../../src/contexts/AuthContext'

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } }
  })

  return ({ children }) => (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        {children}
      </AuthProvider>
    </QueryClientProvider>
  )
}

describe('useAuth', () => {
  it('should start with loading state', () => {
    const { result } = renderHook(() => useAuth(), {
      wrapper: createWrapper()
    })

    expect(result.current.isLoading).toBe(true)
    expect(result.current.user).toBe(null)
    expect(result.current.isAuthenticated).toBe(false)
  })

  it('should handle successful login', async () => {
    const { result } = renderHook(() => useAuth(), {
      wrapper: createWrapper()
    })

    await act(async () => {
      await result.current.login('test@example.com', 'password123')
    })

    expect(result.current.isAuthenticated).toBe(true)
    expect(result.current.user).toMatchObject({
      email: 'test@example.com'
    })
  })

  it('should handle login failure', async () => {
    const { result } = renderHook(() => useAuth(), {
      wrapper: createWrapper()
    })

    await expect(
      act(async () => {
        await result.current.login('invalid@example.com', 'wrongpassword')
      })
    ).rejects.toThrow()

    expect(result.current.isAuthenticated).toBe(false)
    expect(result.current.user).toBe(null)
  })
})
```

#### 2. Component Testing Examples

```typescript
// tests/components/auth/ProtectedRoute.test.tsx
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ProtectedRoute } from '../../../src/components/auth/ProtectedRoute'
import { AuthProvider } from '../../../src/contexts/AuthContext'

const TestComponent = () => <div>Protected Content</div>

const renderProtectedRoute = (user = null) => {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <ProtectedRoute>
          <TestComponent />
        </ProtectedRoute>
      </AuthProvider>
    </MemoryRouter>
  )
}

describe('ProtectedRoute', () => {
  it('should redirect to login when user is not authenticated', () => {
    renderProtectedRoute()

    expect(window.location.pathname).toBe('/login')
    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument()
  })

  it('should render children when user is authenticated', () => {
    const authenticatedUser = { id: '1', email: 'test@example.com' }
    renderProtectedRoute(authenticatedUser)

    expect(screen.getByText('Protected Content')).toBeInTheDocument()
  })

  it('should show loading spinner while authentication is loading', () => {
    renderProtectedRoute(null, true) // isLoading = true

    expect(screen.getByTestId('loading-spinner')).toBeInTheDocument()
  })
})
```

#### 3. API Client Testing

```typescript
// tests/lib/clients/patients-client.test.ts
import { PatientsClient } from '../../../src/lib/clients/patients-client'

describe('PatientsClient', () => {
  let client: PatientsClient

  beforeEach(() => {
    client = new PatientsClient('https://api.test.com')
    global.fetch = jest.fn()
  })

  afterEach(() => {
    jest.resetAllMocks()
  })

  it('should fetch patients list with filters', async () => {
    const mockResponse = {
      patients: [{ id: '1', name: 'Test Patient' }],
      total: 1,
      page: 1,
      size: 10
    }

    ;(global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse
    })

    const result = await client.list({ page: 1, status: 'active' })

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/patients?page=1&status=active'),
      expect.any(Object)
    )
    expect(result.data).toEqual(mockResponse.patients)
  })

  it('should handle API errors gracefully', async () => {
    ;(global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: async () => ({ message: 'Patient not found' })
    })

    await expect(client.get('invalid-id')).rejects.toThrow('Patient not found')
  })
})
```

## 🚀 Route-Based Code Splitting Implementation

### Current vs Proposed

```typescript
// Before: All routes loaded in main bundle
import PatientsPage from '../pages/PatientsPage'
import DashboardPage from '../pages/DashboardPage'
import QuizPage from '../pages/QuizPage'

// After: Lazy-loaded routes
const PatientsPage = lazy(() => import('../pages/PatientsPage'))
const DashboardPage = lazy(() => import('../pages/DashboardPage'))
const QuizPage = lazy(() => import('../pages/QuizPage'))
const AdminPage = lazy(() => import('../pages/AdminPage'))
```

### Implementation Example

```typescript
// src/routes/LazyRoutes.tsx
import { lazy, Suspense } from 'react'
import { Routes, Route } from 'react-router-dom'
import { PageSkeleton } from '../components/ui/PageSkeleton'
import { ErrorBoundary } from '../components/ui/ErrorBoundary'

// Lazy load page components
const DashboardPage = lazy(() => import('../pages/DashboardPage'))
const PatientsPage = lazy(() => import('../pages/PatientsPage'))
const QuizPage = lazy(() => import('../pages/QuizPage'))
const AdminPage = lazy(() => import('../pages/AdminPage'))
const ReportsPage = lazy(() => import('../pages/ReportsPage'))
const SettingsPage = lazy(() => import('../pages/SettingsPage'))

// Route-specific error fallbacks
const DashboardError = () => <div>Dashboard unavailable. Please try again.</div>
const PatientsError = () => <div>Patient data unavailable. Please refresh.</div>

export function LazyRoutes() {
  return (
    <Routes>
      <Route path="/" element={
        <ErrorBoundary fallback={DashboardError}>
          <Suspense fallback={<PageSkeleton />}>
            <DashboardPage />
          </Suspense>
        </ErrorBoundary>
      } />

      <Route path="/patients/*" element={
        <ErrorBoundary fallback={PatientsError}>
          <Suspense fallback={<PageSkeleton />}>
            <PatientsPage />
          </Suspense>
        </ErrorBoundary>
      } />

      <Route path="/quiz/*" element={
        <ErrorBoundary fallback={<div>Quiz unavailable</div>}>
          <Suspense fallback={<PageSkeleton />}>
            <QuizPage />
          </Suspense>
        </ErrorBoundary>
      } />

      <Route path="/admin/*" element={
        <ErrorBoundary fallback={<div>Admin panel unavailable</div>}>
          <Suspense fallback={<PageSkeleton />}>
            <AdminPage />
          </Suspense>
        </ErrorBoundary>
      } />
    </Routes>
  )
}
```

### Page Skeleton Component

```typescript
// src/components/ui/PageSkeleton.tsx
export function PageSkeleton() {
  return (
    <div className="animate-pulse">
      <div className="h-8 bg-gray-200 rounded w-1/4 mb-6"></div>
      <div className="space-y-4">
        <div className="h-4 bg-gray-200 rounded w-3/4"></div>
        <div className="h-4 bg-gray-200 rounded w-1/2"></div>
        <div className="h-4 bg-gray-200 rounded w-5/6"></div>
      </div>
      <div className="mt-8 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="h-48 bg-gray-200 rounded"></div>
        ))}
      </div>
    </div>
  )
}
```

## 📊 Performance Monitoring Implementation

### Web Vitals Integration

```typescript
// src/lib/performance.ts
import { getCLS, getFID, getFCP, getLCP, getTTFB } from 'web-vitals'

interface PerformanceMetric {
  name: string
  value: number
  rating: 'good' | 'needs-improvement' | 'poor'
  timestamp: number
}

class PerformanceTracker {
  private metrics: PerformanceMetric[] = []

  init() {
    // Track Core Web Vitals
    getCLS(this.handleMetric.bind(this))
    getFID(this.handleMetric.bind(this))
    getFCP(this.handleMetric.bind(this))
    getLCP(this.handleMetric.bind(this))
    getTTFB(this.handleMetric.bind(this))
  }

  private handleMetric(metric: any) {
    const performanceMetric: PerformanceMetric = {
      name: metric.name,
      value: metric.value,
      rating: metric.rating,
      timestamp: Date.now()
    }

    this.metrics.push(performanceMetric)

    // Send to analytics (optional)
    this.sendToAnalytics(performanceMetric)

    // Log poor performance
    if (metric.rating === 'poor') {
      console.warn(`Poor ${metric.name} performance:`, metric.value)
    }
  }

  private sendToAnalytics(metric: PerformanceMetric) {
    // Send to your analytics service
    // Example: Google Analytics 4
    if (typeof gtag !== 'undefined') {
      gtag('event', 'web_vital', {
        event_category: 'Performance',
        event_label: metric.name,
        value: metric.value,
        custom_parameter_1: metric.rating
      })
    }
  }

  getMetrics(): PerformanceMetric[] {
    return this.metrics
  }

  getMetricsByName(name: string): PerformanceMetric[] {
    return this.metrics.filter(m => m.name === name)
  }
}

export const performanceTracker = new PerformanceTracker()
```

```typescript
// src/App.tsx - Integration
import { useEffect } from 'react'
import { performanceTracker } from './lib/performance'

export function App() {
  useEffect(() => {
    // Initialize performance tracking
    performanceTracker.init()

    // Report performance metrics every 30 seconds in development
    if (process.env.NODE_ENV === 'development') {
      const interval = setInterval(() => {
        const metrics = performanceTracker.getMetrics()
        console.table(metrics)
      }, 30000)

      return () => clearInterval(interval)
    }
  }, [])

  return (
    <Router>
      <AuthProvider>
        <LazyRoutes />
      </AuthProvider>
    </Router>
  )
}
```

## 📋 Implementation Checklist

### Phase 1: Foundation (1-2 weeks)

#### Component Refactoring
- [ ] Split AuthContext into 3 focused contexts
  - [ ] AuthContext.tsx (core auth state)
  - [ ] SessionContext.tsx (session management)
  - [ ] WebSocketContext.tsx (websocket connections)
- [ ] Split api-client into domain-separated clients
  - [ ] BaseApiClient (shared logic)
  - [ ] AuthClient, PatientsClient, QuizClient, etc.
  - [ ] Composed ApiClient (main interface)

#### Testing Infrastructure
- [ ] Add tests for core hooks (useAuth, useSession)
- [ ] Test critical components (ProtectedRoute, AuthProvider)
- [ ] Add API client unit tests
- [ ] Set up test coverage reporting
- [ ] Target: 60% coverage by end of phase

#### Performance Foundation
- [ ] Implement route-based code splitting
- [ ] Add PageSkeleton components
- [ ] Set up Web Vitals tracking
- [ ] Create performance monitoring dashboard

### Phase 2: Enhancement (1-2 weeks)

#### Advanced Testing
- [ ] Integration tests for auth flows
- [ ] E2E tests for critical user journeys
- [ ] Performance testing suite
- [ ] Target: 80% coverage by end of phase

#### Error Handling
- [ ] Route-specific error boundaries
- [ ] Contextual error fallbacks
- [ ] Error analytics integration
- [ ] User-friendly error messages

#### Accessibility
- [ ] ARIA label audit
- [ ] Keyboard navigation testing
- [ ] Screen reader compatibility
- [ ] Focus management

### Phase 3: Optimization (2-3 weeks)

#### Advanced Performance
- [ ] Virtual scrolling for large lists
- [ ] Service worker implementation
- [ ] Bundle size optimization
- [ ] Performance budgets in CI/CD

#### Monitoring & Analytics
- [ ] Performance dashboard
- [ ] Error tracking system
- [ ] User experience metrics
- [ ] Automated performance alerts

---

This refactoring guide provides concrete examples and implementation steps to transform the frontend from its current state (8.5/10) to production-ready excellence (9.5/10).