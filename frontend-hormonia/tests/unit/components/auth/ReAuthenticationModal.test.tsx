import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ReAuthenticationModal } from '@/components/auth/ReAuthenticationModal'

// Mock UI components
vi.mock('@/components/ui/dialog', () => ({
  Dialog: ({ children, open, onOpenChange }: any) =>
    open ? <div data-testid="dialog" onClick={() => onOpenChange?.(false)}>{children}</div> : null,
  DialogContent: ({ children }: any) => <div data-testid="dialog-content">{children}</div>,
  DialogDescription: ({ children }: any) => <div data-testid="dialog-description">{children}</div>,
  DialogHeader: ({ children }: any) => <div data-testid="dialog-header">{children}</div>,
  DialogTitle: ({ children }: any) => <h2 data-testid="dialog-title">{children}</h2>,
}))

vi.mock('@/components/ui/form', () => ({
  Form: ({ children, ...props }: any) => <form data-testid="form" {...props}>{children}</form>,
  FormControl: ({ children }: any) => <div data-testid="form-control">{children}</div>,
  FormField: ({ render, control, name }: any) => {
    const field = { name, value: '', onChange: vi.fn(), onBlur: vi.fn() }
    return render({ field })
  },
  FormItem: ({ children }: any) => <div data-testid="form-item">{children}</div>,
  FormLabel: ({ children }: any) => <label data-testid="form-label">{children}</label>,
  FormMessage: ({ children }: any) => children ? <div data-testid="form-message">{children}</div> : null,
}))

vi.mock('@/components/ui/input', () => ({
  Input: (props: any) => <input data-testid="password-input" {...props} />,
}))

vi.mock('@/components/ui/button', () => ({
  Button: ({ children, onClick, disabled, type, variant, ...props }: any) => (
    <button
      data-testid={variant === 'outline' ? 'cancel-button' : 'confirm-button'}
      onClick={onClick}
      disabled={disabled}
      type={type}
      {...props}
    >
      {children}
    </button>
  ),
}))

vi.mock('@/components/ui/alert', () => ({
  Alert: ({ children, variant }: any) => (
    <div data-testid="alert" data-variant={variant}>{children}</div>
  ),
  AlertDescription: ({ children }: any) => (
    <div data-testid="alert-description">{children}</div>
  ),
}))

vi.mock('lucide-react', () => ({
  Loader2: () => <div data-testid="loader-icon" />,
  Shield: () => <div data-testid="shield-icon" />,
  AlertCircle: () => <div data-testid="alert-circle-icon" />,
}))

// Mock react-hook-form
const mockReset = vi.fn()
const mockHandleSubmit = vi.fn()
const mockForm = {
  control: {},
  handleSubmit: mockHandleSubmit,
  reset: mockReset,
}

vi.mock('react-hook-form', () => ({
  useForm: () => mockForm,
}))

vi.mock('@hookform/resolvers/zod', () => ({
  zodResolver: () => vi.fn(),
}))

describe('ReAuthenticationModal', () => {
  const defaultProps = {
    open: true,
    onOpenChange: vi.fn(),
    onSuccess: vi.fn(),
  }

  beforeEach(() => {
    vi.clearAllMocks()
    mockHandleSubmit.mockImplementation((fn) => (e) => {
      e?.preventDefault()
      fn({ password: 'test-password' })
    })
  })

  describe('Rendering', () => {
    it('should render modal when open', () => {
      render(<ReAuthenticationModal {...defaultProps} />)

      expect(screen.getByTestId('dialog')).toBeInTheDocument()
      expect(screen.getByTestId('dialog-title')).toHaveTextContent('Confirmar identidade')
      expect(screen.getByTestId('dialog-description')).toHaveTextContent(
        'Por segurança, confirme sua senha atual antes de continuar.'
      )
    })

    it('should not render modal when closed', () => {
      render(<ReAuthenticationModal {...defaultProps} open={false} />)

      expect(screen.queryByTestId('dialog')).not.toBeInTheDocument()
    })

    it('should render custom title and description', () => {
      const customProps = {
        ...defaultProps,
        title: 'Custom Title',
        description: 'Custom description text',
      }

      render(<ReAuthenticationModal {...customProps} />)

      expect(screen.getByTestId('dialog-title')).toHaveTextContent('Custom Title')
      expect(screen.getByTestId('dialog-description')).toHaveTextContent('Custom description text')
    })

    it('should render error message when provided', () => {
      const propsWithError = {
        ...defaultProps,
        error: 'Invalid password',
      }

      render(<ReAuthenticationModal {...propsWithError} />)

      expect(screen.getByTestId('alert')).toBeInTheDocument()
      expect(screen.getByTestId('alert')).toHaveAttribute('data-variant', 'destructive')
      expect(screen.getByTestId('alert-description')).toHaveTextContent('Invalid password')
    })

    it('should not render error alert when error is null', () => {
      render(<ReAuthenticationModal {...defaultProps} error={null} />)

      expect(screen.queryByTestId('alert')).not.toBeInTheDocument()
    })
  })

  describe('Form Elements', () => {
    it('should render password input with correct attributes', () => {
      render(<ReAuthenticationModal {...defaultProps} />)

      const passwordInput = screen.getByTestId('password-input')
      expect(passwordInput).toHaveAttribute('type', 'password')
      expect(passwordInput).toHaveAttribute('placeholder', 'Digite sua senha atual')
      expect(passwordInput).toHaveAttribute('autoComplete', 'current-password')
      expect(passwordInput).toHaveAttribute('autoFocus')
    })

    it('should render form label', () => {
      render(<ReAuthenticationModal {...defaultProps} />)

      expect(screen.getByTestId('form-label')).toHaveTextContent('Senha atual')
    })

    it('should render action buttons', () => {
      render(<ReAuthenticationModal {...defaultProps} />)

      expect(screen.getByTestId('cancel-button')).toHaveTextContent('Cancelar')
      expect(screen.getByTestId('confirm-button')).toHaveTextContent('Confirmar')
    })
  })

  describe('Form Submission', () => {
    it('should call onSuccess with password when form is submitted', async () => {
      const onSuccess = vi.fn().mockResolvedValue(undefined)
      render(<ReAuthenticationModal {...defaultProps} onSuccess={onSuccess} />)

      const form = screen.getByTestId('form')
      fireEvent.submit(form)

      await waitFor(() => {
        expect(onSuccess).toHaveBeenCalledWith('test-password')
      })
    })

    it('should reset form after successful submission', async () => {
      const onSuccess = vi.fn().mockResolvedValue(undefined)
      render(<ReAuthenticationModal {...defaultProps} onSuccess={onSuccess} />)

      const form = screen.getByTestId('form')
      fireEvent.submit(form)

      await waitFor(() => {
        expect(mockReset).toHaveBeenCalled()
      })
    })

    it('should handle async onSuccess function', async () => {
      const onSuccess = vi.fn().mockImplementation(() =>
        new Promise(resolve => setTimeout(resolve, 100))
      )
      render(<ReAuthenticationModal {...defaultProps} onSuccess={onSuccess} />)

      const form = screen.getByTestId('form')
      fireEvent.submit(form)

      // Should show loading state
      expect(screen.getByTestId('confirm-button')).toHaveTextContent('Verificando...')
      expect(screen.getByTestId('loader-icon')).toBeInTheDocument()

      await waitFor(() => {
        expect(onSuccess).toHaveBeenCalled()
      })
    })

    it('should handle submission errors gracefully', async () => {
      const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
      const onSuccess = vi.fn().mockRejectedValue(new Error('Test error'))
      render(<ReAuthenticationModal {...defaultProps} onSuccess={onSuccess} />)

      const form = screen.getByTestId('form')
      fireEvent.submit(form)

      await waitFor(() => {
        expect(consoleError).toHaveBeenCalledWith('Re-authentication error:', expect.any(Error))
      })

      consoleError.mockRestore()
    })
  })

  describe('Loading State', () => {
    it('should disable inputs and buttons during submission', async () => {
      const onSuccess = vi.fn().mockImplementation(() =>
        new Promise(resolve => setTimeout(resolve, 100))
      )
      render(<ReAuthenticationModal {...defaultProps} onSuccess={onSuccess} />)

      const form = screen.getByTestId('form')
      fireEvent.submit(form)

      // Check loading state
      expect(screen.getByTestId('password-input')).toBeDisabled()
      expect(screen.getByTestId('cancel-button')).toBeDisabled()
      expect(screen.getByTestId('confirm-button')).toBeDisabled()

      await waitFor(() => {
        expect(onSuccess).toHaveBeenCalled()
      })
    })

    it('should show loading text and icon during submission', async () => {
      const onSuccess = vi.fn().mockImplementation(() =>
        new Promise(resolve => setTimeout(resolve, 100))
      )
      render(<ReAuthenticationModal {...defaultProps} onSuccess={onSuccess} />)

      const form = screen.getByTestId('form')
      fireEvent.submit(form)

      expect(screen.getByTestId('confirm-button')).toHaveTextContent('Verificando...')
      expect(screen.getByTestId('loader-icon')).toBeInTheDocument()

      await waitFor(() => {
        expect(onSuccess).toHaveBeenCalled()
      })
    })
  })

  describe('Modal Interactions', () => {
    it('should call onOpenChange when cancel button is clicked', () => {
      const onOpenChange = vi.fn()
      render(<ReAuthenticationModal {...defaultProps} onOpenChange={onOpenChange} />)

      fireEvent.click(screen.getByTestId('cancel-button'))

      expect(onOpenChange).toHaveBeenCalledWith(false)
    })

    it('should reset form when modal is closed', () => {
      const onOpenChange = vi.fn()
      render(<ReAuthenticationModal {...defaultProps} onOpenChange={onOpenChange} />)

      fireEvent.click(screen.getByTestId('cancel-button'))

      expect(mockReset).toHaveBeenCalled()
    })

    it('should not reset form when modal opens', () => {
      const onOpenChange = vi.fn()
      render(<ReAuthenticationModal {...defaultProps} onOpenChange={onOpenChange} />)

      // Simulate opening (no close action)
      expect(mockReset).not.toHaveBeenCalled()
    })
  })

  describe('Icons', () => {
    it('should display shield icon in header', () => {
      render(<ReAuthenticationModal {...defaultProps} />)

      expect(screen.getByTestId('shield-icon')).toBeInTheDocument()
    })

    it('should display alert circle icon when error is present', () => {
      render(<ReAuthenticationModal {...defaultProps} error="Test error" />)

      expect(screen.getByTestId('alert-circle-icon')).toBeInTheDocument()
    })

    it('should display shield icon in confirm button when not loading', () => {
      render(<ReAuthenticationModal {...defaultProps} />)

      expect(screen.getByTestId('confirm-button')).toContainElement(
        screen.getByTestId('shield-icon')
      )
    })
  })

  describe('Accessibility', () => {
    it('should have proper form structure', () => {
      render(<ReAuthenticationModal {...defaultProps} />)

      expect(screen.getByTestId('form')).toBeInTheDocument()
      expect(screen.getByTestId('form-item')).toBeInTheDocument()
      expect(screen.getByTestId('form-control')).toBeInTheDocument()
      expect(screen.getByTestId('form-label')).toBeInTheDocument()
    })

    it('should have submit button with correct type', () => {
      render(<ReAuthenticationModal {...defaultProps} />)

      expect(screen.getByTestId('confirm-button')).toHaveAttribute('type', 'submit')
    })

    it('should have cancel button with button type', () => {
      render(<ReAuthenticationModal {...defaultProps} />)

      expect(screen.getByTestId('cancel-button')).toHaveAttribute('type', 'button')
    })
  })
})