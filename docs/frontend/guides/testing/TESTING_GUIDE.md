# Frontend Testing Guide

## Overview

This comprehensive testing guide covers all aspects of testing for the Hormonia Frontend-v2 application, including unit testing, integration testing, end-to-end testing, and performance testing.

## Testing Stack

- **Unit Testing**: Vitest + React Testing Library
- **E2E Testing**: Playwright
- **Component Testing**: Storybook + Interaction Tests
- **Performance Testing**: Lighthouse + Web Vitals
- **Visual Testing**: Percy (planned)
- **API Testing**: MSW (Mock Service Worker)

## Test Structure

```
Frontend-v2/
├── tests/
│   ├── unit/                    # Unit tests
│   ├── integration/             # Integration tests
│   ├── e2e/                     # End-to-end tests
│   ├── performance/             # Performance tests
│   ├── mocks/                   # Test mocks and fixtures
│   └── utils/                   # Test utilities
├── src/
│   └── **/*.test.ts(x)         # Co-located component tests
└── playwright.config.ts         # Playwright configuration
```

## Unit Testing

### Testing Setup

**Vitest Configuration** (`vitest.config.ts`):

```typescript
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      exclude: [
        'node_modules/',
        'tests/',
        '**/*.d.ts',
        '**/*.config.*',
        '**/types/**',
      ],
    },
  },
})
```

**Test Setup** (`tests/setup.ts`):

```typescript
import '@testing-library/jest-dom'
import { vi } from 'vitest'
import { server } from './mocks/server'

// Mock API server setup
beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

// Mock Intersection Observer
global.IntersectionObserver = vi.fn(() => ({
  observe: vi.fn(),
  disconnect: vi.fn(),
  unobserve: vi.fn(),
}))

// Mock ResizeObserver
global.ResizeObserver = vi.fn(() => ({
  observe: vi.fn(),
  disconnect: vi.fn(),
  unobserve: vi.fn(),
}))

// Mock window.matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})
```

### Component Testing Examples

#### Basic Component Test

```typescript
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { PatientCard } from '@/components/patients/PatientCard'

describe('PatientCard', () => {
  const mockPatient = {
    id: '1',
    name: 'João Silva',
    email: 'joao@example.com',
    age: 45,
    phone: '+55 11 99999-9999'
  }

  it('renders patient information correctly', () => {
    render(<PatientCard patient={mockPatient} />)

    expect(screen.getByText('João Silva')).toBeInTheDocument()
    expect(screen.getByText('joao@example.com')).toBeInTheDocument()
    expect(screen.getByText('45 anos')).toBeInTheDocument()
  })

  it('calls onEdit when edit button is clicked', () => {
    const onEdit = vi.fn()
    render(<PatientCard patient={mockPatient} onEdit={onEdit} />)

    fireEvent.click(screen.getByRole('button', { name: /edit/i }))
    expect(onEdit).toHaveBeenCalledWith('1')
  })

  it('shows loading state', () => {
    render(<PatientCard patient={mockPatient} isLoading />)
    expect(screen.getByTestId('loading-spinner')).toBeInTheDocument()
  })
})
```

#### Form Component Test

```typescript
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { CreatePatientForm } from '@/components/forms/CreatePatientForm'

describe('CreatePatientForm', () => {
  it('validates required fields', async () => {
    const onSubmit = vi.fn()
    render(<CreatePatientForm onSubmit={onSubmit} />)

    // Try to submit empty form
    fireEvent.click(screen.getByRole('button', { name: /save/i }))

    await waitFor(() => {
      expect(screen.getByText('Nome é obrigatório')).toBeInTheDocument()
      expect(screen.getByText('Email é obrigatório')).toBeInTheDocument()
    })

    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('submits form with valid data', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(<CreatePatientForm onSubmit={onSubmit} />)

    // Fill form
    await user.type(screen.getByLabelText(/nome/i), 'Maria Santos')
    await user.type(screen.getByLabelText(/email/i), 'maria@example.com')
    await user.type(screen.getByLabelText(/telefone/i), '+55 11 98888-8888')

    // Submit form
    fireEvent.click(screen.getByRole('button', { name: /save/i }))

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({
        name: 'Maria Santos',
        email: 'maria@example.com',
        phone: '+55 11 98888-8888'
      })
    })
  })
})
```

#### Hook Testing

```typescript
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { usePatients } from '@/hooks/usePatients'
import { createWrapper } from '@/tests/utils/test-wrapper'

describe('usePatients', () => {
  it('fetches patients successfully', async () => {
    const { result } = renderHook(() => usePatients(), {
      wrapper: createWrapper()
    })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(result.current.data).toHaveLength(2)
    expect(result.current.data[0]).toEqual(
      expect.objectContaining({
        id: expect.any(String),
        name: expect.any(String),
        email: expect.any(String)
      })
    )
  })

  it('handles error state', async () => {
    // Mock API error
    server.use(
      rest.get('/api/patients', (req, res, ctx) => {
        return res(ctx.status(500), ctx.json({ message: 'Server error' }))
      })
    )

    const { result } = renderHook(() => usePatients(), {
      wrapper: createWrapper()
    })

    await waitFor(() => {
      expect(result.current.isError).toBe(true)
    })

    expect(result.current.error).toBeDefined()
  })
})
```

### Test Utilities

**Test Wrapper** (`tests/utils/test-wrapper.tsx`):

```typescript
import React from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import { AuthProvider } from '@/contexts/AuthContext'
import { ConfigProvider } from '@/contexts/ConfigContext'

export const createWrapper = (options?: {
  queryClient?: QueryClient
  initialRoute?: string
}) => {
  const queryClient = options?.queryClient || new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })

  return ({ children }: { children: React.ReactNode }) => (
    <BrowserRouter
      basename={options?.initialRoute}
    >
      <QueryClientProvider client={queryClient}>
        <ConfigProvider>
          <AuthProvider>
            {children}
          </AuthProvider>
        </ConfigProvider>
      </QueryClientProvider>
    </BrowserRouter>
  )
}
```

**Mock Data** (`tests/mocks/data.ts`):

```typescript
export const mockPatients = [
  {
    id: '1',
    name: 'João Silva',
    email: 'joao@example.com',
    phone: '+55 11 99999-9999',
    age: 45,
    status: 'active',
    created_at: '2023-01-01T00:00:00-03:00'
  },
  {
    id: '2',
    name: 'Maria Santos',
    email: 'maria@example.com',
    phone: '+55 11 88888-8888',
    age: 38,
    status: 'active',
    created_at: '2023-01-02T00:00:00-03:00'
  }
]

export const mockUser = {
  id: '1',
  email: 'admin@example.com',
  full_name: 'Admin User',
  role: 'admin',
  permissions: ['users:read', 'patients:read', 'flows:read']
}
```

## Integration Testing

### API Integration Tests

**MSW Setup** (`tests/mocks/server.ts`):

```typescript
import { setupServer } from 'msw/node'
import { rest } from 'msw'
import { mockPatients, mockUser } from './data'

export const handlers = [
  // Auth endpoints
  rest.post('/api/auth/login', (req, res, ctx) => {
    return res(
      ctx.json({
        user: mockUser,
        token: 'mock-jwt-token',
        expires_in: 3600
      })
    )
  }),

  // Patients endpoints
  rest.get('/api/patients', (req, res, ctx) => {
    const search = req.url.searchParams.get('search')
    const filtered = search
      ? mockPatients.filter(p => p.name.toLowerCase().includes(search.toLowerCase()))
      : mockPatients

    return res(ctx.json({
      items: filtered,
      total: filtered.length,
      page: 1,
      size: 50
    }))
  }),

  rest.post('/api/patients', async (req, res, ctx) => {
    const body = await req.json()
    const newPatient = {
      id: Date.now().toString(),
      ...body,
      status: 'active',
      created_at: new Date().toISOString()
    }

    return res(ctx.status(201), ctx.json(newPatient))
  }),

  // AI endpoints
  rest.get('/api/ai/insights/:patientId', (req, res, ctx) => {
    const { patientId } = req.params

    return res(ctx.json({
      patient_id: patientId,
      insights: [
        {
          title: 'Engagement Pattern',
          description: 'Patient shows consistent engagement with morning messages',
          confidence: 85,
          category: 'behavioral'
        }
      ],
      recommendations: [
        {
          title: 'Increase Interaction',
          action: 'Send more interactive content',
          priority: 'medium',
          confidence: 78
        }
      ]
    }))
  })
]

export const server = setupServer(...handlers)
```

### Page Integration Tests

```typescript
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { PatientsPage } from '@/pages/PatientsPage'
import { createWrapper } from '@/tests/utils/test-wrapper'

describe('PatientsPage Integration', () => {
  it('loads and displays patients list', async () => {
    render(<PatientsPage />, { wrapper: createWrapper() })

    // Wait for loading to complete
    await waitFor(() => {
      expect(screen.queryByText(/loading/i)).not.toBeInTheDocument()
    })

    // Check patients are displayed
    expect(screen.getByText('João Silva')).toBeInTheDocument()
    expect(screen.getByText('Maria Santos')).toBeInTheDocument()
  })

  it('searches patients correctly', async () => {
    const user = userEvent.setup()
    render(<PatientsPage />, { wrapper: createWrapper() })

    // Wait for initial load
    await waitFor(() => {
      expect(screen.getByText('João Silva')).toBeInTheDocument()
    })

    // Search for specific patient
    const searchInput = screen.getByPlaceholderText(/search patients/i)
    await user.type(searchInput, 'Maria')

    // Verify search results
    await waitFor(() => {
      expect(screen.getByText('Maria Santos')).toBeInTheDocument()
      expect(screen.queryByText('João Silva')).not.toBeInTheDocument()
    })
  })

  it('creates new patient', async () => {
    const user = userEvent.setup()
    render(<PatientsPage />, { wrapper: createWrapper() })

    // Open create modal
    await user.click(screen.getByRole('button', { name: /add patient/i }))

    // Fill form
    await user.type(screen.getByLabelText(/nome/i), 'Carlos Oliveira')
    await user.type(screen.getByLabelText(/email/i), 'carlos@example.com')

    // Submit
    await user.click(screen.getByRole('button', { name: /save/i }))

    // Verify patient was created
    await waitFor(() => {
      expect(screen.getByText('Carlos Oliveira')).toBeInTheDocument()
    })
  })
})
```

## End-to-End Testing

### Playwright Configuration

**playwright.config.ts:**

```typescript
import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [
    ['html', { outputFolder: 'test-results/e2e-report' }],
    ['json', { outputFile: 'test-results/e2e-results.json' }],
    ['junit', { outputFile: 'test-results/e2e-junit.xml' }]
  ],
  use: {
    baseURL: process.env.PLAYWRIGHT_TEST_BASE_URL || 'http://localhost:4173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure'
  },

  projects: [
    {
      name: 'setup',
      testMatch: /.*\.setup\.ts/,
    },
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
      dependencies: ['setup'],
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
      dependencies: ['setup'],
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
      dependencies: ['setup'],
    },
    {
      name: 'Mobile Chrome',
      use: { ...devices['Pixel 5'] },
      dependencies: ['setup'],
    },
    {
      name: 'Mobile Safari',
      use: { ...devices['iPhone 12'] },
      dependencies: ['setup'],
    }
  ],

  webServer: {
    command: 'npm run preview',
    port: 4173,
    reuseExistingServer: !process.env.CI,
  }
})
```

### E2E Test Examples

**Authentication Flow** (`tests/e2e/auth.spec.ts`):

```typescript
import { test, expect } from '@playwright/test'

test.describe('Authentication', () => {
  test('user can login successfully', async ({ page }) => {
    await page.goto('/login')

    // Fill login form
    await page.fill('[name="email"]', 'admin@example.com')
    await page.fill('[name="password"]', 'admin123')

    // Submit form
    await page.click('button[type="submit"]')

    // Verify redirect to dashboard
    await expect(page).toHaveURL('/dashboard')
    await expect(page.locator('h1')).toContainText('Dashboard')
  })

  test('shows error for invalid credentials', async ({ page }) => {
    await page.goto('/login')

    // Fill with invalid credentials
    await page.fill('[name="email"]', 'invalid@example.com')
    await page.fill('[name="password"]', 'wrongpassword')

    await page.click('button[type="submit"]')

    // Verify error message
    await expect(page.locator('[role="alert"]'))
      .toContainText('Invalid credentials')
  })

  test('redirects to login when not authenticated', async ({ page }) => {
    await page.goto('/patients')
    await expect(page).toHaveURL('/login')
  })
})
```

**Patient Management** (`tests/e2e/patients.spec.ts`):

```typescript
import { test, expect } from '@playwright/test'

test.describe('Patient Management', () => {
  test.beforeEach(async ({ page }) => {
    // Login before each test
    await page.goto('/login')
    await page.fill('[name="email"]', 'admin@example.com')
    await page.fill('[name="password"]', 'admin123')
    await page.click('button[type="submit"]')
    await expect(page).toHaveURL('/dashboard')
  })

  test('can view patients list', async ({ page }) => {
    await page.goto('/patients')

    // Wait for patients to load
    await page.waitForSelector('[data-testid="patients-table"]')

    // Verify table headers
    await expect(page.locator('th')).toContainText(['Name', 'Email', 'Phone', 'Status'])

    // Verify at least one patient is visible
    const patientRows = page.locator('[data-testid="patient-row"]')
    await expect(patientRows).toHaveCountGreaterThan(0)
  })

  test('can create new patient', async ({ page }) => {
    await page.goto('/patients')

    // Click add patient button
    await page.click('[data-testid="add-patient-button"]')

    // Fill form in modal
    await page.fill('[name="name"]', 'Ana Costa')
    await page.fill('[name="email"]', 'ana@example.com')
    await page.fill('[name="phone"]', '+55 11 77777-7777')

    // Submit form
    await page.click('button[type="submit"]')

    // Wait for modal to close and list to refresh
    await page.waitForSelector('[data-testid="create-patient-modal"]', { state: 'hidden' })

    // Verify new patient appears in list
    await expect(page.locator('[data-testid="patients-table"]'))
      .toContainText('Ana Costa')
  })

  test('can search patients', async ({ page }) => {
    await page.goto('/patients')

    // Type in search field
    await page.fill('[name="search"]', 'João')

    // Wait for search results
    await page.waitForTimeout(500)

    // Verify filtered results
    const patientRows = page.locator('[data-testid="patient-row"]')
    await expect(patientRows).toHaveCount(1)
    await expect(patientRows.first()).toContainText('João Silva')
  })

  test('can view patient details', async ({ page }) => {
    await page.goto('/patients')

    // Click on first patient
    await page.click('[data-testid="patient-row"]:first-child')

    // Verify navigation to patient detail
    await expect(page).toHaveURL(/\/patients\/\w+/)

    // Verify patient detail tabs
    await expect(page.locator('[role="tablist"]'))
      .toContainText(['Overview', 'Messages', 'Flows'])
  })
})
```

**AI Features** (`tests/e2e/ai-features.spec.ts`):

```typescript
import { test, expect } from '@playwright/test'

test.describe('AI Features', () => {
  test.beforeEach(async ({ page }) => {
    // Login as physician (required for AI features)
    await page.goto('/login')
    await page.fill('[name="email"]', 'physician@example.com')
    await page.fill('[name="password"]', 'physician123')
    await page.click('button[type="submit"]')
  })

  test('physician can view AI insights', async ({ page }) => {
    // Navigate to patient detail
    await page.goto('/patients/patient-123')

    // Verify AI insights tab is visible
    await expect(page.locator('[role="tab"]:has-text("AI Insights")')).toBeVisible()

    // Click AI insights tab
    await page.click('[role="tab"]:has-text("AI Insights")')

    // Verify AI dashboard loads
    await expect(page.locator('[data-testid="ai-analytics-dashboard"]')).toBeVisible()

    // Verify dashboard sections
    await expect(page.locator('text="Insights"')).toBeVisible()
    await expect(page.locator('text="Recommendations"')).toBeVisible()
    await expect(page.locator('text="Engagement"')).toBeVisible()
  })

  test('non-physician cannot see AI insights', async ({ page }) => {
    // Logout and login as regular user
    await page.goto('/logout')
    await page.goto('/login')
    await page.fill('[name="email"]', 'user@example.com')
    await page.fill('[name="password"]', 'user123')
    await page.click('button[type="submit"]')

    // Navigate to patient detail
    await page.goto('/patients/patient-123')

    // Verify AI insights tab is not visible
    await expect(page.locator('[role="tab"]:has-text("AI Insights")')).not.toBeVisible()
  })
})
```

### Performance Testing

**Core Web Vitals** (`tests/performance/vitals.spec.ts`):

```typescript
import { test, expect } from '@playwright/test'

test.describe('Performance Tests', () => {
  test('page load performance', async ({ page }) => {
    // Navigate to dashboard
    const startTime = Date.now()
    await page.goto('/dashboard')
    await page.waitForLoadState('networkidle')
    const endTime = Date.now()

    const loadTime = endTime - startTime
    expect(loadTime).toBeLessThan(5000) // Should load within 5 seconds

    // Check Core Web Vitals
    const vitals = await page.evaluate(() => {
      return new Promise((resolve) => {
        new PerformanceObserver((list) => {
          const entries = list.getEntries()
          const metrics = {}

          entries.forEach((entry) => {
            if (entry.name === 'largest-contentful-paint') {
              metrics.lcp = entry.startTime
            }
            if (entry.name === 'first-input-delay') {
              metrics.fid = entry.processingStart - entry.startTime
            }
            if (entry.name === 'cumulative-layout-shift') {
              metrics.cls = entry.value
            }
          })

          resolve(metrics)
        }).observe({ entryTypes: ['largest-contentful-paint', 'first-input', 'layout-shift'] })

        setTimeout(() => resolve({}), 5000) // Timeout after 5 seconds
      })
    })

    // Verify Core Web Vitals thresholds
    if (vitals.lcp) expect(vitals.lcp).toBeLessThan(2500) // LCP < 2.5s
    if (vitals.fid) expect(vitals.fid).toBeLessThan(100)  // FID < 100ms
    if (vitals.cls) expect(vitals.cls).toBeLessThan(0.1)  // CLS < 0.1
  })

  test('memory usage', async ({ page }) => {
    await page.goto('/dashboard')

    // Get initial memory
    const initialMemory = await page.evaluate(() => {
      return (performance as any).memory?.usedJSHeapSize || 0
    })

    // Navigate through several pages
    await page.goto('/patients')
    await page.goto('/flows')
    await page.goto('/settings')
    await page.goto('/dashboard')

    // Get memory after navigation
    const finalMemory = await page.evaluate(() => {
      return (performance as any).memory?.usedJSHeapSize || 0
    })

    // Memory shouldn't increase by more than 50MB
    const memoryIncrease = finalMemory - initialMemory
    expect(memoryIncrease).toBeLessThan(50 * 1024 * 1024)
  })
})
```

### Visual Testing

**Screenshot Testing** (`tests/visual/screenshots.spec.ts`):

```typescript
import { test, expect } from '@playwright/test'

test.describe('Visual Regression', () => {
  test('dashboard appearance', async ({ page }) => {
    await page.goto('/dashboard')
    await page.waitForLoadState('networkidle')

    // Take full page screenshot
    await expect(page).toHaveScreenshot('dashboard-full.png', {
      fullPage: true
    })
  })

  test('patient list appearance', async ({ page }) => {
    await page.goto('/patients')
    await page.waitForSelector('[data-testid="patients-table"]')

    // Take screenshot of specific component
    await expect(page.locator('[data-testid="patients-table"]'))
      .toHaveScreenshot('patients-table.png')
  })

  test('modal appearance', async ({ page }) => {
    await page.goto('/patients')
    await page.click('[data-testid="add-patient-button"]')
    await page.waitForSelector('[data-testid="create-patient-modal"]')

    // Screenshot of modal
    await expect(page.locator('[data-testid="create-patient-modal"]'))
      .toHaveScreenshot('create-patient-modal.png')
  })
})
```

## Test Scripts

**package.json scripts:**

```json
{
  "scripts": {
    "test": "vitest",
    "test:watch": "vitest --watch",
    "test:coverage": "vitest run --coverage",
    "test:ui": "vitest --ui",
    "test:e2e": "playwright test",
    "test:e2e:ui": "playwright test --ui",
    "test:e2e:debug": "playwright test --debug",
    "test:performance": "playwright test --project=performance",
    "test:visual": "playwright test --project=visual",
    "test:all": "npm run test:coverage && npm run test:e2e"
  }
}
```

## CI/CD Integration

### GitHub Actions

**.github/workflows/test.yml:**

```yaml
name: Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: 18
          cache: 'npm'

      - name: Install dependencies
        run: npm ci

      - name: Run unit tests
        run: npm run test:coverage

      - name: Upload coverage reports
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage/lcov.info

  e2e-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: 18
          cache: 'npm'

      - name: Install dependencies
        run: npm ci

      - name: Install Playwright
        run: npx playwright install --with-deps

      - name: Build application
        run: npm run build

      - name: Run E2E tests
        run: npm run test:e2e
        env:
          PLAYWRIGHT_TEST_BASE_URL: http://localhost:4173

      - name: Upload test results
        uses: actions/upload-artifact@v3
        if: failure()
        with:
          name: playwright-report
          path: test-results/
          retention-days: 30
```

## Best Practices

### Writing Good Tests

1. **Test Behavior, Not Implementation**: Focus on what the user sees and does
2. **Use Descriptive Test Names**: Clearly describe what is being tested
3. **Arrange-Act-Assert**: Structure tests with clear setup, action, and verification
4. **Mock External Dependencies**: Isolate unit tests from external services
5. **Test Edge Cases**: Include error conditions and boundary values

### Test Maintenance

1. **Regular Updates**: Keep tests updated with application changes
2. **Remove Flaky Tests**: Fix or remove unreliable tests
3. **Optimize Performance**: Keep test suites fast and efficient
4. **Review Coverage**: Maintain good test coverage without obsessing over 100%
5. **Document Complex Tests**: Add comments for complex test scenarios

### Common Testing Patterns

**Page Object Model** (for E2E tests):

```typescript
// tests/pages/PatientPage.ts
export class PatientPage {
  constructor(private page: Page) {}

  async goto() {
    await this.page.goto('/patients')
  }

  async searchPatient(name: string) {
    await this.page.fill('[name="search"]', name)
  }

  async addPatient(patient: { name: string; email: string; phone: string }) {
    await this.page.click('[data-testid="add-patient-button"]')
    await this.page.fill('[name="name"]', patient.name)
    await this.page.fill('[name="email"]', patient.email)
    await this.page.fill('[name="phone"]', patient.phone)
    await this.page.click('button[type="submit"]')
  }

  async getPatientCount() {
    return await this.page.locator('[data-testid="patient-row"]').count()
  }
}
```

**Custom Render Function**:

```typescript
// tests/utils/custom-render.tsx
export const customRender = (
  ui: ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>
) => {
  const AllTheProviders = ({ children }: { children: React.ReactNode }) => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    })

    return (
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <ConfigProvider>
            <AuthProvider>
              {children}
            </AuthProvider>
          </ConfigProvider>
        </BrowserRouter>
      </QueryClientProvider>
    )
  }

  return render(ui, { wrapper: AllTheProviders, ...options })
}

// Re-export everything
export * from '@testing-library/react'

// Override render method
export { customRender as render }
```

## Troubleshooting

### Common Issues

**Tests Timing Out**:
- Increase timeout values in configuration
- Use proper wait conditions
- Check for memory leaks

**Flaky Tests**:
- Add proper wait conditions
- Mock time-dependent functionality
- Isolate test data

**Performance Issues**:
- Run tests in parallel when possible
- Use test.concurrent for independent tests
- Clean up resources properly

### Debugging

```typescript
// Add debug logging
test('debug example', async ({ page }) => {
  await page.goto('/patients')

  // Enable debug mode
  page.on('console', msg => console.log(`PAGE LOG: ${msg.text()}`))

  // Add debug screenshots
  await page.screenshot({ path: 'debug-screenshot.png' })

  // Pause for manual inspection
  await page.pause()
})
```

---

**Last Updated**: 2025-09-25
**Version**: 1.0.0
**Coverage Target**: 80%+
**Maintained By**: QA Team