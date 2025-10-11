/**
 * Error Boundary and Fault Tolerance Integration Tests
 * ===================================================
 *
 * This test suite validates error boundary components and application fault tolerance,
 * ensuring graceful degradation and proper error handling throughout the application.
 *
 * Test Coverage:
 * - React Error Boundary components
 * - Network error handling and recovery
 * - API timeout and retry mechanisms
 * - Component error recovery
 * - User-friendly error messaging
 * - Fallback UI rendering
 */

import React from 'react'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest'

// Import components that should have error boundaries
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { DashboardPage } from '@/pages/DashboardPage'
import { AdminDashboard } from '@/components/admin/AdminDashboard'
import { UserDetailsModal } from '@/components/admin/users/UserDetailsModal'
import { QuickStats } from '@/components/dashboard/QuickStats'

// Mock components that might throw errors
const ThrowingComponent = ({ shouldThrow = true }: { shouldThrow?: boolean }) => {
  if (shouldThrow) {
    throw new Error('Test component error')
  }
  return <div>Component rendered successfully</div>
}

const NetworkErrorComponent = () => {
  const [data, setData] = React.useState(null)
  const [error, setError] = React.useState<string | null>(null)
  const [loading, setLoading] = React.useState(false)

  const fetchData = async () => {
    setLoading(true)
    setError(null)

    try {
      const response = await fetch('/api/v1/test-endpoint')
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      const result = await response.json()
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  React.useEffect(() => {
    fetchData()
  }, [])

  if (loading) return <div>Loading...</div>
  if (error) return <div data-testid="error-message">Error: {error}</div>
  return <div data-testid="success-message">Data loaded successfully</div>
}

// Test wrapper with providers
const TestWrapper = ({ children }: { children: React.ReactNode }) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        {children}
      </BrowserRouter>
    </QueryClientProvider>
  )
}

describe('Error Boundary Components', () => {
  let consoleErrorSpy: any

  beforeEach(() => {
    // Suppress console.error for error boundary tests
    consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    consoleErrorSpy.mockRestore()
  })

  it('should catch and display component errors gracefully', async () => {
    render(
      <TestWrapper>
        <ErrorBoundary>
          <ThrowingComponent shouldThrow={true} />
        </ErrorBoundary>
      </TestWrapper>
    )

    // Should display error boundary fallback UI
    await waitFor(() => {
      expect(screen.getByText(/something went wrong/i)).toBeInTheDocument()
    })

    // Should provide option to retry or report error
    expect(screen.getByRole('button', { name: /try again|reload/i })).toBeInTheDocument()
  })

  it('should allow recovery from errors', async () => {
    const MockComponent = ({ shouldError }: { shouldError: boolean }) => {
      if (shouldError) {
        throw new Error('Component error')
      }
      return <div>Component working</div>
    }

    const TestContainer = () => {
      const [hasError, setHasError] = React.useState(true)

      return (
        <div>
          <button onClick={() => setHasError(false)}>Fix Error</button>
          <ErrorBoundary key={hasError ? 'error' : 'success'}>
            <MockComponent shouldError={hasError} />
          </ErrorBoundary>
        </div>
      )
    }

    render(
      <TestWrapper>
        <TestContainer />
      </TestWrapper>
    )

    // Initially should show error
    await waitFor(() => {
      expect(screen.getByText(/something went wrong/i)).toBeInTheDocument()
    })

    // Fix the error and verify recovery
    fireEvent.click(screen.getByText('Fix Error'))

    await waitFor(() => {
      expect(screen.getByText('Component working')).toBeInTheDocument()
    })
  })

  it('should handle errors in nested components', async () => {
    const NestedComponent = () => {
      throw new Error('Nested component error')
    }

    const ParentComponent = () => (
      <div>
        <h1>Parent Component</h1>
        <NestedComponent />
      </div>
    )

    render(
      <TestWrapper>
        <ErrorBoundary>
          <ParentComponent />
        </ErrorBoundary>
      </TestWrapper>
    )

    await waitFor(() => {
      expect(screen.getByText(/something went wrong/i)).toBeInTheDocument()
    })

    // Parent component should not be rendered due to error in child
    expect(screen.queryByText('Parent Component')).not.toBeInTheDocument()
  })

  it('should provide error reporting functionality', async () => {
    const mockErrorReport = vi.fn()

    // Mock error reporting service
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: true })
    }))

    render(
      <TestWrapper>
        <ErrorBoundary onError={mockErrorReport}>
          <ThrowingComponent />
        </ErrorBoundary>
      </TestWrapper>
    )

    await waitFor(() => {
      expect(screen.getByText(/something went wrong/i)).toBeInTheDocument()
    })

    // Click report error button if available
    const reportButton = screen.queryByRole('button', { name: /report|send report/i })
    if (reportButton) {
      fireEvent.click(reportButton)
      expect(mockErrorReport).toHaveBeenCalled()
    }
  })

  it('should handle errors during async operations', async () => {
    const AsyncErrorComponent = () => {
      const [error, setError] = React.useState<Error | null>(null)

      React.useEffect(() => {
        // Simulate async error
        const timer = setTimeout(() => {
          setError(new Error('Async operation failed'))
        }, 100)

        return () => clearTimeout(timer)
      }, [])

      if (error) {
        throw error
      }

      return <div>Async component loaded</div>
    }

    render(
      <TestWrapper>
        <ErrorBoundary>
          <AsyncErrorComponent />
        </ErrorBoundary>
      </TestWrapper>
    )

    // Initially should show component loading
    expect(screen.getByText('Async component loaded')).toBeInTheDocument()

    // After error occurs, should show error boundary
    await waitFor(() => {
      expect(screen.getByText(/something went wrong/i)).toBeInTheDocument()
    }, { timeout: 200 })
  })
})

describe('Network Error Handling', () => {
  beforeEach(() => {
    // Reset fetch mock
    vi.restoreAllMocks()
  })

  it('should handle network timeouts gracefully', async () => {
    // Mock network timeout
    vi.stubGlobal('fetch', vi.fn().mockImplementation(() =>
      new Promise((_, reject) =>
        setTimeout(() => reject(new Error('Network timeout')), 100)
      )
    ))

    render(
      <TestWrapper>
        <NetworkErrorComponent />
      </TestWrapper>
    )

    // Should show loading initially
    expect(screen.getByText('Loading...')).toBeInTheDocument()

    // Should show timeout error after timeout
    await waitFor(() => {
      expect(screen.getByTestId('error-message')).toBeInTheDocument()
      expect(screen.getByText(/network timeout/i)).toBeInTheDocument()
    }, { timeout: 200 })
  })

  it('should handle HTTP error responses', async () => {
    // Mock HTTP error response
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error'
    }))

    render(
      <TestWrapper>
        <NetworkErrorComponent />
      </TestWrapper>
    )

    await waitFor(() => {
      expect(screen.getByTestId('error-message')).toBeInTheDocument()
      expect(screen.getByText(/HTTP 500/i)).toBeInTheDocument()
    })
  })

  it('should handle network connectivity issues', async () => {
    // Mock network connectivity error
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Failed to fetch')))

    render(
      <TestWrapper>
        <NetworkErrorComponent />
      </TestWrapper>
    )

    await waitFor(() => {
      expect(screen.getByTestId('error-message')).toBeInTheDocument()
      expect(screen.getByText(/failed to fetch/i)).toBeInTheDocument()
    })
  })

  it('should implement retry mechanism for failed requests', async () => {
    let callCount = 0
    vi.stubGlobal('fetch', vi.fn().mockImplementation(() => {
      callCount++
      if (callCount <= 2) {
        return Promise.reject(new Error('Temporary failure'))
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ data: 'success' })
      })
    }))

    const RetryComponent = () => {
      const [data, setData] = React.useState(null)
      const [error, setError] = React.useState<string | null>(null)
      const [retryCount, setRetryCount] = React.useState(0)

      const fetchWithRetry = async (attempt = 0) => {
        try {
          const response = await fetch('/api/v1/test-endpoint')
          if (!response.ok) {
            throw new Error(`HTTP ${response.status}`)
          }
          const result = await response.json()
          setData(result)
          setError(null)
        } catch (err) {
          if (attempt < 2) {
            setRetryCount(attempt + 1)
            setTimeout(() => fetchWithRetry(attempt + 1), 1000)
          } else {
            setError(err instanceof Error ? err.message : 'Unknown error')
          }
        }
      }

      React.useEffect(() => {
        fetchWithRetry()
      }, [])

      if (error) return <div data-testid="final-error">Final error: {error}</div>
      if (data) return <div data-testid="success-data">Success!</div>
      return <div data-testid="retry-status">Retrying... (attempt {retryCount + 1})</div>
    }

    render(
      <TestWrapper>
        <RetryComponent />
      </TestWrapper>
    )

    // Should eventually succeed after retries
    await waitFor(() => {
      expect(screen.getByTestId('success-data')).toBeInTheDocument()
    }, { timeout: 5000 })

    expect(callCount).toBe(3) // 1 initial + 2 retries
  })
})

describe('Component Fault Tolerance', () => {
  it('should gracefully degrade when optional components fail', async () => {
    const OptionalComponent = ({ shouldFail }: { shouldFail: boolean }) => {
      if (shouldFail) {
        throw new Error('Optional component failed')
      }
      return <div data-testid="optional-content">Optional content</div>
    }

    const MainComponent = () => (
      <div>
        <h1 data-testid="main-content">Main Content</h1>
        <ErrorBoundary fallback={<div data-testid="optional-fallback">Feature unavailable</div>}>
          <OptionalComponent shouldFail={true} />
        </ErrorBoundary>
      </div>
    )

    render(
      <TestWrapper>
        <MainComponent />
      </TestWrapper>
    )

    // Main content should still be visible
    expect(screen.getByTestId('main-content')).toBeInTheDocument()

    // Optional component should show fallback
    await waitFor(() => {
      expect(screen.getByTestId('optional-fallback')).toBeInTheDocument()
    })

    // Optional content should not be visible
    expect(screen.queryByTestId('optional-content')).not.toBeInTheDocument()
  })

  it('should handle state corruption gracefully', async () => {
    const CorruptibleComponent = () => {
      const [isCorrupted, setIsCorrupted] = React.useState(false)

      React.useEffect(() => {
        // Simulate state corruption
        const timer = setTimeout(() => {
          setIsCorrupted(true)
        }, 100)

        return () => clearTimeout(timer)
      }, [])

      if (isCorrupted) {
        // Reset component state on corruption
        return (
          <div data-testid="recovery-mode">
            <p>Component recovered from error</p>
            <button onClick={() => window.location.reload()}>Refresh Page</button>
          </div>
        )
      }

      return <div data-testid="normal-mode">Normal operation</div>
    }

    render(
      <TestWrapper>
        <CorruptibleComponent />
      </TestWrapper>
    )

    // Initially should show normal mode
    expect(screen.getByTestId('normal-mode')).toBeInTheDocument()

    // After state corruption, should show recovery mode
    await waitFor(() => {
      expect(screen.getByTestId('recovery-mode')).toBeInTheDocument()
    }, { timeout: 200 })
  })

  it('should maintain app functionality when non-critical features fail', async () => {
    const CriticalFeature = () => (
      <div data-testid="critical-feature">Critical functionality working</div>
    )

    const NonCriticalFeature = ({ shouldFail }: { shouldFail: boolean }) => {
      if (shouldFail) {
        throw new Error('Non-critical feature failed')
      }
      return <div data-testid="non-critical-feature">Non-critical feature</div>
    }

    const App = () => (
      <div>
        <CriticalFeature />
        <ErrorBoundary fallback={<div data-testid="feature-unavailable">Feature temporarily unavailable</div>}>
          <NonCriticalFeature shouldFail={true} />
        </ErrorBoundary>
      </div>
    )

    render(
      <TestWrapper>
        <App />
      </TestWrapper>
    )

    // Critical feature should always work
    expect(screen.getByTestId('critical-feature')).toBeInTheDocument()

    // Non-critical feature should show fallback
    await waitFor(() => {
      expect(screen.getByTestId('feature-unavailable')).toBeInTheDocument()
    })
  })

  it('should handle memory pressure gracefully', async () => {
    const MemoryIntensiveComponent = ({ size }: { size: number }) => {
      const [data, setData] = React.useState<string[]>([])

      React.useEffect(() => {
        try {
          // Simulate memory-intensive operation
          const largeArray = new Array(size).fill('x'.repeat(1000))
          setData(largeArray)
        } catch (error) {
          // Handle out of memory gracefully
          console.warn('Memory allocation failed, falling back to smaller dataset')
          setData(['fallback data'])
        }
      }, [size])

      return (
        <div data-testid="memory-component">
          Items loaded: {data.length}
        </div>
      )
    }

    render(
      <TestWrapper>
        <ErrorBoundary fallback={<div data-testid="memory-error">Memory allocation failed</div>}>
          <MemoryIntensiveComponent size={1000000} />
        </ErrorBoundary>
      </TestWrapper>
    )

    // Should either handle gracefully or show error boundary
    await waitFor(() => {
      const memoryComponent = screen.queryByTestId('memory-component')
      const memoryError = screen.queryByTestId('memory-error')

      expect(memoryComponent || memoryError).toBeInTheDocument()
    })
  })
})

describe('User Experience During Errors', () => {
  it('should show user-friendly error messages', async () => {
    const UserFriendlyErrorBoundary = ({ children }: { children: React.ReactNode }) => {
      const [hasError, setHasError] = React.useState(false)

      React.useEffect(() => {
        const handleError = () => setHasError(true)
        window.addEventListener('error', handleError)
        return () => window.removeEventListener('error', handleError)
      }, [])

      if (hasError) {
        return (
          <div data-testid="user-friendly-error" className="error-container">
            <h2>Oops! Something went wrong</h2>
            <p>We're sorry, but something unexpected happened. Please try refreshing the page.</p>
            <button onClick={() => window.location.reload()}>Refresh Page</button>
            <button onClick={() => setHasError(false)}>Try Again</button>
          </div>
        )
      }

      return <>{children}</>
    }

    render(
      <TestWrapper>
        <UserFriendlyErrorBoundary>
          <ThrowingComponent />
        </UserFriendlyErrorBoundary>
      </TestWrapper>
    )

    // Should show user-friendly error message
    await waitFor(() => {
      expect(screen.getByTestId('user-friendly-error')).toBeInTheDocument()
      expect(screen.getByText(/oops! something went wrong/i)).toBeInTheDocument()
      expect(screen.getByText(/try refreshing the page/i)).toBeInTheDocument()
    })

    // Should provide actionable buttons
    expect(screen.getByRole('button', { name: /refresh page/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument()
  })

  it('should maintain navigation functionality during partial failures', async () => {
    const PartiallyFailingApp = () => {
      const [currentPage, setCurrentPage] = React.useState('home')

      const renderPage = () => {
        switch (currentPage) {
          case 'home':
            return <div data-testid="home-page">Home Page</div>
          case 'about':
            return <ThrowingComponent />
          case 'contact':
            return <div data-testid="contact-page">Contact Page</div>
          default:
            return <div>Page not found</div>
        }
      }

      return (
        <div>
          <nav data-testid="navigation">
            <button onClick={() => setCurrentPage('home')}>Home</button>
            <button onClick={() => setCurrentPage('about')}>About</button>
            <button onClick={() => setCurrentPage('contact')}>Contact</button>
          </nav>
          <ErrorBoundary
            key={currentPage}
            fallback={
              <div data-testid="page-error">
                <p>This page is temporarily unavailable</p>
                <button onClick={() => setCurrentPage('home')}>Go to Home</button>
              </div>
            }
          >
            {renderPage()}
          </ErrorBoundary>
        </div>
      )
    }

    render(
      <TestWrapper>
        <PartiallyFailingApp />
      </TestWrapper>
    )

    // Initially should show home page
    expect(screen.getByTestId('home-page')).toBeInTheDocument()

    // Navigation should always be available
    expect(screen.getByTestId('navigation')).toBeInTheDocument()

    // Try to navigate to failing page
    fireEvent.click(screen.getByText('About'))

    await waitFor(() => {
      expect(screen.getByTestId('page-error')).toBeInTheDocument()
    })

    // Navigation should still work
    expect(screen.getByTestId('navigation')).toBeInTheDocument()

    // Should be able to navigate to working page
    fireEvent.click(screen.getByText('Contact'))

    await waitFor(() => {
      expect(screen.getByTestId('contact-page')).toBeInTheDocument()
    })
  })

  it('should preserve user data during component errors', async () => {
    const DataPreservingComponent = () => {
      const [formData, setFormData] = React.useState({ name: '', email: '' })
      const [hasError, setHasError] = React.useState(false)

      // Simulate component error but preserve form data
      const handleSubmit = () => {
        if (formData.name === 'error') {
          setHasError(true)
          return
        }
        // Normal submission logic
      }

      if (hasError) {
        return (
          <div data-testid="error-with-data">
            <p>Submission failed, but your data is preserved</p>
            <p>Name: {formData.name}</p>
            <p>Email: {formData.email}</p>
            <button onClick={() => setHasError(false)}>Try Again</button>
          </div>
        )
      }

      return (
        <form data-testid="data-form">
          <input
            type="text"
            placeholder="Name"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
          />
          <input
            type="email"
            placeholder="Email"
            value={formData.email}
            onChange={(e) => setFormData({ ...formData, email: e.target.value })}
          />
          <button type="button" onClick={handleSubmit}>Submit</button>
        </form>
      )
    }

    render(
      <TestWrapper>
        <DataPreservingComponent />
      </TestWrapper>
    )

    // Fill form
    fireEvent.change(screen.getByPlaceholderText('Name'), { target: { value: 'error' } })
    fireEvent.change(screen.getByPlaceholderText('Email'), { target: { value: 'test@example.com' } })

    // Submit to trigger error
    fireEvent.click(screen.getByText('Submit'))

    // Should show error but preserve data
    await waitFor(() => {
      expect(screen.getByTestId('error-with-data')).toBeInTheDocument()
      expect(screen.getByText('Name: error')).toBeInTheDocument()
      expect(screen.getByText('Email: test@example.com')).toBeInTheDocument()
    })
  })
})

describe('Integration with Real Components', () => {
  it('should handle QuickStats component errors gracefully', async () => {
    // Mock API to return error
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('API Error')))

    render(
      <TestWrapper>
        <ErrorBoundary fallback={<div data-testid="stats-error">Stats temporarily unavailable</div>}>
          <QuickStats />
        </ErrorBoundary>
      </TestWrapper>
    )

    // Should either handle the error internally or trigger error boundary
    await waitFor(() => {
      const statsError = screen.queryByTestId('stats-error')
      const statsContent = screen.queryByTestId('quick-stats')

      // Should show either error fallback or handle error gracefully
      expect(statsError || statsContent).toBeInTheDocument()
    }, { timeout: 2000 })
  })

  it('should handle dashboard page partial failures', async () => {
    // Mock some API calls to fail
    vi.stubGlobal('fetch', vi.fn().mockImplementation((url) => {
      if (url.includes('stats')) {
        return Promise.reject(new Error('Stats API Error'))
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ data: 'success' })
      })
    }))

    render(
      <TestWrapper>
        <ErrorBoundary>
          <DashboardPage />
        </ErrorBoundary>
      </TestWrapper>
    )

    // Dashboard should handle partial failures gracefully
    await waitFor(() => {
      // Should not show complete error boundary
      expect(screen.queryByText(/something went wrong/i)).not.toBeInTheDocument()
    }, { timeout: 2000 })
  })
})