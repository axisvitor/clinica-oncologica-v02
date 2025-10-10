# Frontend Testing Suite

This directory contains comprehensive tests for the frontend components and hooks of the Clínica Oncológica application.

## Test Structure

```
tests/
├── setup.ts                      # Test configuration and global mocks
├── test-utils/                   # Testing utilities and providers
│   ├── test-setup.tsx            # React providers and test helpers
│   └── mock-providers.tsx        # Mock implementations for contexts
├── unit/                         # Unit tests
│   ├── components/               # Component tests
│   │   ├── auth/                 # Authentication component tests
│   │   │   ├── ProtectedRoute.test.tsx
│   │   │   └── ReAuthenticationModal.test.tsx
│   │   ├── quiz/                 # Quiz component tests
│   │   │   └── QuizForm.test.tsx
│   │   └── patient/              # Patient component tests
│   │       └── CreatePatientDialog.test.tsx
│   └── hooks/                    # Hook tests
│       ├── useAuth.test.ts       # Authentication hook tests
│       ├── useWebSocket.test.ts  # WebSocket hook tests
│       └── useApi.test.ts        # API hook tests
├── integration/                  # Integration tests
├── accessibility/                # Accessibility tests
└── performance/                  # Performance tests
```

## Test Coverage

Our test suite focuses on critical UI components and hooks with the following coverage:

### Authentication Components
- **ProtectedRoute**: Role-based access control, authentication states, error handling
- **ReAuthenticationModal**: Password confirmation flows, form validation, security

### Quiz Components
- **QuizForm**: Multi-question types, progress tracking, validation, submission

### Patient Management
- **CreatePatientDialog**: Form validation, API integration, error handling

### Custom Hooks
- **useAuth**: Authentication state, permissions, retry logic
- **useWebSocket**: Connection management, message handling, reconnection
- **useApi**: Data fetching, caching, error recovery

## Running Tests

### All Tests
```bash
npm test
```

### Specific Test Types
```bash
# Unit tests only
npm run test:unit

# Integration tests
npm run test:integration

# Watch mode for development
npm run test:watch

# Coverage report
npm run test:coverage
```

### Test Specific Files
```bash
# Test specific component
npm test ProtectedRoute

# Test specific hook
npm test useAuth

# Test with verbose output
npm test -- --verbose
```

## Test Utilities

### TestWrapper
Provides all necessary providers for testing React components:

```tsx
import { renderWithProviders } from '../test-utils/test-setup'

test('component renders correctly', () => {
  renderWithProviders(<MyComponent />)
  // test assertions
})
```

### Mock Data Helpers
Pre-configured mock data for consistent testing:

```tsx
import { createTestUser, createMockPatient } from '../test-utils/test-setup'

const user = createTestUser({ role: 'admin' })
const patient = createMockPatient({ name: 'Test Patient' })
```

### Authentication Testing
Mock authentication states for different scenarios:

```tsx
import { MockAuthProvider } from '../test-utils/test-setup'

// Test as authenticated user
renderWithProviders(<Component />, {
  authValue: {
    user: createTestUser(),
    isAuthenticated: true
  }
})

// Test as unauthenticated
renderWithProviders(<Component />, {
  authValue: {
    user: null,
    isAuthenticated: false
  }
})
```

## Testing Best Practices

### Component Testing
1. **Test behavior, not implementation**
2. **Use accessible queries** (getByRole, getByLabelText)
3. **Test user interactions** with fireEvent and userEvent
4. **Mock external dependencies** properly
5. **Test error states** and edge cases

### Hook Testing
1. **Use renderHook** from @testing-library/react
2. **Test all return values** and state changes
3. **Mock dependencies** with vi.mock()
4. **Test async operations** with waitFor()
5. **Test cleanup** and unmounting behavior

### API Testing
1. **Mock API responses** consistently
2. **Test loading states** and error handling
3. **Test cache behavior** with React Query
4. **Verify request parameters** and headers
5. **Test retry logic** and timeouts

## Mock Implementations

### API Client
All API calls are mocked with realistic responses:

```tsx
// Successful response
mockApiClient.patients.create.mockResolvedValue({
  id: '1',
  name: 'Test Patient',
  status: 'active'
})

// Error response
mockApiClient.patients.create.mockRejectedValue({
  status: 400,
  data: { message: 'Invalid data' }
})
```

### WebSocket
WebSocket connections are mocked for testing real-time features:

```tsx
import { MockWebSocket } from '../test-utils/mock-providers'

// Simulate incoming message
mockWebSocket.simulateMessage({
  type: 'patient_update',
  data: { patientId: '1', status: 'updated' }
})
```

### Authentication
Firebase authentication is mocked with controllable states:

```tsx
// Mock successful login
mockAuth.login.mockResolvedValue({
  user: { id: '1', email: 'test@example.com' },
  session: { access_token: 'token' }
})
```

## Accessibility Testing

### Custom Matchers
Extended expect matchers for accessibility:

```tsx
// Check basic accessibility requirements
expect(component).toBeAccessible()

// Check form structure
expect(form).toHaveValidForm()

// Check loading states
expect(element).toBeLoadingState()
```

### Screen Reader Testing
Test components with screen reader considerations:

```tsx
// Use accessible queries
const button = screen.getByRole('button', { name: 'Submit Form' })
const input = screen.getByLabelText('Patient Name')

// Check ARIA attributes
expect(button).toHaveAttribute('aria-disabled', 'false')
expect(input).toHaveAttribute('aria-required', 'true')
```

## Performance Testing

### Render Performance
Test component render times:

```tsx
import { measureRenderTime } from '../test-utils/test-setup'

test('component renders within performance budget', () => {
  const renderTime = measureRenderTime(() => {
    render(<ExpensiveComponent />)
  })

  expect(renderTime).toBeLessThan(100) // 100ms budget
})
```

### Memory Leaks
Test for proper cleanup:

```tsx
test('component cleans up properly', () => {
  const { unmount } = render(<ComponentWithSubscriptions />)

  // Verify subscriptions are cleaned up
  unmount()
  expect(mockWebSocket.close).toHaveBeenCalled()
})
```

## Debugging Tests

### Debug Utilities
```tsx
import { screen } from '@testing-library/react'

// Debug what's rendered
screen.debug()

// Debug specific element
screen.debug(screen.getByRole('button'))

// Log queries
screen.logTestingPlaygroundURL()
```

### Common Issues

1. **Element not found**: Use `waitFor()` for async elements
2. **Act warnings**: Wrap state updates in `act()`
3. **Memory leaks**: Check cleanup in `useEffect`
4. **Flaky tests**: Use fake timers with `vi.useFakeTimers()`

## CI/CD Integration

Tests run automatically on:
- Pull requests
- Main branch pushes
- Pre-commit hooks

Coverage thresholds:
- Statements: 80%
- Branches: 75%
- Functions: 80%
- Lines: 80%

## Contributing

When adding new tests:

1. Follow the existing patterns and structure
2. Use descriptive test names that explain the scenario
3. Include both happy path and error cases
4. Add accessibility tests for UI components
5. Update this README if adding new test types

## Dependencies

- **Vitest**: Test runner
- **@testing-library/react**: React testing utilities
- **@testing-library/jest-dom**: Extended matchers
- **@testing-library/user-event**: User interaction simulation
- **React Query**: Data fetching and caching
- **React Router**: Navigation testing

## Resources

- [Testing Library Documentation](https://testing-library.com/)
- [Vitest Documentation](https://vitest.dev/)
- [React Testing Best Practices](https://kentcdodds.com/blog/common-mistakes-with-react-testing-library)
- [Accessibility Testing Guide](https://www.w3.org/WAI/WCAG21/quickref/)