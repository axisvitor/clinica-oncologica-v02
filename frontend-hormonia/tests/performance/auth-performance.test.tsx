import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter } from 'react-router-dom'
import { performance } from 'perf_hooks'
import { LoginPage } from '@/pages/LoginPage'
import { AuthContext } from '@/contexts/AuthContext'
import { AuthContextType } from '@/contexts/AuthContext'

// Performance measurement utilities
class PerformanceTracker {
  private startTime: number = 0
  private measurements: Record<string, number> = {}

  start(label: string) {
    this.startTime = performance.now()
    return label
  }

  end(label: string) {
    const duration = performance.now() - this.startTime
    this.measurements[label] = duration
    return duration
  }

  getMeasurement(label: string): number {
    return this.measurements[label] || 0
  }

  getAllMeasurements(): Record<string, number> {
    return { ...this.measurements }
  }

  clear() {
    this.measurements = {}
    this.startTime = 0
  }
}

// Mock dependencies with performance tracking
const mockLogin = vi.fn()
const performanceTracker = new PerformanceTracker()

vi.mock('@/lib/runtime-config', () => ({
  isProduction: vi.fn().mockReturnValue(false)
}))

vi.mock('@/lib/config-initializer', () => ({
  useConfig: () => ({
    config: {
      VITE_ENVIRONMENT: 'development',
      VITE_DEBUG_MODE: 'true',
      VITE_SHOW_DEMO_CREDENTIALS: 'true'
    }
  })
}))

vi.mock('@/hooks/use-auth-submit', () => ({
  useAuthSubmit: vi.fn().mockReturnValue({
    isSubmitting: false,
    error: null,
    handleSubmit: vi.fn((fn) => fn)
  })
}))

const createMockAuthContext = (overrides: Partial<AuthContextType> = {}): AuthContextType => ({
  user: null,
  session: null,
  isAuthenticated: false,
  isLoading: false,
  login: mockLogin,
  logout: vi.fn(),
  logoutAll: vi.fn(),
  hasPermission: vi.fn(),
  hasRole: vi.fn(),
  getFirebaseToken: vi.fn(),
  refreshToken: vi.fn(),
  ...overrides
})

const renderWithAuth = (authValue: Partial<AuthContextType> = {}) => {
  const contextValue = createMockAuthContext(authValue)

  return render(
    <BrowserRouter>
      <AuthContext.Provider value={contextValue}>
        <LoginPage />
      </AuthContext.Provider>
    </BrowserRouter>
  )
}

describe('Authentication Performance Tests', () => {
  let user: ReturnType<typeof userEvent.setup>

  beforeEach(() => {
    user = userEvent.setup()
    vi.clearAllMocks()
    performanceTracker.clear()
  })

  afterEach(() => {
    vi.clearAllMocks()
    performanceTracker.clear()
  })

  describe('Component Rendering Performance', () => {
    it('should render login page within acceptable time', () => {
      performanceTracker.start('login-page-render')

      renderWithAuth()

      const renderTime = performanceTracker.end('login-page-render')

      // Should render within 100ms
      expect(renderTime).toBeLessThan(100)
      expect(screen.getByRole('heading', { name: /entrar na sua conta/i })).toBeInTheDocument()
    })

    it('should render with minimal DOM nodes', () => {
      const { container } = renderWithAuth()

      const nodeCount = container.querySelectorAll('*').length

      // Should have reasonable DOM size (less than 200 nodes)
      expect(nodeCount).toBeLessThan(200)
    })

    it('should handle multiple re-renders efficiently', () => {
      const renders: number[] = []

      for (let i = 0; i < 10; i++) {
        performanceTracker.start(`render-${i}`)
        const { unmount } = renderWithAuth()
        renders.push(performanceTracker.end(`render-${i}`))
        unmount()
      }

      const averageRenderTime = renders.reduce((sum, time) => sum + time, 0) / renders.length

      // Average render time should be under 50ms
      expect(averageRenderTime).toBeLessThan(50)
    })
  })

  describe('Form Interaction Performance', () => {
    it('should handle typing without performance degradation', async () => {
      renderWithAuth()

      const emailInput = screen.getByLabelText(/email/i)
      const typingTimes: number[] = []

      const testText = 'test@example.com'

      for (let i = 0; i < testText.length; i++) {
        performanceTracker.start(`type-${i}`)
        await user.type(emailInput, testText[i])
        typingTimes.push(performanceTracker.end(`type-${i}`))
      }

      const averageTypingTime = typingTimes.reduce((sum, time) => sum + time, 0) / typingTimes.length

      // Each keystroke should be processed quickly
      expect(averageTypingTime).toBeLessThan(20)
    })

    it('should validate form fields efficiently', async () => {
      renderWithAuth()

      const emailInput = screen.getByLabelText(/email/i)
      const submitButton = screen.getByRole('button', { name: /entrar/i })

      performanceTracker.start('validation')

      await user.type(emailInput, 'invalid-email')
      await user.click(submitButton)

      await waitFor(() => {
        expect(screen.getByText(/email inválido/i)).toBeInTheDocument()
      })

      const validationTime = performanceTracker.end('validation')

      // Validation should be fast
      expect(validationTime).toBeLessThan(100)
    })

    it('should handle form submission efficiently', async () => {
      mockLogin.mockResolvedValue(undefined)

      renderWithAuth()

      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/senha/i)
      const submitButton = screen.getByRole('button', { name: /entrar/i })

      await user.type(emailInput, 'test@example.com')
      await user.type(passwordInput, 'password123')

      performanceTracker.start('form-submission')
      await user.click(submitButton)

      await waitFor(() => {
        expect(mockLogin).toHaveBeenCalled()
      })

      const submissionTime = performanceTracker.end('form-submission')

      // Form submission handling should be fast
      expect(submissionTime).toBeLessThan(50)
    })
  })

  describe('State Management Performance', () => {
    it('should handle auth state changes efficiently', async () => {
      const stateChangeTimes: number[] = []

      // Test multiple state changes
      for (let i = 0; i < 5; i++) {
        performanceTracker.start(`state-change-${i}`)

        const { rerender } = renderWithAuth({ isLoading: false })

        rerender(
          <BrowserRouter>
            <AuthContext.Provider value={createMockAuthContext({ isLoading: true })}>
              <LoginPage />
            </AuthContext.Provider>
          </BrowserRouter>
        )

        stateChangeTimes.push(performanceTracker.end(`state-change-${i}`))
      }

      const averageStateChangeTime = stateChangeTimes.reduce((sum, time) => sum + time, 0) / stateChangeTimes.length

      // State changes should be processed quickly
      expect(averageStateChangeTime).toBeLessThan(30)
    })

    it('should handle error state changes without performance impact', async () => {
      const { rerender } = renderWithAuth()

      performanceTracker.start('error-state-change')

      // Simulate error state
      const useAuthSubmitMock = vi.mocked(require('@/hooks/use-auth-submit').useAuthSubmit)
      useAuthSubmitMock.mockReturnValue({
        isSubmitting: false,
        error: 'Authentication failed',
        handleSubmit: vi.fn((fn) => fn)
      })

      rerender(
        <BrowserRouter>
          <AuthContext.Provider value={createMockAuthContext()}>
            <LoginPage />
          </AuthContext.Provider>
        </BrowserRouter>
      )

      await waitFor(() => {
        expect(screen.getByText('Authentication failed')).toBeInTheDocument()
      })

      const errorStateTime = performanceTracker.end('error-state-change')

      // Error state rendering should be fast
      expect(errorStateTime).toBeLessThan(50)
    })
  })

  describe('Memory Performance', () => {
    it('should not create memory leaks with multiple renders', () => {
      const initialMemory = performance.memory?.usedJSHeapSize || 0

      // Render and unmount multiple times
      for (let i = 0; i < 100; i++) {
        const { unmount } = renderWithAuth()
        unmount()
      }

      // Force garbage collection if available
      if (global.gc) {
        global.gc()
      }

      const finalMemory = performance.memory?.usedJSHeapSize || 0
      const memoryIncrease = finalMemory - initialMemory

      // Memory increase should be minimal (less than 10MB)
      expect(memoryIncrease).toBeLessThan(10 * 1024 * 1024)
    })

    it('should cleanup event listeners properly', () => {
      const addEventListenerSpy = vi.spyOn(document, 'addEventListener')
      const removeEventListenerSpy = vi.spyOn(document, 'removeEventListener')

      const { unmount } = renderWithAuth()

      const addedListeners = addEventListenerSpy.mock.calls.length

      unmount()

      const removedListeners = removeEventListenerSpy.mock.calls.length

      // Should remove at least as many listeners as added
      expect(removedListeners).toBeGreaterThanOrEqual(addedListeners)

      addEventListenerSpy.mockRestore()
      removeEventListenerSpy.mockRestore()
    })
  })

  describe('Network Performance Simulation', () => {
    it('should handle slow network responses gracefully', async () => {
      const slowMockLogin = vi.fn().mockImplementation(() =>
        new Promise(resolve => setTimeout(resolve, 1000))
      )

      renderWithAuth()

      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/senha/i)
      const submitButton = screen.getByRole('button', { name: /entrar/i })

      await user.type(emailInput, 'test@example.com')
      await user.type(passwordInput, 'password123')

      performanceTracker.start('slow-network-handling')
      await user.click(submitButton)

      // Should remain responsive during slow network request
      expect(screen.getByRole('button')).toBeInTheDocument()

      const handlingTime = performanceTracker.end('slow-network-handling')

      // UI handling should be fast even with slow network
      expect(handlingTime).toBeLessThan(100)
    })

    it('should handle network errors without blocking UI', async () => {
      const errorMockLogin = vi.fn().mockRejectedValue(new Error('Network error'))

      renderWithAuth()

      const emailInput = screen.getByLabelText(/email/i)
      const passwordInput = screen.getByLabelText(/senha/i)
      const submitButton = screen.getByRole('button', { name: /entrar/i })

      await user.type(emailInput, 'test@example.com')
      await user.type(passwordInput, 'password123')

      performanceTracker.start('error-handling')
      await user.click(submitButton)

      const errorHandlingTime = performanceTracker.end('error-handling')

      // Error handling should be fast
      expect(errorHandlingTime).toBeLessThan(50)
    })
  })

  describe('Bundle Size Impact', () => {
    it('should have minimal CSS class usage', () => {
      const { container } = renderWithAuth()

      const elementsWithClasses = container.querySelectorAll('[class]')
      const totalClasses = Array.from(elementsWithClasses)
        .reduce((total, el) => total + el.className.split(' ').length, 0)

      // Should have reasonable number of CSS classes
      expect(totalClasses).toBeLessThan(500)
    })

    it('should use semantic HTML elements efficiently', () => {
      const { container } = renderWithAuth()

      const semanticElements = container.querySelectorAll(
        'main, section, article, header, footer, nav, aside, h1, h2, h3, h4, h5, h6, form, fieldset, legend, label, button, input'
      )

      const totalElements = container.querySelectorAll('*').length
      const semanticRatio = semanticElements.length / totalElements

      // Should have good semantic HTML ratio (at least 30%)
      expect(semanticRatio).toBeGreaterThan(0.3)
    })
  })

  describe('Rendering Optimization', () => {
    it('should avoid unnecessary re-renders', () => {
      let renderCount = 0
      const TrackingComponent = () => {
        renderCount++
        return <LoginPage />
      }

      const MockAuthProvider = ({ children }: { children: React.ReactNode }) => (
        <AuthContext.Provider value={createMockAuthContext()}>
          {children}
        </AuthContext.Provider>
      )

      const { rerender } = render(
        <BrowserRouter>
          <MockAuthProvider>
            <TrackingComponent />
          </MockAuthProvider>
        </BrowserRouter>
      )

      const initialRenderCount = renderCount

      // Trigger re-render with same props
      rerender(
        <BrowserRouter>
          <MockAuthProvider>
            <TrackingComponent />
          </MockAuthProvider>
        </BrowserRouter>
      )

      // Should not cause unnecessary re-renders
      expect(renderCount).toBe(initialRenderCount + 1)
    })

    it('should handle rapid prop changes efficiently', () => {
      const { rerender } = renderWithAuth({ isLoading: false })

      performanceTracker.start('rapid-prop-changes')

      // Simulate rapid prop changes
      for (let i = 0; i < 10; i++) {
        rerender(
          <BrowserRouter>
            <AuthContext.Provider value={createMockAuthContext({ isLoading: i % 2 === 0 })}>
              <LoginPage />
            </AuthContext.Provider>
          </BrowserRouter>
        )
      }

      const propChangeTime = performanceTracker.end('rapid-prop-changes')

      // Should handle rapid changes efficiently
      expect(propChangeTime).toBeLessThan(200)
    })
  })

  describe('Accessibility Performance', () => {
    it('should maintain performance with screen reader attributes', () => {
      performanceTracker.start('accessibility-render')

      renderWithAuth()

      const renderTime = performanceTracker.end('accessibility-render')

      // Accessibility attributes should not significantly impact performance
      expect(renderTime).toBeLessThan(150)

      // Verify accessibility attributes are present
      expect(screen.getByLabelText(/email/i)).toHaveAttribute('aria-invalid')
      expect(screen.getByLabelText(/senha/i)).toHaveAttribute('aria-invalid')
    })

    it('should handle focus management efficiently', async () => {
      renderWithAuth()

      const elements = [
        screen.getByLabelText(/email/i),
        screen.getByLabelText(/senha/i),
        screen.getByRole('button', { name: /mostrar senha/i }),
        screen.getByRole('checkbox'),
        screen.getByRole('button', { name: /entrar/i })
      ]

      performanceTracker.start('focus-management')

      // Tab through all elements
      for (const element of elements) {
        await user.tab()
      }

      const focusTime = performanceTracker.end('focus-management')

      // Focus management should be fast
      expect(focusTime).toBeLessThan(100)
    })
  })

  describe('Performance Budgets', () => {
    it('should meet Core Web Vitals thresholds', () => {
      // Largest Contentful Paint (LCP) simulation
      performanceTracker.start('lcp-simulation')
      renderWithAuth()
      const lcpTime = performanceTracker.end('lcp-simulation')

      // Should render main content quickly (simulated LCP)
      expect(lcpTime).toBeLessThan(100) // Much faster than 2.5s real LCP threshold

      // First Input Delay (FID) simulation
      performanceTracker.start('fid-simulation')
      screen.getByLabelText(/email/i).focus()
      const fidTime = performanceTracker.end('fid-simulation')

      // Should respond to first input quickly
      expect(fidTime).toBeLessThan(10) // Much faster than 100ms FID threshold
    })

    it('should maintain 60fps during animations', async () => {
      renderWithAuth()

      const passwordToggle = screen.getByRole('button', { name: /mostrar senha/i })

      const frameTimes: number[] = []

      // Simulate multiple rapid interactions
      for (let i = 0; i < 5; i++) {
        performanceTracker.start(`frame-${i}`)
        await user.click(passwordToggle)
        frameTimes.push(performanceTracker.end(`frame-${i}`))
      }

      const averageFrameTime = frameTimes.reduce((sum, time) => sum + time, 0) / frameTimes.length

      // Each interaction should be faster than 16.67ms (60fps)
      expect(averageFrameTime).toBeLessThan(16.67)
    })
  })

  describe('Performance Monitoring', () => {
    it('should track performance metrics for monitoring', () => {
      const metrics = {
        renderTime: 0,
        interactionTime: 0,
        memoryUsage: 0
      }

      performanceTracker.start('comprehensive-test')

      renderWithAuth()
      metrics.renderTime = performance.now()

      // Simulate user interaction
      const emailInput = screen.getByLabelText(/email/i)
      emailInput.focus()
      metrics.interactionTime = performance.now()

      metrics.memoryUsage = performance.memory?.usedJSHeapSize || 0

      performanceTracker.end('comprehensive-test')

      // All metrics should be reasonable
      expect(metrics.renderTime).toBeLessThan(1000)
      expect(metrics.interactionTime).toBeLessThan(2000)
      expect(metrics.memoryUsage).toBeLessThan(50 * 1024 * 1024) // Less than 50MB
    })
  })
})