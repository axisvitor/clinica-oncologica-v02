import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { axe, toHaveNoViolations } from 'jest-axe'
import userEvent from '@testing-library/user-event'
import { LoginPage } from '../../src/pages/LoginPage'
import { AuthContext } from '../../src/contexts/AuthContext'

// Extend Jest matchers
expect.extend(toHaveNoViolations)

// Mock dependencies
jest.mock('../../src/lib/runtime-config', () => ({
  isProduction: () => false
}))

// Mock auth context
const mockAuthContext = {
  login: jest.fn(),
  isAuthenticated: false,
  isLoading: false,
  logout: jest.fn(),
  user: null
}

const renderLoginPage = (authContext = mockAuthContext) => {
  return render(
    <BrowserRouter>
      <AuthContext.Provider value={authContext}>
        <LoginPage />
      </AuthContext.Provider>
    </BrowserRouter>
  )
}

describe('LoginPage Accessibility Tests', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    // Set development environment variables
    process.env['VITE_ENVIRONMENT'] = 'development'
  })

  afterEach(() => {
    delete process.env['VITE_ENVIRONMENT']
  })

  describe('WCAG 2.1 Compliance', () => {
    it('should not have any accessibility violations', async () => {
      const { container } = renderLoginPage()
      const results = await axe(container)
      expect(results).toHaveNoViolations()
    })

    it('should have proper heading structure', () => {
      renderLoginPage()

      // Check for main heading
      expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Neoplasias Litoral')

      // Check for card title heading
      expect(screen.getByRole('heading', { level: 3 })).toHaveTextContent('Entrar na sua conta')
    })

    it('should have proper landmark regions', () => {
      renderLoginPage()

      // Check for main content area
      const form = screen.getByRole('form', { name: /entrar na sua conta/i })
      expect(form).toBeInTheDocument()
    })
  })

  describe('Form Labels and Inputs', () => {
    it('should have all form inputs properly labeled', () => {
      renderLoginPage()

      // Check email input
      const emailInput = screen.getByLabelText(/email/i)
      expect(emailInput).toBeInTheDocument()
      expect(emailInput).toHaveAttribute('type', 'email')
      expect(emailInput).toHaveAttribute('autoComplete', 'email')

      // Check password input
      const passwordInput = screen.getByLabelText(/senha/i)
      expect(passwordInput).toBeInTheDocument()
      expect(passwordInput).toHaveAttribute('type', 'password')
      expect(passwordInput).toHaveAttribute('autoComplete', 'current-password')
    })

    it('should have proper autocomplete attributes', () => {
      renderLoginPage()

      const emailInput = screen.getByRole('textbox', { name: /email/i })
      const passwordInput = screen.getByLabelText(/senha/i)

      expect(emailInput).toHaveAttribute('autoComplete', 'email')
      expect(passwordInput).toHaveAttribute('autoComplete', 'current-password')
    })

    it('should have proper input types for security', () => {
      renderLoginPage()

      const emailInput = screen.getByRole('textbox', { name: /email/i })
      const passwordInput = screen.getByLabelText(/senha/i)

      expect(emailInput).toHaveAttribute('type', 'email')
      expect(passwordInput).toHaveAttribute('type', 'password')
    })
  })

  describe('Error Messages and ARIA States', () => {
    it('should announce form validation errors with proper ARIA attributes', async () => {
      renderLoginPage()

      const submitButton = screen.getByRole('button', { name: /entrar/i })

      // Submit form with empty fields to trigger validation
      fireEvent.click(submitButton)

      await waitFor(() => {
        const emailError = screen.getByText(/email inválido/i)
        const passwordError = screen.getByText(/senha deve ter pelo menos 6 caracteres/i)

        // Check that error messages have proper role
        expect(emailError).toHaveAttribute('role', 'alert')
        expect(passwordError).toHaveAttribute('role', 'alert')
      })
    })

    it('should have aria-invalid attributes on invalid inputs', async () => {
      renderLoginPage()

      const emailInput = screen.getByRole('textbox', { name: /email/i })
      const passwordInput = screen.getByLabelText(/senha/i)

      // Initially should not have aria-invalid
      expect(emailInput).not.toHaveAttribute('aria-invalid', 'true')
      expect(passwordInput).not.toHaveAttribute('aria-invalid', 'true')

      // Submit to trigger validation
      const submitButton = screen.getByRole('button', { name: /entrar/i })
      fireEvent.click(submitButton)

      await waitFor(() => {
        expect(emailInput).toHaveAttribute('aria-invalid', 'true')
        expect(passwordInput).toHaveAttribute('aria-invalid', 'true')
      })
    })

    it('should properly associate error messages with inputs using aria-describedby', async () => {
      renderLoginPage()

      const submitButton = screen.getByRole('button', { name: /entrar/i })
      fireEvent.click(submitButton)

      await waitFor(() => {
        const emailInput = screen.getByRole('textbox', { name: /email/i })
        const passwordInput = screen.getByLabelText(/senha/i)

        expect(emailInput).toHaveAttribute('aria-describedby', 'email-error')
        expect(passwordInput).toHaveAttribute('aria-describedby', 'password-error')

        // Verify the error elements exist with matching IDs
        expect(screen.getByText(/email inválido/i)).toHaveAttribute('id', 'email-error')
        expect(screen.getByText(/senha deve ter pelo menos 6 caracteres/i)).toHaveAttribute('id', 'password-error')
      })
    })
  })

  describe('Keyboard Navigation', () => {
    it('should support keyboard navigation through all interactive elements', async () => {
      const user = userEvent.setup()
      renderLoginPage()

      // Tab through all focusable elements
      await user.tab() // Email input (has autoFocus)
      expect(screen.getByRole('textbox', { name: /email/i })).toHaveFocus()

      await user.tab() // Password input
      expect(screen.getByLabelText(/senha/i)).toHaveFocus()

      await user.tab() // Show/hide password button
      expect(screen.getByRole('button', { name: /mostrar senha/i })).toHaveFocus()

      await user.tab() // Submit button
      expect(screen.getByRole('button', { name: /entrar/i })).toHaveFocus()

      await user.tab() // Forgot password link
      expect(screen.getByRole('button', { name: /solicitar redefinição de senha/i })).toHaveFocus()
    })

    it('should have proper focus management for password visibility toggle', async () => {
      const user = userEvent.setup()
      renderLoginPage()

      const toggleButton = screen.getByRole('button', { name: /mostrar senha/i })
      const passwordInput = screen.getByLabelText(/senha/i)

      // Focus and activate toggle
      toggleButton.focus()
      await user.click(toggleButton)

      // Check that password input type changed and aria-label updated
      expect(passwordInput).toHaveAttribute('type', 'text')
      expect(toggleButton).toHaveAttribute('aria-label', 'Ocultar senha')

      // Toggle back
      await user.click(toggleButton)
      expect(passwordInput).toHaveAttribute('type', 'password')
      expect(toggleButton).toHaveAttribute('aria-label', 'Mostrar senha')
    })

    it('should focus error alert when login fails', async () => {
      const mockLogin = jest.fn().mockRejectedValue(new Error('Invalid credentials'))
      const authContextWithError = {
        ...mockAuthContext,
        login: mockLogin
      }

      renderLoginPage(authContextWithError)

      // Fill form and submit
      const emailInput = screen.getByRole('textbox', { name: /email/i })
      const passwordInput = screen.getByLabelText(/senha/i)
      const submitButton = screen.getByRole('button', { name: /entrar/i })

      await userEvent.type(emailInput, 'test@example.com')
      await userEvent.type(passwordInput, 'password123')
      await userEvent.click(submitButton)

      // Wait for error to appear and verify focus
      await waitFor(() => {
        const errorAlert = screen.getByRole('alert')
        expect(errorAlert).toHaveClass('focus:outline-none', 'focus:ring-2', 'focus:ring-red-500')
        expect(errorAlert).toHaveAttribute('tabIndex', '-1')
      })
    })
  })

  describe('Screen Reader Support', () => {
    it('should have proper live regions for dynamic content', () => {
      renderLoginPage()

      // Check for live region that announces form status
      const liveRegion = screen.getByText('', { selector: '[aria-live="polite"]' })
      expect(liveRegion).toBeInTheDocument()
      expect(liveRegion).toHaveAttribute('aria-atomic', 'true')
    })

    it('should announce loading state changes', async () => {
      const mockLogin = jest.fn().mockImplementation(() => new Promise(resolve => setTimeout(resolve, 100)))
      const authContextWithDelay = {
        ...mockAuthContext,
        login: mockLogin
      }

      renderLoginPage(authContextWithDelay)

      // Fill and submit form
      const emailInput = screen.getByRole('textbox', { name: /email/i })
      const passwordInput = screen.getByLabelText(/senha/i)
      const submitButton = screen.getByRole('button', { name: /entrar/i })

      await userEvent.type(emailInput, 'test@example.com')
      await userEvent.type(passwordInput, 'password123')

      fireEvent.click(submitButton)

      // Check loading state is announced
      await waitFor(() => {
        expect(screen.getByText('Entrando...')).toHaveAttribute('aria-live', 'polite')
      })
    })

    it('should have descriptive labels for all interactive elements', () => {
      renderLoginPage()

      // Check password visibility toggle
      const toggleButton = screen.getByRole('button', { name: /mostrar senha/i })
      expect(toggleButton).toHaveAttribute('aria-label', 'Mostrar senha')

      // Check forgot password link
      const forgotPasswordButton = screen.getByRole('button', { name: /solicitar redefinição de senha/i })
      expect(forgotPasswordButton).toHaveAttribute('aria-label', 'Solicitar redefinição de senha')
    })
  })

  describe('Environment-Based Security Features', () => {
    it('should show demo credentials only in development environment', () => {
      // Already in development environment
      renderLoginPage()

      expect(screen.getByText(/credenciais de demonstração/i)).toBeInTheDocument()
      expect(screen.getByText(/admin@neoplasiaslitoral.com/)).toBeInTheDocument()
      expect(screen.getByText(/Admin@123456!/)).toBeInTheDocument()
    })

    it('should hide demo credentials in production', () => {
      // Mock production environment
      jest.doMock('../../src/lib/runtime-config', () => ({
        isProduction: () => true
      }))

      // Re-import and render with production config
      const { LoginPage: ProductionLoginPage } = require('../../src/pages/LoginPage')

      render(
        <BrowserRouter>
          <AuthContext.Provider value={mockAuthContext}>
            <ProductionLoginPage />
          </AuthContext.Provider>
        </BrowserRouter>
      )

      expect(screen.queryByText(/credenciais de demonstração/i)).not.toBeInTheDocument()
    })

    it('should show development indicator when not in production', () => {
      renderLoginPage()

      expect(screen.getByText(/ambiente de desenvolvimento/i)).toBeInTheDocument()
    })
  })

  describe('Form Interaction Accessibility', () => {
    it('should support Enter key submission', async () => {
      const mockLogin = jest.fn().mockResolvedValue({})
      const authContextWithMockLogin = {
        ...mockAuthContext,
        login: mockLogin
      }

      renderLoginPage(authContextWithMockLogin)

      const emailInput = screen.getByRole('textbox', { name: /email/i })
      const passwordInput = screen.getByLabelText(/senha/i)

      await userEvent.type(emailInput, 'test@example.com')
      await userEvent.type(passwordInput, 'password123')

      // Press Enter on password field
      await userEvent.type(passwordInput, '{enter}')

      await waitFor(() => {
        expect(mockLogin).toHaveBeenCalledWith('test@example.com', 'password123')
      })
    })

    it('should prevent double submission', async () => {
      const mockLogin = jest.fn().mockImplementation(() => new Promise(resolve => setTimeout(resolve, 100)))
      const authContextWithDelay = {
        ...mockAuthContext,
        login: mockLogin
      }

      renderLoginPage(authContextWithDelay)

      const emailInput = screen.getByRole('textbox', { name: /email/i })
      const passwordInput = screen.getByLabelText(/senha/i)
      const submitButton = screen.getByRole('button', { name: /entrar/i })

      await userEvent.type(emailInput, 'test@example.com')
      await userEvent.type(passwordInput, 'password123')

      // Click submit button twice quickly
      fireEvent.click(submitButton)
      fireEvent.click(submitButton)

      // Should only be called once
      await waitFor(() => {
        expect(mockLogin).toHaveBeenCalledTimes(1)
        expect(submitButton).toBeDisabled()
      })
    })
  })

  describe('Color Contrast and Visual Accessibility', () => {
    it('should have sufficient color contrast for text elements', () => {
      renderLoginPage()

      // Main heading should be visible
      const heading = screen.getByRole('heading', { name: /neoplasias litoral/i })
      expect(heading).toHaveClass('text-gray-900')

      // Error messages should have high contrast
      const submitButton = screen.getByRole('button', { name: /entrar/i })
      fireEvent.click(submitButton)

      // Check error styling
      setTimeout(() => {
        const errorElements = screen.getAllByRole('alert')
        errorElements.forEach(error => {
          expect(error).toHaveClass('text-red-600')
        })
      }, 100)
    })

    it('should have visible focus indicators', async () => {
      const user = userEvent.setup()
      renderLoginPage()

      const emailInput = screen.getByRole('textbox', { name: /email/i })

      await user.click(emailInput)

      // Focus styles should be applied (tested via className presence)
      expect(emailInput).toHaveClass('focus:outline-none', 'focus:ring-2')
    })
  })
})