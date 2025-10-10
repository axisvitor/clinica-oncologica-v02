# Test Templates and Patterns
**Frontend Testing Best Practices Guide**
**Date**: 2025-01-09

---

## 🎯 Testing Strategy Overview

### Test Pyramid Implementation
```
         /\
        /E2E\      ← 10% (Critical user journeys)
       /------\
      /Integr. \   ← 20% (Component interactions)
     /----------\
    /   Unit     \ ← 70% (Individual functions/components)
   /--------------\
```

### Testing Categories
- **Unit Tests**: Component logic, hooks, utilities
- **Integration Tests**: API calls, component interactions
- **E2E Tests**: Complete user workflows
- **Performance Tests**: Rendering speed, bundle size
- **Accessibility Tests**: Screen reader, keyboard navigation
- **Security Tests**: XSS prevention, input validation

---

## 🧪 Component Testing Templates

### **Template 1: React Component Testing**
```typescript
// tests/components/ExampleComponent.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ExampleComponent } from '@/components/ExampleComponent'
import { renderWithAuth, createMockAuthContext } from '../../test-utils'

describe('ExampleComponent', () => {
  // Test data setup
  const mockProps = {
    title: 'Test Title',
    onSubmit: vi.fn(),
    loading: false
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ✅ Rendering Tests
  describe('Rendering', () => {
    it('renders with default props', () => {
      render(<ExampleComponent {...mockProps} />)

      expect(screen.getByText('Test Title')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /submit/i })).toBeInTheDocument()
    })

    it('renders loading state correctly', () => {
      render(<ExampleComponent {...mockProps} loading={true} />)

      expect(screen.getByRole('progressbar')).toBeInTheDocument()
      expect(screen.getByRole('button')).toBeDisabled()
    })

    it('renders error state when props are invalid', () => {
      const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})

      render(<ExampleComponent {...mockProps} title="" />)

      expect(screen.getByText(/error/i)).toBeInTheDocument()
      consoleError.mockRestore()
    })
  })

  // ✅ User Interaction Tests
  describe('User Interactions', () => {
    it('handles click events correctly', async () => {
      const user = userEvent.setup()
      render(<ExampleComponent {...mockProps} />)

      const submitButton = screen.getByRole('button', { name: /submit/i })
      await user.click(submitButton)

      expect(mockProps.onSubmit).toHaveBeenCalledTimes(1)
    })

    it('handles form submission', async () => {
      const user = userEvent.setup()
      render(<ExampleComponent {...mockProps} />)

      const input = screen.getByLabelText(/email/i)
      await user.type(input, 'test@example.com')

      const form = screen.getByRole('form')
      await user.submit(form)

      expect(mockProps.onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          email: 'test@example.com'
        })
      )
    })

    it('handles keyboard navigation', async () => {
      const user = userEvent.setup()
      render(<ExampleComponent {...mockProps} />)

      const firstInput = screen.getByLabelText(/email/i)
      await user.click(firstInput)
      await user.tab()

      expect(screen.getByLabelText(/password/i)).toHaveFocus()
    })
  })

  // ✅ Edge Cases
  describe('Edge Cases', () => {
    it('handles network errors gracefully', async () => {
      const onSubmit = vi.fn().mockRejectedValue(new Error('Network error'))
      render(<ExampleComponent {...mockProps} onSubmit={onSubmit} />)

      const user = userEvent.setup()
      await user.click(screen.getByRole('button'))

      await waitFor(() => {
        expect(screen.getByText(/network error/i)).toBeInTheDocument()
      })
    })

    it('handles malformed data', () => {
      const invalidProps = { ...mockProps, data: null }
      render(<ExampleComponent {...invalidProps} />)

      expect(screen.getByText(/no data available/i)).toBeInTheDocument()
    })

    it('handles concurrent operations', async () => {
      const onSubmit = vi.fn().mockImplementation(() =>
        new Promise(resolve => setTimeout(resolve, 100))
      )
      render(<ExampleComponent {...mockProps} onSubmit={onSubmit} />)

      const user = userEvent.setup()
      const button = screen.getByRole('button')

      // Click multiple times rapidly
      await user.click(button)
      await user.click(button)
      await user.click(button)

      await waitFor(() => {
        expect(onSubmit).toHaveBeenCalledTimes(1) // Should debounce
      })
    })
  })

  // ✅ Accessibility Tests
  describe('Accessibility', () => {
    it('has proper ARIA labels', () => {
      render(<ExampleComponent {...mockProps} />)

      const button = screen.getByRole('button')
      expect(button).toHaveAttribute('aria-label')

      const form = screen.getByRole('form')
      expect(form).toHaveAttribute('aria-describedby')
    })

    it('supports keyboard navigation', async () => {
      const user = userEvent.setup()
      render(<ExampleComponent {...mockProps} />)

      // Test tab order
      await user.tab()
      expect(screen.getByLabelText(/email/i)).toHaveFocus()

      await user.tab()
      expect(screen.getByLabelText(/password/i)).toHaveFocus()

      await user.tab()
      expect(screen.getByRole('button')).toHaveFocus()
    })

    it('announces state changes to screen readers', async () => {
      render(<ExampleComponent {...mockProps} />)

      const user = userEvent.setup()
      await user.click(screen.getByRole('button'))

      await waitFor(() => {
        const status = screen.getByRole('status')
        expect(status).toHaveTextContent(/submitting/i)
      })
    })
  })

  // ✅ Authentication Context Tests
  describe('With Authentication', () => {
    it('renders correctly for authenticated users', () => {
      const authContext = createMockAuthContext({ isAuthenticated: true })
      renderWithAuth(<ExampleComponent {...mockProps} />, authContext)

      expect(screen.getByText(/welcome back/i)).toBeInTheDocument()
    })

    it('shows login prompt for unauthenticated users', () => {
      const authContext = createMockAuthContext({ isAuthenticated: false })
      renderWithAuth(<ExampleComponent {...mockProps} />, authContext)

      expect(screen.getByText(/please log in/i)).toBeInTheDocument()
    })
  })
})
```

### **Template 2: Custom Hook Testing**
```typescript
// tests/hooks/useExampleHook.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useExampleHook } from '@/hooks/useExampleHook'
import { createWrapperWithProviders } from '../test-utils'

describe('useExampleHook', () => {
  const wrapper = createWrapperWithProviders()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ✅ Initial State Tests
  describe('Initial State', () => {
    it('initializes with correct default state', () => {
      const { result } = renderHook(() => useExampleHook(), { wrapper })

      expect(result.current.data).toBeNull()
      expect(result.current.loading).toBe(false)
      expect(result.current.error).toBeNull()
    })

    it('accepts initial parameters', () => {
      const initialParams = { id: '123', enabled: true }
      const { result } = renderHook(() => useExampleHook(initialParams), { wrapper })

      expect(result.current.params).toEqual(initialParams)
    })
  })

  // ✅ State Management Tests
  describe('State Management', () => {
    it('updates state when calling actions', async () => {
      const { result } = renderHook(() => useExampleHook(), { wrapper })

      act(() => {
        result.current.fetchData('test-id')
      })

      expect(result.current.loading).toBe(true)

      await waitFor(() => {
        expect(result.current.loading).toBe(false)
        expect(result.current.data).toBeDefined()
      })
    })

    it('handles multiple rapid calls correctly', async () => {
      const { result } = renderHook(() => useExampleHook(), { wrapper })

      act(() => {
        result.current.fetchData('id1')
        result.current.fetchData('id2')
        result.current.fetchData('id3')
      })

      await waitFor(() => {
        expect(result.current.data.id).toBe('id3') // Latest call wins
      })
    })
  })

  // ✅ Side Effects Tests
  describe('Side Effects', () => {
    it('subscribes to external data sources', async () => {
      const mockSubscribe = vi.fn()
      const mockUnsubscribe = vi.fn()

      vi.mock('@/lib/websocket', () => ({
        subscribe: mockSubscribe.mockReturnValue(mockUnsubscribe)
      }))

      const { unmount } = renderHook(() => useExampleHook({ autoSubscribe: true }), { wrapper })

      expect(mockSubscribe).toHaveBeenCalled()

      unmount()
      expect(mockUnsubscribe).toHaveBeenCalled()
    })

    it('cleans up resources on unmount', () => {
      const cleanup = vi.fn()
      vi.mocked(useExampleHook).mockImplementation(() => {
        useEffect(() => cleanup, [])
        return { data: null, loading: false, error: null }
      })

      const { unmount } = renderHook(() => useExampleHook(), { wrapper })
      unmount()

      expect(cleanup).toHaveBeenCalled()
    })
  })

  // ✅ Error Handling Tests
  describe('Error Handling', () => {
    it('handles API errors gracefully', async () => {
      const mockError = new Error('API Error')
      vi.mocked(apiClient.get).mockRejectedValue(mockError)

      const { result } = renderHook(() => useExampleHook(), { wrapper })

      act(() => {
        result.current.fetchData('error-id')
      })

      await waitFor(() => {
        expect(result.current.error).toBe(mockError)
        expect(result.current.loading).toBe(false)
      })
    })

    it('retries failed requests', async () => {
      vi.mocked(apiClient.get)
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValueOnce({ data: 'success' })

      const { result } = renderHook(() => useExampleHook({ retry: true }), { wrapper })

      act(() => {
        result.current.fetchData('retry-id')
      })

      await waitFor(() => {
        expect(result.current.data).toBe('success')
        expect(apiClient.get).toHaveBeenCalledTimes(2)
      })
    })
  })
})
```

### **Template 3: API Integration Testing**
```typescript
// tests/integration/api-example.test.ts
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { apiClient, ApiError } from '@/lib/api-client'
import { mockApiResponse, mockApiError } from '../test-utils'

// Mock fetch globally
const mockFetch = vi.fn()
global.fetch = mockFetch

describe('API Integration - Example Service', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    apiClient.setAuthToken('mock-token')
    apiClient.setBaseURL('http://localhost:8000/api/v1')
  })

  afterEach(() => {
    vi.clearAllTimers()
  })

  // ✅ Success Scenarios
  describe('Success Scenarios', () => {
    it('fetches data successfully', async () => {
      const mockData = { id: 1, name: 'Test Item' }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Map([['content-type', 'application/json']]),
        json: async () => mockData
      })

      const result = await apiClient.get('/items/1')

      expect(result).toEqual(mockData)
      expect(mockFetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v1/items/1',
        expect.objectContaining({
          method: 'GET',
          headers: expect.objectContaining({
            'Authorization': 'Bearer mock-token',
            'Content-Type': 'application/json'
          })
        })
      )
    })

    it('posts data with CSRF protection', async () => {
      const postData = { name: 'New Item' }
      const responseData = { id: 2, ...postData }

      // Mock CSRF token fetch
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          headers: new Map([['x-csrf-token', 'csrf-123']])
        })
        .mockResolvedValueOnce({
          ok: true,
          status: 201,
          json: async () => responseData
        })

      const result = await apiClient.post('/items', postData)

      expect(result).toEqual(responseData)
      expect(mockFetch).toHaveBeenCalledTimes(2) // CSRF + actual request
      expect(mockFetch).toHaveBeenLastCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.objectContaining({
            'X-CSRF-Token': 'csrf-123'
          })
        })
      )
    })

    it('handles pagination correctly', async () => {
      const paginatedData = {
        items: [{ id: 1 }, { id: 2 }],
        pagination: { page: 1, per_page: 10, total: 100 }
      }

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => paginatedData
      })

      const result = await apiClient.get('/items', { params: { page: 1, per_page: 10 } })

      expect(result.items).toHaveLength(2)
      expect(result.pagination.total).toBe(100)
    })
  })

  // ✅ Error Scenarios
  describe('Error Scenarios', () => {
    it('handles 401 unauthorized errors', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: async () => ({ message: 'Unauthorized' })
      })

      await expect(apiClient.get('/protected-resource')).rejects.toThrow(ApiError)
      await expect(apiClient.get('/protected-resource')).rejects.toThrow('Unauthorized')
    })

    it('handles 422 validation errors', async () => {
      const validationErrors = {
        message: 'Validation failed',
        errors: {
          email: ['Email is required'],
          password: ['Password too short']
        }
      }

      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 422,
        json: async () => validationErrors
      })

      try {
        await apiClient.post('/users', { email: '', password: '123' })
      } catch (error) {
        expect(error).toBeInstanceOf(ApiError)
        expect(error.status).toBe(422)
        expect(error.errors).toEqual(validationErrors.errors)
      }
    })

    it('handles network timeouts', async () => {
      mockFetch.mockImplementation(() =>
        new Promise((_, reject) =>
          setTimeout(() => reject(new Error('Network timeout')), 100)
        )
      )

      vi.useFakeTimers()

      const promise = apiClient.get('/slow-endpoint')
      vi.advanceTimersByTime(5000) // Trigger timeout

      await expect(promise).rejects.toThrow('Network timeout')

      vi.useRealTimers()
    })

    it('handles malformed JSON responses', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => { throw new SyntaxError('Invalid JSON') }
      })

      await expect(apiClient.get('/malformed-response')).rejects.toThrow('Invalid JSON')
    })
  })

  // ✅ Authentication Flow
  describe('Authentication Flow', () => {
    it('includes auth token in requests', async () => {
      apiClient.setAuthToken('new-auth-token')

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({})
      })

      await apiClient.get('/protected')

      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.objectContaining({
            'Authorization': 'Bearer new-auth-token'
          })
        })
      )
    })

    it('refreshes expired tokens automatically', async () => {
      // First request fails with 401
      mockFetch
        .mockResolvedValueOnce({
          ok: false,
          status: 401,
          json: async () => ({ message: 'Token expired' })
        })
        // Token refresh succeeds
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ access_token: 'new-token' })
        })
        // Retry original request succeeds
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ data: 'success' })
        })

      const result = await apiClient.get('/protected-resource')

      expect(result.data).toBe('success')
      expect(mockFetch).toHaveBeenCalledTimes(3)
    })

    it('handles auth failure after token refresh', async () => {
      // First request fails
      mockFetch
        .mockResolvedValueOnce({
          ok: false,
          status: 401
        })
        // Token refresh also fails
        .mockResolvedValueOnce({
          ok: false,
          status: 401,
          json: async () => ({ message: 'Invalid refresh token' })
        })

      await expect(apiClient.get('/protected')).rejects.toThrow('Invalid refresh token')

      // Should trigger logout
      expect(window.location.href).toContain('/login')
    })
  })

  // ✅ Rate Limiting
  describe('Rate Limiting', () => {
    it('handles 429 rate limit responses', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 429,
        headers: new Map([['retry-after', '60']]),
        json: async () => ({ message: 'Rate limit exceeded' })
      })

      await expect(apiClient.get('/rate-limited')).rejects.toThrow('Rate limit exceeded')
    })

    it('respects retry-after headers', async () => {
      vi.useFakeTimers()

      mockFetch
        .mockResolvedValueOnce({
          ok: false,
          status: 429,
          headers: new Map([['retry-after', '2']])
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ data: 'success after retry' })
        })

      const promise = apiClient.get('/rate-limited', { retryOnRateLimit: true })

      vi.advanceTimersByTime(2000)
      const result = await promise

      expect(result.data).toBe('success after retry')
      vi.useRealTimers()
    })
  })

  // ✅ Concurrent Requests
  describe('Concurrent Requests', () => {
    it('handles multiple simultaneous requests', async () => {
      const requests = Array.from({ length: 5 }, (_, i) =>
        mockFetch.mockResolvedValueOnce({
          ok: true,
          json: async () => ({ id: i + 1 })
        })
      )

      const promises = Array.from({ length: 5 }, (_, i) =>
        apiClient.get(`/items/${i + 1}`)
      )

      const results = await Promise.all(promises)

      expect(results).toHaveLength(5)
      results.forEach((result, index) => {
        expect(result.id).toBe(index + 1)
      })
    })

    it('prevents duplicate requests to same endpoint', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({ data: 'response' })
      })

      // Make multiple requests to same endpoint simultaneously
      const promises = Array.from({ length: 3 }, () =>
        apiClient.get('/items/1', { dedupeRequests: true })
      )

      await Promise.all(promises)

      expect(mockFetch).toHaveBeenCalledTimes(1) // Should dedupe
    })
  })
})
```

---

## 🎭 Mock Patterns & Utilities

### **Comprehensive Mock Setup**
```typescript
// test-utils/mock-setup.ts
import { vi } from 'vitest'

// API Client Mocks
export const createMockApiClient = () => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  delete: vi.fn(),
  setAuthToken: vi.fn(),
  setBaseURL: vi.fn(),
  getCsrfToken: vi.fn().mockReturnValue('csrf-token'),
  getBaseURL: vi.fn().mockReturnValue('http://localhost:8000')
})

// Firebase Auth Mocks
export const createMockFirebaseAuth = () => ({
  currentUser: null,
  onAuthStateChanged: vi.fn(),
  signInWithEmailAndPassword: vi.fn(),
  signOut: vi.fn(),
  createUserWithEmailAndPassword: vi.fn(),
  sendPasswordResetEmail: vi.fn(),
  updateProfile: vi.fn()
})

// WebSocket Mocks
export const createMockWebSocket = () => ({
  connect: vi.fn(),
  disconnect: vi.fn(),
  send: vi.fn(),
  on: vi.fn(),
  off: vi.fn(),
  readyState: 1,
  CONNECTING: 0,
  OPEN: 1,
  CLOSING: 2,
  CLOSED: 3
})

// React Query Mocks
export const createMockQueryClient = () => ({
  getQueryData: vi.fn(),
  setQueryData: vi.fn(),
  invalidateQueries: vi.fn(),
  removeQueries: vi.fn(),
  clear: vi.fn()
})
```

### **Data Factory Pattern**
```typescript
// test-utils/data-factories.ts
import { faker } from '@faker-js/faker'

export const createMockUser = (overrides = {}) => ({
  id: faker.string.uuid(),
  email: faker.internet.email(),
  full_name: faker.person.fullName(),
  role: 'user',
  is_active: true,
  permissions: ['read:own_data'],
  created_at: faker.date.past().toISOString(),
  avatar_url: faker.image.avatar(),
  ...overrides
})

export const createMockPatient = (overrides = {}) => ({
  id: faker.string.uuid(),
  name: faker.person.fullName(),
  email: faker.internet.email(),
  phone: faker.phone.number(),
  birth_date: faker.date.birthdate().toISOString().split('T')[0],
  gender: faker.helpers.arrayElement(['male', 'female', 'other']),
  treatment_type: faker.helpers.arrayElement(['chemotherapy', 'radiation', 'surgery']),
  status: 'active',
  created_at: faker.date.past().toISOString(),
  updated_at: faker.date.recent().toISOString(),
  ...overrides
})

export const createMockMessage = (overrides = {}) => ({
  id: faker.string.uuid(),
  patient_id: faker.string.uuid(),
  content: faker.lorem.sentence(),
  type: 'text',
  direction: faker.helpers.arrayElement(['inbound', 'outbound']),
  status: faker.helpers.arrayElement(['sent', 'delivered', 'read', 'failed']),
  sent_at: faker.date.recent().toISOString(),
  delivered_at: faker.date.recent().toISOString(),
  metadata: {},
  ...overrides
})

export const createMockQuizSession = (overrides = {}) => ({
  id: faker.string.uuid(),
  patient_id: faker.string.uuid(),
  quiz_template_id: faker.string.uuid(),
  status: faker.helpers.arrayElement(['pending', 'in_progress', 'completed', 'expired']),
  started_at: faker.date.recent().toISOString(),
  completed_at: null,
  responses: [],
  score: null,
  ...overrides
})

// Pagination factory
export const createMockPaginatedResponse = <T>(
  items: T[],
  options: {
    page?: number
    per_page?: number
    total?: number
  } = {}
) => ({
  items,
  pagination: {
    page: options.page || 1,
    per_page: options.per_page || 10,
    total: options.total || items.length,
    total_pages: Math.ceil((options.total || items.length) / (options.per_page || 10))
  }
})
```

---

## 🔧 Performance Testing Templates

### **Component Performance Testing**
```typescript
// tests/performance/component-performance.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { performance } from 'perf_hooks'
import { ExampleComponent } from '@/components/ExampleComponent'

describe('Component Performance', () => {
  it('renders within performance budget', () => {
    const start = performance.now()

    render(<ExampleComponent data={Array.from({ length: 1000 }, (_, i) => ({ id: i }))} />)

    const end = performance.now()
    const renderTime = end - start

    expect(renderTime).toBeLessThan(16) // 60fps budget
  })

  it('handles large datasets efficiently', () => {
    const largeDataset = Array.from({ length: 10000 }, (_, i) => ({
      id: i,
      name: `Item ${i}`
    }))

    const start = performance.now()
    render(<ExampleComponent data={largeDataset} />)
    const end = performance.now()

    expect(end - start).toBeLessThan(100) // 100ms budget for large datasets
  })

  it('memo optimization prevents unnecessary re-renders', () => {
    const renderSpy = vi.fn()
    const MemoizedComponent = React.memo(({ data, onRender }) => {
      onRender()
      return <div>{data.length} items</div>
    })

    const { rerender } = render(
      <MemoizedComponent data={[1, 2, 3]} onRender={renderSpy} />
    )

    expect(renderSpy).toHaveBeenCalledTimes(1)

    // Re-render with same props
    rerender(<MemoizedComponent data={[1, 2, 3]} onRender={renderSpy} />)

    expect(renderSpy).toHaveBeenCalledTimes(1) // Should not re-render
  })
})
```

### **Bundle Size Testing**
```typescript
// tests/performance/bundle-analysis.test.ts
import { describe, it, expect } from 'vitest'
import { analyze } from 'bundle-analyzer'

describe('Bundle Size Analysis', () => {
  it('main bundle stays under size limit', async () => {
    const stats = await analyze('./dist')
    const mainBundle = stats.assets.find(asset => asset.name.includes('main'))

    expect(mainBundle.size).toBeLessThan(500 * 1024) // 500KB limit
  })

  it('vendor bundle is efficiently split', async () => {
    const stats = await analyze('./dist')
    const vendorBundle = stats.assets.find(asset => asset.name.includes('vendor'))

    expect(vendorBundle.size).toBeLessThan(1024 * 1024) // 1MB limit
  })

  it('lazy-loaded chunks are properly sized', async () => {
    const stats = await analyze('./dist')
    const lazyChunks = stats.assets.filter(asset =>
      asset.name.includes('lazy') || asset.name.includes('chunk')
    )

    lazyChunks.forEach(chunk => {
      expect(chunk.size).toBeLessThan(200 * 1024) // 200KB per chunk
    })
  })
})
```

---

## 🛡️ Security Testing Templates

### **XSS Prevention Testing**
```typescript
// tests/security/xss-prevention.test.tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { UserProfile } from '@/components/UserProfile'

describe('XSS Prevention', () => {
  it('sanitizes user input in display components', () => {
    const maliciousInput = '<script>alert("XSS")</script><img src=x onerror=alert("XSS")>'

    render(<UserProfile name={maliciousInput} />)

    // Verify script tags are not present in DOM
    expect(document.querySelector('script')).toBeNull()
    expect(screen.queryByRole('img')).toBeNull()

    // Verify content is escaped
    expect(screen.getByText(maliciousInput, { exact: false })).toBeInTheDocument()
  })

  it('prevents innerHTML injection', () => {
    const DangerousComponent = ({ content }) => {
      return <div dangerouslySetInnerHTML={{ __html: content }} />
    }

    const maliciousContent = '<script>window.hacked = true</script>'

    render(<DangerousComponent content={maliciousContent} />)

    // Should not execute the script
    expect(window.hacked).toBeUndefined()
  })

  it('validates URL inputs', () => {
    const maliciousUrl = 'javascript:alert("XSS")'

    render(<a href={maliciousUrl}>Click me</a>)

    const link = screen.getByRole('link')
    expect(link.getAttribute('href')).not.toBe(maliciousUrl)
  })
})
```

### **Input Validation Testing**
```typescript
// tests/security/input-validation.test.tsx
import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ContactForm } from '@/components/ContactForm'

describe('Input Validation', () => {
  it('validates email format', async () => {
    const user = userEvent.setup()
    render(<ContactForm />)

    const emailInput = screen.getByLabelText(/email/i)
    await user.type(emailInput, 'invalid-email')

    fireEvent.blur(emailInput)

    expect(screen.getByText(/invalid email format/i)).toBeInTheDocument()
  })

  it('prevents SQL injection in search inputs', async () => {
    const mockSearch = vi.fn()
    const user = userEvent.setup()

    render(<SearchForm onSearch={mockSearch} />)

    const searchInput = screen.getByLabelText(/search/i)
    await user.type(searchInput, "'; DROP TABLE users; --")

    fireEvent.submit(screen.getByRole('form'))

    // Verify the malicious input is sanitized
    expect(mockSearch).toHaveBeenCalledWith(
      expect.not.stringContaining('DROP TABLE')
    )
  })

  it('limits input length', async () => {
    const user = userEvent.setup()
    render(<ContactForm />)

    const messageInput = screen.getByLabelText(/message/i)
    const longMessage = 'a'.repeat(1001) // Exceeds 1000 char limit

    await user.type(messageInput, longMessage)

    expect(messageInput.value).toHaveLength(1000) // Should be truncated
    expect(screen.getByText(/message too long/i)).toBeInTheDocument()
  })

  it('sanitizes file uploads', async () => {
    const user = userEvent.setup()
    render(<FileUpload />)

    const fileInput = screen.getByLabelText(/upload/i)
    const maliciousFile = new File(
      ['<?php system($_GET["cmd"]); ?>'],
      'malicious.php',
      { type: 'application/x-php' }
    )

    await user.upload(fileInput, maliciousFile)

    expect(screen.getByText(/file type not allowed/i)).toBeInTheDocument()
  })
})
```

---

## 📊 Coverage Reporting Templates

### **Custom Coverage Analysis**
```typescript
// scripts/analyze-coverage.ts
import fs from 'fs'
import path from 'path'

interface CoverageReport {
  total: {
    lines: { pct: number }
    functions: { pct: number }
    branches: { pct: number }
    statements: { pct: number }
  }
  files: Record<string, any>
}

export function analyzeCoverage() {
  const coveragePath = path.join(process.cwd(), 'coverage/coverage-summary.json')
  const coverage: CoverageReport = JSON.parse(fs.readFileSync(coveragePath, 'utf8'))

  const criticalFiles = [
    'src/contexts/AuthContext.tsx',
    'src/lib/api-client.ts',
    'src/services/firebase-auth.ts',
    'src/hooks/auth/useAuth.ts'
  ]

  const criticalFilesCoverage = criticalFiles.map(file => ({
    file,
    coverage: coverage.files[file]?.lines?.pct || 0
  }))

  const lowCoverageFiles = criticalFilesCoverage.filter(
    ({ coverage }) => coverage < 80
  )

  if (lowCoverageFiles.length > 0) {
    console.error('Critical files with low coverage:')
    lowCoverageFiles.forEach(({ file, coverage }) => {
      console.error(`  ${file}: ${coverage}%`)
    })
    process.exit(1)
  }

  console.log('✅ All critical files meet coverage requirements')
}
```

---

## 🎯 Test Execution Scripts

### **Comprehensive Test Runner**
```bash
#!/bin/bash
# scripts/run-comprehensive-tests.sh

echo "🧪 Running Comprehensive Test Suite"

# Unit Tests
echo "📦 Running Unit Tests..."
npm run test:unit -- --coverage --reporter=verbose

# Integration Tests
echo "🔗 Running Integration Tests..."
npm run test:integration -- --reporter=verbose

# E2E Tests
echo "🎭 Running E2E Tests..."
npm run test:e2e -- --headless

# Performance Tests
echo "⚡ Running Performance Tests..."
npm run test:performance

# Accessibility Tests
echo "♿ Running Accessibility Tests..."
npm run test:a11y

# Security Tests
echo "🛡️ Running Security Tests..."
npm run test:security

# Generate Combined Report
echo "📊 Generating Combined Coverage Report..."
npm run coverage:merge
npm run coverage:report

echo "✅ All tests completed!"
```

### **Pre-commit Test Hook**
```bash
#!/bin/bash
# .husky/pre-commit

# Run tests on staged files only
STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep -E '\.(ts|tsx)$')

if [ ${#STAGED_FILES} -eq 0 ]; then
  echo "No TypeScript files staged for commit"
  exit 0
fi

echo "Running tests on staged files..."

# Type checking
npm run typecheck

# Linting
npm run lint -- $STAGED_FILES

# Unit tests for affected files
npm run test:affected -- --run

# Coverage check
npm run test:coverage -- --threshold=80

echo "✅ Pre-commit checks passed!"
```

---

**Status**: ✅ **READY FOR IMPLEMENTATION**
**Usage**: Copy templates and adapt to specific components/features
**Maintenance**: Update templates as patterns evolve