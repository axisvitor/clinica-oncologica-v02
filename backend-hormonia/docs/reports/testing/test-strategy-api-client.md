# Comprehensive Test Strategy: API Client Architecture

## Executive Summary

This document outlines the comprehensive testing strategy for the new API client architecture, focusing on:
- **lib/api-client.ts**: TypeScript QuizApiClient class
- **hooks/use-quiz-session.ts**: React hook for quiz session management
- **Backend CSRF/CORS**: Python FastAPI security layer

**Target Coverage**: 90%+ code coverage across all layers
**Test Pyramid**: 60% Unit, 30% Integration, 10% E2E
**Security Focus**: Zero-trust security validation

---

## 1. Unit Testing Strategy

### 1.1 QuizApiClient Class Tests (`lib/api-client.ts`)

**Location**: `/tests/frontend/unit/api-client.test.ts`

#### Test Categories

##### A. Constructor & Initialization
```typescript
describe('QuizApiClient - Initialization', () => {
  it('should initialize with baseUrl', () => {
    const client = new QuizApiClient('https://api.example.com');
    expect(client).toBeDefined();
    expect(client['baseUrl']).toBe('https://api.example.com');
  });

  it('should initialize in-memory token storage (null)', () => {
    const client = new QuizApiClient('https://api.example.com');
    expect(client['csrfToken']).toBeNull();
  });

  it('should initialize AbortController timeout to 15000ms', () => {
    const client = new QuizApiClient('https://api.example.com');
    expect(client['timeout']).toBe(15000);
  });

  it('should throw error if baseUrl is invalid', () => {
    expect(() => new QuizApiClient('')).toThrow();
    expect(() => new QuizApiClient('not-a-url')).toThrow();
  });
});
```

##### B. CSRF Token Handshake
```typescript
describe('QuizApiClient - CSRF Token Handshake', () => {
  it('should fetch CSRF token from /api/v2/auth/csrf-token', async () => {
    const mockFetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ csrf_token: 'test-token-123.abc.def' }),
    });
    global.fetch = mockFetch;

    const client = new QuizApiClient('https://api.example.com');
    await client.fetchCsrfToken();

    expect(mockFetch).toHaveBeenCalledWith(
      'https://api.example.com/api/v2/auth/csrf-token',
      expect.objectContaining({
        credentials: 'include',
        method: 'GET',
      })
    );
  });

  it('should store CSRF token in memory only (no localStorage)', async () => {
    const mockFetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ csrf_token: 'test-token-123.abc.def' }),
    });
    global.fetch = mockFetch;

    const client = new QuizApiClient('https://api.example.com');
    await client.fetchCsrfToken();

    expect(client['csrfToken']).toBe('test-token-123.abc.def');
    expect(localStorage.getItem).not.toHaveBeenCalled();
  });

  it('should validate CSRF token format (timestamp.random.signature)', async () => {
    const mockFetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ csrf_token: 'invalid-format' }),
    });
    global.fetch = mockFetch;

    const client = new QuizApiClient('https://api.example.com');

    await expect(client.fetchCsrfToken()).rejects.toThrow('Invalid CSRF token format');
  });

  it('should retry CSRF fetch on network failure (3 retries)', async () => {
    const mockFetch = jest.fn()
      .mockRejectedValueOnce(new Error('Network error'))
      .mockRejectedValueOnce(new Error('Network error'))
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ csrf_token: 'test-token-123.abc.def' }),
      });
    global.fetch = mockFetch;

    const client = new QuizApiClient('https://api.example.com');
    await client.fetchCsrfToken();

    expect(mockFetch).toHaveBeenCalledTimes(3);
  });

  it('should throw after max retries exceeded', async () => {
    const mockFetch = jest.fn().mockRejectedValue(new Error('Network error'));
    global.fetch = mockFetch;

    const client = new QuizApiClient('https://api.example.com');

    await expect(client.fetchCsrfToken()).rejects.toThrow('Max retries exceeded');
    expect(mockFetch).toHaveBeenCalledTimes(3);
  });
});
```

##### C. AbortController Timeout Testing
```typescript
describe('QuizApiClient - AbortController Timeout', () => {
  it('should abort request after 15 seconds', async () => {
    jest.useFakeTimers();

    const mockFetch = jest.fn(() => new Promise((resolve) => {
      // Never resolves (simulates hanging request)
    }));
    global.fetch = mockFetch;

    const client = new QuizApiClient('https://api.example.com');
    const requestPromise = client.get('/api/endpoint');

    jest.advanceTimersByTime(15000);

    await expect(requestPromise).rejects.toThrow('Request timeout');
    expect(mockFetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        signal: expect.any(AbortSignal),
      })
    );

    jest.useRealTimers();
  });

  it('should cleanup AbortController after successful request', async () => {
    const mockFetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ data: 'success' }),
    });
    global.fetch = mockFetch;

    const client = new QuizApiClient('https://api.example.com');
    await client.get('/api/endpoint');

    // Internal AbortController should be nullified
    expect(client['currentController']).toBeNull();
  });

  it('should support custom timeout override', async () => {
    jest.useFakeTimers();

    const client = new QuizApiClient('https://api.example.com', { timeout: 5000 });
    const mockFetch = jest.fn(() => new Promise(() => {}));
    global.fetch = mockFetch;

    const requestPromise = client.get('/api/endpoint');
    jest.advanceTimersByTime(5000);

    await expect(requestPromise).rejects.toThrow('Request timeout');

    jest.useRealTimers();
  });
});
```

##### D. Credentials: 'include' Cookie Handling
```typescript
describe('QuizApiClient - Cookie Handling', () => {
  it('should send credentials: include on all requests', async () => {
    const mockFetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ data: 'success' }),
    });
    global.fetch = mockFetch;

    const client = new QuizApiClient('https://api.example.com');
    await client.get('/api/endpoint');

    expect(mockFetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        credentials: 'include',
      })
    );
  });

  it('should include CSRF token in X-CSRF-Token header', async () => {
    const mockFetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ data: 'success' }),
    });
    global.fetch = mockFetch;

    const client = new QuizApiClient('https://api.example.com');
    client['csrfToken'] = 'test-token-123.abc.def';

    await client.post('/api/endpoint', { data: 'test' });

    expect(mockFetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        headers: expect.objectContaining({
          'X-CSRF-Token': 'test-token-123.abc.def',
        }),
      })
    );
  });

  it('should NOT store cookies in localStorage or sessionStorage', async () => {
    const localStorageSpy = jest.spyOn(Storage.prototype, 'setItem');
    const sessionStorageSpy = jest.spyOn(Storage.prototype, 'setItem');

    const mockFetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ data: 'success' }),
      headers: new Headers({
        'Set-Cookie': 'session=abc123; HttpOnly; Secure; SameSite=Strict',
      }),
    });
    global.fetch = mockFetch;

    const client = new QuizApiClient('https://api.example.com');
    await client.get('/api/endpoint');

    expect(localStorageSpy).not.toHaveBeenCalled();
    expect(sessionStorageSpy).not.toHaveBeenCalled();
  });
});
```

##### E. Error Handling Scenarios
```typescript
describe('QuizApiClient - Error Handling', () => {
  it('should throw on 403 Forbidden (CSRF validation failed)', async () => {
    const mockFetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ detail: 'CSRF validation failed' }),
    });
    global.fetch = mockFetch;

    const client = new QuizApiClient('https://api.example.com');

    await expect(client.post('/api/endpoint', {})).rejects.toThrow('CSRF validation failed');
  });

  it('should refetch CSRF token on 403 and retry once', async () => {
    const mockFetch = jest.fn()
      .mockResolvedValueOnce({ // First POST fails with 403
        ok: false,
        status: 403,
        json: async () => ({ detail: 'CSRF validation failed' }),
      })
      .mockResolvedValueOnce({ // CSRF token refetch succeeds
        ok: true,
        json: async () => ({ csrf_token: 'new-token-456.xyz.uvw' }),
      })
      .mockResolvedValueOnce({ // Retry POST succeeds
        ok: true,
        json: async () => ({ data: 'success' }),
      });
    global.fetch = mockFetch;

    const client = new QuizApiClient('https://api.example.com');
    await client.post('/api/endpoint', {});

    expect(mockFetch).toHaveBeenCalledTimes(3);
  });

  it('should throw on 401 Unauthorized (not authenticated)', async () => {
    const mockFetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: 'Not authenticated' }),
    });
    global.fetch = mockFetch;

    const client = new QuizApiClient('https://api.example.com');

    await expect(client.get('/api/endpoint')).rejects.toThrow('Not authenticated');
  });

  it('should handle network errors gracefully', async () => {
    const mockFetch = jest.fn().mockRejectedValue(new TypeError('Failed to fetch'));
    global.fetch = mockFetch;

    const client = new QuizApiClient('https://api.example.com');

    await expect(client.get('/api/endpoint')).rejects.toThrow('Network error');
  });

  it('should parse JSON error responses', async () => {
    const mockFetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({
        detail: [
          { loc: ['body', 'email'], msg: 'Invalid email format' }
        ]
      }),
    });
    global.fetch = mockFetch;

    const client = new QuizApiClient('https://api.example.com');

    try {
      await client.post('/api/endpoint', { email: 'invalid' });
    } catch (error) {
      expect(error.message).toContain('Invalid email format');
      expect(error.validationErrors).toBeDefined();
    }
  });
});
```

##### F. Direct Python Backend Connection
```typescript
describe('QuizApiClient - Backend Connection', () => {
  it('should connect to Python FastAPI backend URL', async () => {
    const mockFetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ version: 'v2', framework: 'FastAPI' }),
    });
    global.fetch = mockFetch;

    const client = new QuizApiClient('http://localhost:8000');
    await client.get('/api/v2/health');

    expect(mockFetch).toHaveBeenCalledWith(
      'http://localhost:8000/api/v2/health',
      expect.any(Object)
    );
  });

  it('should handle CORS preflight OPTIONS correctly', async () => {
    const mockFetch = jest.fn()
      .mockResolvedValueOnce({ // OPTIONS preflight
        ok: true,
        status: 200,
        headers: new Headers({
          'Access-Control-Allow-Origin': 'http://localhost:5173',
          'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE',
          'Access-Control-Allow-Credentials': 'true',
        }),
      })
      .mockResolvedValueOnce({ // Actual POST
        ok: true,
        json: async () => ({ data: 'success' }),
      });
    global.fetch = mockFetch;

    const client = new QuizApiClient('http://localhost:8000');
    await client.post('/api/v2/endpoint', {});

    // Verify CORS headers are respected
    expect(mockFetch).toHaveBeenCalledTimes(1); // Browser handles preflight
  });

  it('should validate backend response schema', async () => {
    const mockFetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ unexpected: 'schema' }),
    });
    global.fetch = mockFetch;

    const client = new QuizApiClient('http://localhost:8000');

    // If using Zod or similar for validation
    await expect(client.get('/api/v2/endpoint')).rejects.toThrow('Invalid response schema');
  });
});
```

---

### 1.2 React Hook Tests (`hooks/use-quiz-session.ts`)

**Location**: `/tests/frontend/unit/use-quiz-session.test.ts`

#### Test Categories

##### A. Hook Initialization
```typescript
import { renderHook } from '@testing-library/react';
import { useQuizSession } from '@/hooks/use-quiz-session';
import { MemoryRouter } from 'react-router-dom';

describe('useQuizSession - Initialization', () => {
  it('should initialize with null session', () => {
    const wrapper = ({ children }) => (
      <MemoryRouter>{children}</MemoryRouter>
    );

    const { result } = renderHook(() => useQuizSession(), { wrapper });

    expect(result.current.session).toBeNull();
    expect(result.current.loading).toBe(true);
    expect(result.current.error).toBeNull();
  });

  it('should extract session_id from URL searchParams', () => {
    const wrapper = ({ children }) => (
      <MemoryRouter initialEntries={['/?session_id=abc-123']}>
        {children}
      </MemoryRouter>
    );

    const { result } = renderHook(() => useQuizSession(), { wrapper });

    // Hook should detect session_id=abc-123
    expect(result.current.sessionId).toBe('abc-123');
  });

  it('should handle missing session_id gracefully', () => {
    const wrapper = ({ children }) => (
      <MemoryRouter initialEntries={['/']}>
        {children}
      </MemoryRouter>
    );

    const { result } = renderHook(() => useQuizSession(), { wrapper });

    expect(result.current.sessionId).toBeNull();
    expect(result.current.error).toBe('Missing session_id parameter');
  });
});
```

##### B. useRef Double Execution Prevention
```typescript
describe('useQuizSession - Double Execution Prevention', () => {
  it('should prevent duplicate API calls with useRef', async () => {
    const mockFetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ session_id: 'abc-123', status: 'active' }),
    });
    global.fetch = mockFetch;

    const wrapper = ({ children }) => (
      <MemoryRouter initialEntries={['/?session_id=abc-123']}>
        {children}
      </MemoryRouter>
    );

    const { result, rerender } = renderHook(() => useQuizSession(), { wrapper });

    // Wait for initial effect
    await waitFor(() => expect(result.current.loading).toBe(false));

    // Force React 18 double render
    rerender();

    // Should still only call fetch once
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it('should use useRef.current as execution guard', () => {
    const wrapper = ({ children }) => (
      <MemoryRouter>{children}</MemoryRouter>
    );

    const { result } = renderHook(() => useQuizSession(), { wrapper });

    // Internal ref should prevent double execution
    // This tests the implementation detail
    expect(result.current['hasInitialized'].current).toBe(true);
  });
});
```

##### C. useSearchParams Integration
```typescript
describe('useQuizSession - useSearchParams Integration', () => {
  it('should react to searchParams changes', async () => {
    const wrapper = ({ children }) => (
      <MemoryRouter initialEntries={['/?session_id=abc-123']}>
        {children}
      </MemoryRouter>
    );

    const { result } = renderHook(() => useQuizSession(), { wrapper });

    await waitFor(() => expect(result.current.sessionId).toBe('abc-123'));

    // Simulate URL change
    act(() => {
      // Change to new session_id
      window.history.pushState({}, '', '/?session_id=xyz-789');
    });

    await waitFor(() => expect(result.current.sessionId).toBe('xyz-789'));
  });

  it('should handle multiple search parameters', () => {
    const wrapper = ({ children }) => (
      <MemoryRouter initialEntries={['/?session_id=abc-123&quiz_type=monthly&lang=pt']}>
        {children}
      </MemoryRouter>
    );

    const { result } = renderHook(() => useQuizSession(), { wrapper });

    expect(result.current.sessionId).toBe('abc-123');
    // Other params should not interfere
  });
});
```

##### D. State Management Testing
```typescript
describe('useQuizSession - State Management', () => {
  it('should manage loading state correctly', async () => {
    const mockFetch = jest.fn(() => new Promise(resolve =>
      setTimeout(() => resolve({
        ok: true,
        json: async () => ({ session_id: 'abc-123' }),
      }), 100)
    ));
    global.fetch = mockFetch;

    const wrapper = ({ children }) => (
      <MemoryRouter initialEntries={['/?session_id=abc-123']}>
        {children}
      </MemoryRouter>
    );

    const { result } = renderHook(() => useQuizSession(), { wrapper });

    expect(result.current.loading).toBe(true);

    await waitFor(() => expect(result.current.loading).toBe(false), { timeout: 200 });
  });

  it('should update session state on successful fetch', async () => {
    const mockSession = {
      session_id: 'abc-123',
      status: 'active',
      expires_at: '2025-12-31T23:59:59Z',
    };

    const mockFetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => mockSession,
    });
    global.fetch = mockFetch;

    const wrapper = ({ children }) => (
      <MemoryRouter initialEntries={['/?session_id=abc-123']}>
        {children}
      </MemoryRouter>
    );

    const { result } = renderHook(() => useQuizSession(), { wrapper });

    await waitFor(() => {
      expect(result.current.session).toEqual(mockSession);
      expect(result.current.error).toBeNull();
    });
  });

  it('should set error state on failed fetch', async () => {
    const mockFetch = jest.fn().mockRejectedValue(new Error('Network error'));
    global.fetch = mockFetch;

    const wrapper = ({ children }) => (
      <MemoryRouter initialEntries={['/?session_id=abc-123']}>
        {children}
      </MemoryRouter>
    );

    const { result } = renderHook(() => useQuizSession(), { wrapper });

    await waitFor(() => {
      expect(result.current.session).toBeNull();
      expect(result.current.error).toBe('Network error');
      expect(result.current.loading).toBe(false);
    });
  });
});
```

##### E. Error Boundary Testing
```typescript
describe('useQuizSession - Error Boundary', () => {
  it('should throw error to ErrorBoundary on critical failure', () => {
    const mockFetch = jest.fn().mockRejectedValue(new Error('Critical error'));
    global.fetch = mockFetch;

    const ErrorBoundary = ({ children }) => {
      const [hasError, setHasError] = React.useState(false);

      if (hasError) {
        return <div>Error caught by boundary</div>;
      }

      return children;
    };

    const wrapper = ({ children }) => (
      <MemoryRouter initialEntries={['/?session_id=abc-123']}>
        <ErrorBoundary>
          {children}
        </ErrorBoundary>
      </MemoryRouter>
    );

    const { result } = renderHook(() => useQuizSession(), { wrapper });

    // Should propagate error to boundary
    expect(result.error).toBeDefined();
  });

  it('should recover from errors on retry', async () => {
    const mockFetch = jest.fn()
      .mockRejectedValueOnce(new Error('Temporary error'))
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ session_id: 'abc-123' }),
      });
    global.fetch = mockFetch;

    const wrapper = ({ children }) => (
      <MemoryRouter initialEntries={['/?session_id=abc-123']}>
        {children}
      </MemoryRouter>
    );

    const { result } = renderHook(() => useQuizSession(), { wrapper });

    await waitFor(() => expect(result.current.error).toBeDefined());

    // Trigger retry
    act(() => {
      result.current.retry();
    });

    await waitFor(() => {
      expect(result.current.session).toBeDefined();
      expect(result.current.error).toBeNull();
    });
  });
});
```

---

## 2. Integration Testing Strategy

### 2.1 Frontend → Backend CSRF Token Flow

**Location**: `/tests/integration/csrf-token-flow.test.ts`

```typescript
describe('Integration: CSRF Token Lifecycle', () => {
  let apiClient: QuizApiClient;
  let testServer: TestServer;

  beforeAll(async () => {
    testServer = await startTestServer({
      environment: 'testing',
      port: 8888,
    });
    apiClient = new QuizApiClient('http://localhost:8888');
  });

  afterAll(async () => {
    await testServer.close();
  });

  it('should complete full CSRF handshake: fetch → validate → request', async () => {
    // Step 1: Fetch CSRF token
    await apiClient.fetchCsrfToken();
    expect(apiClient['csrfToken']).toBeTruthy();

    // Step 2: Make authenticated request
    const response = await apiClient.post('/api/v2/quiz/submit', {
      answers: [{ question_id: 1, answer: 'A' }],
    });

    expect(response).toBeDefined();
    expect(response.success).toBe(true);
  });

  it('should receive HttpOnly cookie from backend', async () => {
    const cookieJar = new Map<string, string>();

    // Override fetch to capture Set-Cookie
    const originalFetch = global.fetch;
    global.fetch = jest.fn(async (url, options) => {
      const response = await originalFetch(url, options);
      const setCookie = response.headers.get('Set-Cookie');
      if (setCookie) {
        const [name, value] = setCookie.split(';')[0].split('=');
        cookieJar.set(name, value);
      }
      return response;
    });

    await apiClient.fetchCsrfToken();

    // Should have received fastapi-csrf-token cookie
    expect(cookieJar.has('fastapi-csrf-token')).toBe(true);
    expect(cookieJar.get('fastapi-csrf-token')).toBeTruthy();

    global.fetch = originalFetch;
  });

  it('should validate cookie attributes: HttpOnly, Secure, SameSite=Strict', async () => {
    const response = await fetch('http://localhost:8888/api/v2/auth/csrf-token', {
      credentials: 'include',
    });

    const setCookie = response.headers.get('Set-Cookie');

    expect(setCookie).toContain('HttpOnly');
    expect(setCookie).toContain('SameSite=Strict');
    // In production, should also have Secure
    if (process.env.NODE_ENV === 'production') {
      expect(setCookie).toContain('Secure');
    }
  });

  it('should reject request with missing CSRF token', async () => {
    // Reset token to simulate missing token
    apiClient['csrfToken'] = null;

    await expect(
      apiClient.post('/api/v2/quiz/submit', {})
    ).rejects.toThrow('Missing CSRF token');
  });

  it('should reject request with invalid CSRF token signature', async () => {
    // Set invalid token
    apiClient['csrfToken'] = 'invalid.token.signature';

    const response = await apiClient.post('/api/v2/quiz/submit', {});

    expect(response.status).toBe(403);
    expect(response.detail).toContain('CSRF validation failed');
  });

  it('should handle CSRF token expiration and refetch', async () => {
    // Set token that will expire
    apiClient['csrfToken'] = await generateExpiredToken();

    // First request should fail with 403
    // Client should automatically refetch and retry
    const response = await apiClient.post('/api/v2/quiz/submit', {});

    expect(response.success).toBe(true);
    // Token should have been refreshed
    expect(apiClient['csrfToken']).not.toBe('expired-token');
  });
});
```

### 2.2 Session Management Integration

**Location**: `/tests/integration/session-management.test.ts`

```typescript
describe('Integration: Quiz Session Management', () => {
  it('should create session → fetch session → submit answers → validate', async () => {
    const apiClient = new QuizApiClient('http://localhost:8888');

    // Step 1: Create session
    const session = await apiClient.post('/api/v2/quiz/session/create', {
      quiz_type: 'monthly',
      patient_id: 'test-patient-123',
    });
    expect(session.session_id).toBeDefined();

    // Step 2: Fetch session via hook
    const wrapper = ({ children }) => (
      <MemoryRouter initialEntries={[`/?session_id=${session.session_id}`]}>
        {children}
      </MemoryRouter>
    );

    const { result } = renderHook(() => useQuizSession(), { wrapper });

    await waitFor(() => {
      expect(result.current.session).toBeDefined();
      expect(result.current.session.session_id).toBe(session.session_id);
    });

    // Step 3: Submit answers
    const submitResponse = await apiClient.post('/api/v2/quiz/submit', {
      session_id: session.session_id,
      answers: [{ question_id: 1, answer: 'A' }],
    });

    expect(submitResponse.success).toBe(true);
  });

  it('should handle concurrent session requests without race conditions', async () => {
    const apiClient = new QuizApiClient('http://localhost:8888');
    const sessionId = 'test-session-concurrent';

    // Simulate concurrent requests
    const requests = Array(10).fill(null).map(() =>
      apiClient.get(`/api/v2/quiz/session/${sessionId}`)
    );

    const responses = await Promise.all(requests);

    // All should succeed with same session data
    expect(responses.every(r => r.session_id === sessionId)).toBe(true);
  });
});
```

### 2.3 Cookie Handling Integration

**Location**: `/tests/integration/cookie-handling.test.ts`

```python
# Backend Python test
import pytest
from fastapi.testclient import TestClient
from app.main import app

class TestCookieHandling:
    """Test cookie security attributes and browser interaction."""

    def test_csrf_cookie_attributes_httponly_secure_samesite(self):
        """CSRF cookie should have HttpOnly, Secure, SameSite=Strict."""
        client = TestClient(app)

        response = client.get("/api/v2/auth/csrf-token")

        assert response.status_code == 200

        # Check Set-Cookie header
        set_cookie = response.headers.get("set-cookie")
        assert "fastapi-csrf-token=" in set_cookie
        assert "HttpOnly" in set_cookie
        assert "SameSite=Strict" in set_cookie

        # In production, should also have Secure
        if app.state.environment == "production":
            assert "Secure" in set_cookie

    def test_cookie_sent_with_credentials_include(self):
        """Browser should send cookie with credentials: 'include'."""
        client = TestClient(app)

        # First request: get CSRF token and cookie
        token_response = client.get("/api/v2/auth/csrf-token")
        csrf_token = token_response.json()["csrf_token"]
        cookies = token_response.cookies

        # Second request: cookie should be sent automatically
        response = client.post(
            "/api/v2/quiz/submit",
            json={"answers": []},
            headers={"X-CSRF-Token": csrf_token},
            cookies=cookies,
        )

        # Should validate successfully
        assert response.status_code in [200, 201]

    def test_cookie_not_accessible_via_javascript(self):
        """HttpOnly cookie should not be accessible via document.cookie."""
        # This is tested via E2E browser test
        # Frontend unit test verifies no localStorage/sessionStorage usage
        pass
```

---

## 3. Security Testing Strategy

### 3.1 XSS Prevention Validation

**Location**: `/tests/security/xss-prevention.test.ts`

```typescript
describe('Security: XSS Prevention', () => {
  it('should NOT store any sensitive data in DOM storage', () => {
    const localStorageSpy = jest.spyOn(Storage.prototype, 'setItem');
    const sessionStorageSpy = jest.spyOn(Storage.prototype, 'setItem');

    const apiClient = new QuizApiClient('https://api.example.com');
    apiClient.fetchCsrfToken();

    // Should never call localStorage or sessionStorage
    expect(localStorageSpy).not.toHaveBeenCalled();
    expect(sessionStorageSpy).not.toHaveBeenCalled();
  });

  it('should sanitize all user inputs before API submission', async () => {
    const apiClient = new QuizApiClient('https://api.example.com');

    const maliciousInput = {
      answer: '<script>alert("XSS")</script>',
      comment: '<img src=x onerror=alert("XSS")>',
    };

    const mockFetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ success: true }),
    });
    global.fetch = mockFetch;

    await apiClient.post('/api/v2/quiz/submit', maliciousInput);

    // Verify sanitization occurred
    const requestBody = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(requestBody.answer).not.toContain('<script>');
    expect(requestBody.comment).not.toContain('<img');
  });

  it('should escape HTML in rendered quiz questions', () => {
    const maliciousQuestion = {
      text: '<script>alert("XSS")</script>What is 2+2?',
    };

    // Component should escape HTML
    const { container } = render(<QuizQuestion question={maliciousQuestion} />);

    expect(container.textContent).toContain('&lt;script&gt;');
    expect(container.innerHTML).not.toContain('<script>');
  });
});
```

### 3.2 CSRF Protection Validation

**Location**: `/tests/security/csrf-protection.test.ts`

```python
# Backend Python test
class TestCsrfProtection:
    """Validate CSRF protection mechanisms."""

    def test_reject_post_without_csrf_token(self, client: TestClient):
        """POST request without CSRF token should be rejected."""
        response = client.post(
            "/api/v2/quiz/submit",
            json={"answers": []},
        )

        assert response.status_code == 403
        assert "CSRF" in response.json()["detail"]

    def test_reject_post_with_invalid_csrf_token(self, client: TestClient):
        """POST with invalid CSRF token should be rejected."""
        response = client.post(
            "/api/v2/quiz/submit",
            json={"answers": []},
            headers={"X-CSRF-Token": "invalid-token-format"},
        )

        assert response.status_code == 403

    def test_reject_csrf_token_without_matching_cookie(self, client: TestClient):
        """Double Submit Cookie pattern: token must match cookie."""
        # Get valid token
        token_response = client.get("/api/v2/auth/csrf-token")
        csrf_token = token_response.json()["csrf_token"]

        # Send token but wrong cookie
        response = client.post(
            "/api/v2/quiz/submit",
            json={"answers": []},
            headers={"X-CSRF-Token": csrf_token},
            cookies={"fastapi-csrf-token": "different-token"},
        )

        assert response.status_code == 403
        assert "mismatch" in response.json()["detail"].lower()

    def test_csrf_token_signature_validation_hmac_sha256(self, client: TestClient):
        """CSRF token signature should use HMAC-SHA256."""
        import hmac
        import hashlib

        token_response = client.get("/api/v2/auth/csrf-token")
        csrf_token = token_response.json()["csrf_token"]

        # Parse token
        timestamp, random_data, signature = csrf_token.split(".")

        # Verify signature format (64 hex chars = SHA256)
        assert len(signature) == 64
        assert all(c in "0123456789abcdef" for c in signature)

        # Verify HMAC signature
        from app.config.settings import settings
        data = f"{timestamp}.{random_data}"
        expected_sig = hmac.new(
            settings.SECRET_KEY.encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()

        assert hmac.compare_digest(expected_sig, signature)

    def test_csrf_token_expiration_after_1_hour(self, client: TestClient):
        """CSRF tokens should expire after 1 hour."""
        import time
        from unittest.mock import patch

        # Get token
        token_response = client.get("/api/v2/auth/csrf-token")
        csrf_token = token_response.json()["csrf_token"]
        cookies = token_response.cookies

        # Mock time to 2 hours in future
        with patch('time.time', return_value=time.time() + 7200):
            response = client.post(
                "/api/v2/quiz/submit",
                json={"answers": []},
                headers={"X-CSRF-Token": csrf_token},
                cookies=cookies,
            )

            assert response.status_code == 403
            assert "expired" in response.json()["detail"].lower()
```

### 3.3 Cookie Security Validation

**Location**: `/tests/security/cookie-security.test.ts`

```typescript
describe('Security: Cookie Attributes', () => {
  it('should verify HttpOnly attribute prevents JavaScript access', async () => {
    // This is inherently tested by browser, but we verify the header
    const response = await fetch('http://localhost:8888/api/v2/auth/csrf-token', {
      credentials: 'include',
    });

    const setCookie = response.headers.get('Set-Cookie');
    expect(setCookie).toMatch(/HttpOnly/i);

    // Verify document.cookie cannot access it
    expect(document.cookie).not.toContain('fastapi-csrf-token');
  });

  it('should verify Secure attribute requires HTTPS in production', async () => {
    if (process.env.NODE_ENV === 'production') {
      const response = await fetch('https://api.production.com/api/v2/auth/csrf-token', {
        credentials: 'include',
      });

      const setCookie = response.headers.get('Set-Cookie');
      expect(setCookie).toMatch(/Secure/i);
    }
  });

  it('should verify SameSite=Strict prevents CSRF attacks', async () => {
    const response = await fetch('http://localhost:8888/api/v2/auth/csrf-token', {
      credentials: 'include',
    });

    const setCookie = response.headers.get('Set-Cookie');
    expect(setCookie).toMatch(/SameSite=Strict/i);
  });

  it('should reject cross-origin requests without proper CORS', async () => {
    // Simulate request from different origin
    const response = await fetch('http://localhost:8888/api/v2/quiz/submit', {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Origin': 'https://malicious-site.com',
      },
    });

    // Should be blocked by CORS
    expect(response.status).toBe(403);
  });
});
```

### 3.4 Network Request Validation

**Location**: `/tests/security/network-validation.test.ts`

```typescript
describe('Security: Network Request Validation', () => {
  it('should always use HTTPS in production', () => {
    if (process.env.NODE_ENV === 'production') {
      const apiClient = new QuizApiClient(process.env.API_URL);

      expect(apiClient['baseUrl']).toMatch(/^https:\/\//);

      // Verify all requests use HTTPS
      const mockFetch = jest.fn();
      global.fetch = mockFetch;

      apiClient.get('/api/endpoint');

      const requestUrl = mockFetch.mock.calls[0][0];
      expect(requestUrl).toMatch(/^https:\/\//);
    }
  });

  it('should validate SSL certificates in production', async () => {
    if (process.env.NODE_ENV === 'production') {
      const response = await fetch(process.env.API_URL + '/api/v2/health');

      // If SSL is invalid, fetch will throw
      expect(response.ok).toBe(true);
    }
  });

  it('should reject requests with invalid Content-Type', async () => {
    const apiClient = new QuizApiClient('http://localhost:8888');

    const mockFetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 415,
      json: async () => ({ detail: 'Unsupported Media Type' }),
    });
    global.fetch = mockFetch;

    await expect(
      apiClient.post('/api/v2/quiz/submit', {}, {
        headers: { 'Content-Type': 'text/plain' },
      })
    ).rejects.toThrow('Unsupported Media Type');
  });

  it('should sanitize request headers', async () => {
    const apiClient = new QuizApiClient('http://localhost:8888');

    const mockFetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({}),
    });
    global.fetch = mockFetch;

    await apiClient.get('/api/endpoint', {
      headers: {
        'X-Malicious': '<script>alert("XSS")</script>',
      },
    });

    const requestHeaders = mockFetch.mock.calls[0][1].headers;

    // Header values should be sanitized or rejected
    expect(requestHeaders['X-Malicious']).not.toContain('<script>');
  });
});
```

---

## 4. Performance & Timeout Testing

### 4.1 Timeout Scenarios

**Location**: `/tests/performance/timeout-scenarios.test.ts`

```typescript
describe('Performance: Timeout Handling', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('should timeout after 15 seconds by default', async () => {
    const apiClient = new QuizApiClient('http://localhost:8888');

    const mockFetch = jest.fn(() => new Promise(() => {})); // Never resolves
    global.fetch = mockFetch;

    const requestPromise = apiClient.get('/api/slow-endpoint');

    jest.advanceTimersByTime(15000);

    await expect(requestPromise).rejects.toThrow('Request timeout after 15000ms');
  });

  it('should allow custom timeout configuration', async () => {
    const apiClient = new QuizApiClient('http://localhost:8888', { timeout: 5000 });

    const mockFetch = jest.fn(() => new Promise(() => {}));
    global.fetch = mockFetch;

    const requestPromise = apiClient.get('/api/endpoint');

    jest.advanceTimersByTime(5000);

    await expect(requestPromise).rejects.toThrow('Request timeout');
  });

  it('should cleanup AbortController on timeout', async () => {
    const apiClient = new QuizApiClient('http://localhost:8888');

    const mockFetch = jest.fn(() => new Promise(() => {}));
    global.fetch = mockFetch;

    const requestPromise = apiClient.get('/api/endpoint');

    jest.advanceTimersByTime(15000);

    await expect(requestPromise).rejects.toThrow();

    // Controller should be cleaned up
    expect(apiClient['currentController']).toBeNull();
  });

  it('should handle slow network gracefully (simulate 3G)', async () => {
    const apiClient = new QuizApiClient('http://localhost:8888', { timeout: 30000 });

    const mockFetch = jest.fn(() => new Promise((resolve) => {
      setTimeout(() => resolve({
        ok: true,
        json: async () => ({ data: 'success' }),
      }), 5000); // Slow response
    }));
    global.fetch = mockFetch;

    const response = await apiClient.get('/api/endpoint');

    expect(response.data).toBe('success');
  });
});
```

### 4.2 Performance Benchmarks

**Location**: `/tests/performance/benchmarks.test.ts`

```typescript
describe('Performance: Benchmarks', () => {
  it('should complete CSRF token fetch under 100ms (local)', async () => {
    const apiClient = new QuizApiClient('http://localhost:8888');

    const start = performance.now();
    await apiClient.fetchCsrfToken();
    const duration = performance.now() - start;

    expect(duration).toBeLessThan(100);
  });

  it('should handle 100 concurrent requests without memory leaks', async () => {
    const apiClient = new QuizApiClient('http://localhost:8888');
    await apiClient.fetchCsrfToken();

    const initialMemory = process.memoryUsage().heapUsed;

    const requests = Array(100).fill(null).map((_, i) =>
      apiClient.get(`/api/v2/quiz/question/${i}`)
    );

    await Promise.all(requests);

    global.gc(); // Force garbage collection

    const finalMemory = process.memoryUsage().heapUsed;
    const memoryIncrease = finalMemory - initialMemory;

    expect(memoryIncrease).toBeLessThan(10 * 1024 * 1024); // <10MB
  });

  it('should maintain <200ms p95 latency for API requests', async () => {
    const apiClient = new QuizApiClient('http://localhost:8888');
    await apiClient.fetchCsrfToken();

    const latencies: number[] = [];

    for (let i = 0; i < 100; i++) {
      const start = performance.now();
      await apiClient.get('/api/v2/quiz/question/1');
      latencies.push(performance.now() - start);
    }

    latencies.sort((a, b) => a - b);
    const p95 = latencies[Math.floor(latencies.length * 0.95)];

    expect(p95).toBeLessThan(200);
  });
});
```

---

## 5. End-to-End Testing Strategy

### 5.1 Full Frontend-Backend Flow

**Location**: `/tests/e2e/quiz-session-flow.spec.ts`

```typescript
import { test, expect } from '@playwright/test';

test.describe('E2E: Quiz Session Complete Flow', () => {
  test('should complete quiz from landing to submission', async ({ page }) => {
    // Step 1: Navigate to quiz landing page
    await page.goto('http://localhost:5173/quiz/monthly');

    // Step 2: Start quiz session
    await page.click('button:has-text("Iniciar Quiz")');

    // Wait for session creation
    await page.waitForURL(/session_id=/);

    const url = new URL(page.url());
    const sessionId = url.searchParams.get('session_id');
    expect(sessionId).toBeTruthy();

    // Step 3: Verify CSRF token was fetched
    const csrfCookie = await page.context().cookies();
    const csrfCookieValue = csrfCookie.find(c => c.name === 'fastapi-csrf-token');
    expect(csrfCookieValue).toBeDefined();
    expect(csrfCookieValue.httpOnly).toBe(true);
    expect(csrfCookieValue.sameSite).toBe('Strict');

    // Step 4: Answer quiz questions
    await page.click('[data-testid="answer-option-A"]');
    await page.click('button:has-text("Próxima")');

    await page.click('[data-testid="answer-option-B"]');
    await page.click('button:has-text("Próxima")');

    // Step 5: Submit quiz
    await page.click('button:has-text("Enviar Respostas")');

    // Step 6: Verify submission success
    await expect(page.locator('text=Quiz enviado com sucesso')).toBeVisible();

    // Verify no XSS vulnerabilities
    const pageContent = await page.content();
    expect(pageContent).not.toContain('<script>');
  });

  test('should handle session expiration gracefully', async ({ page }) => {
    // Mock expired session
    await page.goto('http://localhost:5173/quiz/monthly?session_id=expired-session-123');

    // Should show error message
    await expect(page.locator('text=Sessão expirada')).toBeVisible({timeout: 5000});

    // Should offer to restart
    await page.click('button:has-text("Reiniciar Quiz")');

    await page.waitForURL(/session_id=/);
    const url = new URL(page.url());
    const newSessionId = url.searchParams.get('session_id');
    expect(newSessionId).not.toBe('expired-session-123');
  });

  test('should recover from network errors with retry', async ({ page }) => {
    // Simulate network failure
    await page.route('**/api/v2/quiz/**', route => route.abort());

    await page.goto('http://localhost:5173/quiz/monthly?session_id=test-123');

    // Should show network error
    await expect(page.locator('text=Erro de conexão')).toBeVisible();

    // Re-enable network
    await page.unroute('**/api/v2/quiz/**');

    // Click retry
    await page.click('button:has-text("Tentar Novamente")');

    // Should load successfully
    await expect(page.locator('[data-testid="quiz-question"]')).toBeVisible();
  });
});
```

### 5.2 CSRF Attack Prevention E2E

**Location**: `/tests/e2e/csrf-prevention.spec.ts`

```typescript
test.describe('E2E: CSRF Attack Prevention', () => {
  test('should reject forged cross-origin POST requests', async ({ page, context }) => {
    // Step 1: User visits legitimate site and gets session
    await page.goto('http://localhost:5173/quiz/monthly');
    await page.click('button:has-text("Iniciar Quiz")');
    await page.waitForURL(/session_id=/);

    // Step 2: Attacker tries to submit from malicious site
    const maliciousPage = await context.newPage();
    await maliciousPage.goto('http://malicious-site.com/fake-form.html');

    // Attempt CSRF attack (submit to legitimate API)
    const response = await maliciousPage.evaluate(async () => {
      return fetch('http://localhost:8888/api/v2/quiz/submit', {
        method: 'POST',
        credentials: 'include', // Include cookies
        headers: {
          'Content-Type': 'application/json',
          // No CSRF token header (attacker doesn't have it)
        },
        body: JSON.stringify({ answers: [] }),
      }).then(r => ({ status: r.status, ok: r.ok }));
    });

    // Should be rejected with 403
    expect(response.status).toBe(403);
    expect(response.ok).toBe(false);
  });

  test('should prevent CSRF token theft via XSS', async ({ page }) => {
    // Ensure CSRF token is HttpOnly and not accessible via JavaScript
    await page.goto('http://localhost:5173/quiz/monthly');
    await page.click('button:has-text("Iniciar Quiz")');

    // Try to read CSRF cookie via JavaScript
    const csrfToken = await page.evaluate(() => {
      return document.cookie
        .split('; ')
        .find(row => row.startsWith('fastapi-csrf-token='));
    });

    // Should be undefined (HttpOnly prevents access)
    expect(csrfToken).toBeUndefined();
  });
});
```

---

## 6. Test Coverage Requirements

### Coverage Targets

| Component | Line Coverage | Branch Coverage | Function Coverage |
|-----------|---------------|-----------------|-------------------|
| lib/api-client.ts | 95%+ | 90%+ | 100% |
| hooks/use-quiz-session.ts | 95%+ | 90%+ | 100% |
| Backend CSRF middleware | 98%+ | 95%+ | 100% |
| Backend CORS middleware | 98%+ | 95%+ | 100% |
| Integration tests | 85%+ | 80%+ | 90%+ |
| E2E tests | 70%+ | 65%+ | 80%+ |

### Coverage Tools

**Frontend (TypeScript/React)**:
```json
{
  "jest": {
    "collectCoverageFrom": [
      "lib/**/*.{ts,tsx}",
      "hooks/**/*.{ts,tsx}",
      "!**/*.d.ts",
      "!**/node_modules/**"
    ],
    "coverageThresholds": {
      "global": {
        "statements": 90,
        "branches": 85,
        "functions": 90,
        "lines": 90
      }
    }
  }
}
```

**Backend (Python)**:
```ini
[tool.pytest.ini_options]
addopts = """
    --cov=app
    --cov-report=html
    --cov-report=term-missing
    --cov-fail-under=90
"""

[tool.coverage.run]
source = ["app"]
omit = [
    "*/tests/*",
    "*/migrations/*",
    "*/__pycache__/*"
]

[tool.coverage.report]
precision = 2
show_missing = true
skip_covered = false
```

### Coverage Validation Script

**Location**: `/tests/validate-coverage.sh`

```bash
#!/bin/bash
set -e

echo "🧪 Running Frontend Tests with Coverage..."
cd frontend
npm run test:coverage

echo "🧪 Running Backend Tests with Coverage..."
cd ../backend
pytest --cov --cov-report=json

echo "📊 Validating Coverage Thresholds..."
python -c "
import json
with open('coverage.json') as f:
    coverage = json.load(f)
    total_coverage = coverage['totals']['percent_covered']
    if total_coverage < 90:
        print(f'❌ Coverage {total_coverage}% is below 90% threshold')
        exit(1)
    print(f'✅ Coverage {total_coverage}% meets threshold')
"

echo "✅ All coverage requirements met!"
```

---

## 7. Test File Structure

```
backend-hormonia/
├── tests/
│   ├── conftest.py (existing)
│   ├── pytest.ini (existing)
│   │
│   ├── unit/
│   │   ├── test_api_client.py (Python unit tests if needed)
│   │   └── ...
│   │
│   ├── integration/
│   │   ├── test_csrf_token_flow.py
│   │   ├── test_session_management.py
│   │   ├── test_cookie_handling.py
│   │   └── test_cors_integration.py
│   │
│   ├── security/ (existing)
│   │   ├── test_cors.py (existing)
│   │   ├── test_csrf.py (existing)
│   │   ├── test_xss_prevention.py (new)
│   │   ├── test_cookie_security.py (new)
│   │   └── test_network_validation.py (new)
│   │
│   ├── performance/
│   │   ├── test_timeout_scenarios.py
│   │   ├── test_benchmarks.py
│   │   └── test_load.py
│   │
│   ├── e2e/
│   │   ├── test_quiz_session_flow.py (Playwright)
│   │   ├── test_csrf_prevention.py (Playwright)
│   │   └── test_browser_integration.py (Playwright)
│   │
│   └── fixtures/
│       ├── api_client_fixtures.py
│       ├── csrf_fixtures.py
│       └── session_fixtures.py

frontend/ (separate repository or monorepo)
├── tests/
│   ├── unit/
│   │   ├── api-client.test.ts
│   │   └── use-quiz-session.test.ts
│   │
│   ├── integration/
│   │   ├── csrf-token-flow.test.ts
│   │   └── session-management.test.ts
│   │
│   ├── security/
│   │   ├── xss-prevention.test.ts
│   │   ├── cookie-security.test.ts
│   │   └── network-validation.test.ts
│   │
│   ├── performance/
│   │   ├── timeout-scenarios.test.ts
│   │   └── benchmarks.test.ts
│   │
│   └── e2e/
│       ├── quiz-session-flow.spec.ts (Playwright)
│       └── csrf-prevention.spec.ts (Playwright)
```

---

## 8. Test Execution Plan

### 8.1 Local Development

```bash
# Frontend
cd frontend
npm run test              # Run all tests
npm run test:watch        # Watch mode
npm run test:coverage     # With coverage
npm run test:unit         # Unit tests only
npm run test:integration  # Integration tests only

# Backend
cd backend
pytest                    # Run all tests
pytest --cov              # With coverage
pytest -m unit            # Unit tests only
pytest -m integration     # Integration tests only
pytest -m security        # Security tests only
```

### 8.2 CI/CD Pipeline

**GitHub Actions**: `.github/workflows/test.yml`

```yaml
name: Test Suite

on: [push, pull_request]

jobs:
  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'

      - name: Install dependencies
        run: npm ci

      - name: Run unit tests
        run: npm run test:unit -- --coverage

      - name: Run integration tests
        run: npm run test:integration

      - name: Upload coverage
        uses: codecov/codecov-action@v3

  backend-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s

    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov pytest-asyncio

      - name: Run unit tests
        run: pytest -m unit --cov

      - name: Run integration tests
        run: pytest -m integration --cov --cov-append

      - name: Run security tests
        run: pytest -m security --cov --cov-append

      - name: Validate coverage threshold
        run: pytest --cov --cov-fail-under=90

      - name: Upload coverage
        uses: codecov/codecov-action@v3

  e2e-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Install Playwright
        run: npx playwright install --with-deps

      - name: Start backend
        run: |
          cd backend
          uvicorn app.main:app --host 0.0.0.0 --port 8888 &

      - name: Start frontend
        run: |
          cd frontend
          npm run dev &

      - name: Run E2E tests
        run: npx playwright test

      - name: Upload Playwright report
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: playwright-report
          path: playwright-report/
```

### 8.3 Pre-commit Hooks

**Husky**: `.husky/pre-commit`

```bash
#!/bin/sh
. "$(dirname "$0")/_/husky.sh"

# Run frontend tests
cd frontend && npm run test:unit --silent --bail || exit 1

# Run backend unit tests (fast)
cd ../backend && pytest -m unit --quiet || exit 1

echo "✅ Pre-commit tests passed!"
```

---

## 9. Test Data & Fixtures

### 9.1 CSRF Token Fixtures

**Location**: `/tests/fixtures/csrf_fixtures.py`

```python
import pytest
import time
import hmac
import hashlib
from app.config.settings import settings

@pytest.fixture
def valid_csrf_token():
    """Generate a valid CSRF token."""
    timestamp = str(int(time.time()))
    random_data = "a" * 64  # 32 bytes hex
    data = f"{timestamp}.{random_data}"

    signature = hmac.new(
        settings.SECRET_KEY.encode(),
        data.encode(),
        hashlib.sha256
    ).hexdigest()

    return f"{data}.{signature}"

@pytest.fixture
def expired_csrf_token():
    """Generate an expired CSRF token (2 hours old)."""
    old_timestamp = str(int(time.time()) - 7200)
    random_data = "b" * 64
    data = f"{old_timestamp}.{random_data}"

    signature = hmac.new(
        settings.SECRET_KEY.encode(),
        data.encode(),
        hashlib.sha256
    ).hexdigest()

    return f"{data}.{signature}"

@pytest.fixture
def invalid_csrf_token():
    """Generate a CSRF token with invalid signature."""
    timestamp = str(int(time.time()))
    random_data = "c" * 64
    wrong_signature = "d" * 64  # Invalid signature

    return f"{timestamp}.{random_data}.{wrong_signature}"
```

### 9.2 Session Fixtures

**Location**: `/tests/fixtures/session_fixtures.py`

```python
import pytest
from uuid import uuid4
from datetime import datetime, timedelta

@pytest.fixture
def active_quiz_session(db_session):
    """Create an active quiz session."""
    from app.models.quiz_session import QuizSession

    session = QuizSession(
        session_id=str(uuid4()),
        patient_id="test-patient-123",
        quiz_type="monthly",
        status="active",
        expires_at=datetime.utcnow() + timedelta(hours=1),
        created_at=datetime.utcnow(),
    )

    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    return session

@pytest.fixture
def expired_quiz_session(db_session):
    """Create an expired quiz session."""
    from app.models.quiz_session import QuizSession

    session = QuizSession(
        session_id=str(uuid4()),
        patient_id="test-patient-456",
        quiz_type="monthly",
        status="expired",
        expires_at=datetime.utcnow() - timedelta(hours=1),
        created_at=datetime.utcnow() - timedelta(hours=2),
    )

    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    return session
```

### 9.3 Frontend Test Fixtures

**Location**: `/tests/fixtures/api-client-fixtures.ts`

```typescript
export const mockValidCsrfResponse = {
  csrf_token: '1735123456.abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890.1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef',
};

export const mockInvalidCsrfResponse = {
  csrf_token: 'invalid-format',
};

export const mockSessionResponse = {
  session_id: 'test-session-123',
  status: 'active',
  quiz_type: 'monthly',
  expires_at: '2025-12-31T23:59:59Z',
  created_at: '2025-12-20T10:00:00Z',
};

export const mockExpiredSessionResponse = {
  session_id: 'expired-session-456',
  status: 'expired',
  quiz_type: 'monthly',
  expires_at: '2025-12-19T10:00:00Z',
  created_at: '2025-12-19T09:00:00Z',
};

export function createMockFetch(responses: Record<string, any>) {
  return jest.fn((url: string) => {
    const matchedKey = Object.keys(responses).find(key => url.includes(key));
    const response = matchedKey ? responses[matchedKey] : { ok: false, status: 404 };

    return Promise.resolve({
      ok: response.ok !== false,
      status: response.status || 200,
      json: async () => response,
    });
  });
}
```

---

## 10. Memory Storage Test Plan

### Collective Memory Keys

```bash
# Test strategy storage
hive/tester/unit-tests         # Unit test specifications
hive/tester/integration-tests  # Integration test specifications
hive/tester/security-tests     # Security test specifications
hive/tester/test-coverage      # Coverage requirements and results
hive/tester/performance-tests  # Performance benchmarks
hive/tester/e2e-tests          # E2E test scenarios
hive/tester/test-status        # Current test execution status

# Coordination with other agents
hive/researcher/api-analysis   # API design decisions
hive/coder/implementation-plan # Implementation details
hive/reviewer/security-review  # Security requirements
```

---

## 11. Success Criteria

### Definition of Done

- [ ] All unit tests written with 95%+ coverage
- [ ] All integration tests passing
- [ ] Security tests validating XSS, CSRF, cookie protection
- [ ] Performance benchmarks meeting targets (<200ms p95)
- [ ] E2E tests covering complete user flows
- [ ] Coverage reports generated and validated
- [ ] CI/CD pipeline configured and passing
- [ ] Test documentation complete
- [ ] Test strategy stored in collective memory

### Acceptance Criteria

1. **QuizApiClient Tests**: 100% function coverage, 95%+ line coverage
2. **useQuizSession Tests**: 100% function coverage, 95%+ line coverage
3. **CSRF Integration**: All token lifecycle scenarios tested
4. **Security**: Zero XSS vulnerabilities, CSRF protection validated
5. **Performance**: All requests <15s timeout, p95 <200ms
6. **E2E**: Complete quiz flow tested in real browser

---

## 12. Next Steps

**Waiting for Coder Agent to complete implementation, then:**

1. Create test files based on this strategy
2. Implement unit tests first (QuizApiClient, useQuizSession)
3. Add integration tests (CSRF flow, session management)
4. Implement security tests (XSS, CSRF, cookies)
5. Add performance tests (timeouts, benchmarks)
6. Create E2E tests (Playwright)
7. Configure coverage reporting
8. Set up CI/CD pipeline
9. Document test execution procedures

---

**Document Version**: 1.0
**Author**: Tester Agent (Hive Mind Swarm)
**Date**: 2025-12-20
**Status**: Ready for Implementation
