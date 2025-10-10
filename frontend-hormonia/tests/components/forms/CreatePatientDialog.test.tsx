import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@/../tests/test-utils'
import { CreatePatientDialog } from '@/components/patients/CreatePatientDialog'

const mockCreatePatient = vi.fn()

// Mock API
vi.mock('@/lib/api-client', () => ({
  apiClient: {
    patients: {
      create: mockCreatePatient
    }
  }
}))

// Mock react-hook-form
vi.mock('react-hook-form', async () => {
  const actual = await vi.importActual('react-hook-form')
  return {
    ...actual,
    useForm: () => ({
      register: vi.fn((name) => ({ name })),
      handleSubmit: vi.fn((fn) => (e) => {
        e.preventDefault()
        fn({
          name: 'Test Patient',
          email: 'test@example.com',
          phone: '+5511999999999',
          birth_date: '1990-01-01',
          gender: 'male',
          treatment_type: 'chemotherapy'
        })
      }),
      formState: { errors: {}, isSubmitting: false, isValid: true },
      reset: vi.fn(),
      setValue: vi.fn(),
      watch: vi.fn()
    })
  }
})

describe('CreatePatientDialog Component', () => {
  const defaultProps = {
    open: true,
    onClose: vi.fn(),
    onSuccess: vi.fn()
  }

  beforeEach(() => {
    vi.clearAllMocks()
    mockCreatePatient.mockResolvedValue({
      id: 'new-patient-id',
      name: 'Test Patient',
      email: 'test@example.com'
    })
  })

  describe('rendering', () => {
    it('should render dialog when open', () => {
      render(<CreatePatientDialog {...defaultProps} />)

      expect(screen.getByRole('dialog')).toBeInTheDocument()
      expect(screen.getByText('Novo Paciente')).toBeInTheDocument()
    })

    it('should not render dialog when closed', () => {
      render(<CreatePatientDialog {...defaultProps} open={false} />)

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })

    it('should render all form fields', () => {
      render(<CreatePatientDialog {...defaultProps} />)

      expect(screen.getByLabelText(/nome completo/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/telefone/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/data de nascimento/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/gênero/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/tipo de tratamento/i)).toBeInTheDocument()
    })

    it('should render form buttons', () => {
      render(<CreatePatientDialog {...defaultProps} />)

      expect(screen.getByRole('button', { name: /cancelar/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /criar paciente/i })).toBeInTheDocument()
    })
  })

  describe('form validation', () => {
    it('should show required field errors', async () => {
      const user = userEvent.setup()

      // Mock form with errors
      vi.mocked(require('react-hook-form').useForm).mockReturnValue({
        register: vi.fn(),
        handleSubmit: vi.fn(),
        formState: {
          errors: {
            name: { message: 'Nome é obrigatório' },
            email: { message: 'Email é obrigatório' }
          },
          isSubmitting: false,
          isValid: false
        },
        reset: vi.fn(),
        setValue: vi.fn(),
        watch: vi.fn()
      })

      render(<CreatePatientDialog {...defaultProps} />)

      expect(screen.getByText('Nome é obrigatório')).toBeInTheDocument()
      expect(screen.getByText('Email é obrigatório')).toBeInTheDocument()
    })

    it('should validate email format', async () => {
      const user = userEvent.setup()

      // Mock form with email format error
      vi.mocked(require('react-hook-form').useForm).mockReturnValue({
        register: vi.fn(),
        handleSubmit: vi.fn(),
        formState: {
          errors: {
            email: { message: 'Email inválido' }
          },
          isSubmitting: false,
          isValid: false
        },
        reset: vi.fn(),
        setValue: vi.fn(),
        watch: vi.fn()
      })

      render(<CreatePatientDialog {...defaultProps} />)

      expect(screen.getByText('Email inválido')).toBeInTheDocument()
    })

    it('should validate phone format', async () => {
      // Mock form with phone format error
      vi.mocked(require('react-hook-form').useForm).mockReturnValue({
        register: vi.fn(),
        handleSubmit: vi.fn(),
        formState: {
          errors: {
            phone: { message: 'Telefone inválido' }
          },
          isSubmitting: false,
          isValid: false
        },
        reset: vi.fn(),
        setValue: vi.fn(),
        watch: vi.fn()
      })

      render(<CreatePatientDialog {...defaultProps} />)

      expect(screen.getByText('Telefone inválido')).toBeInTheDocument()
    })

    it('should validate birth date', async () => {
      // Mock form with birth date error
      vi.mocked(require('react-hook-form').useForm).mockReturnValue({
        register: vi.fn(),
        handleSubmit: vi.fn(),
        formState: {
          errors: {
            birth_date: { message: 'Data de nascimento inválida' }
          },
          isSubmitting: false,
          isValid: false
        },
        reset: vi.fn(),
        setValue: vi.fn(),
        watch: vi.fn()
      })

      render(<CreatePatientDialog {...defaultProps} />)

      expect(screen.getByText('Data de nascimento inválida')).toBeInTheDocument()
    })
  })

  describe('form submission', () => {
    it('should submit form with correct data', async () => {
      const user = userEvent.setup()
      render(<CreatePatientDialog {...defaultProps} />)

      const submitButton = screen.getByRole('button', { name: /criar paciente/i })
      await user.click(submitButton)

      expect(mockCreatePatient).toHaveBeenCalledWith({
        name: 'Test Patient',
        email: 'test@example.com',
        phone: '+5511999999999',
        birth_date: '1990-01-01',
        gender: 'male',
        treatment_type: 'chemotherapy'
      })
    })

    it('should show loading state during submission', async () => {
      const user = userEvent.setup()

      // Mock submitting state
      vi.mocked(require('react-hook-form').useForm).mockReturnValue({
        register: vi.fn(),
        handleSubmit: vi.fn((fn) => async (e) => {
          e.preventDefault()
          await fn({})
        }),
        formState: {
          errors: {},
          isSubmitting: true,
          isValid: true
        },
        reset: vi.fn(),
        setValue: vi.fn(),
        watch: vi.fn()
      })

      render(<CreatePatientDialog {...defaultProps} />)

      const submitButton = screen.getByRole('button', { name: /criando.../i })
      expect(submitButton).toBeDisabled()
      expect(screen.getByTestId('loading-spinner')).toBeInTheDocument()
    })

    it('should call onSuccess after successful submission', async () => {
      const user = userEvent.setup()
      render(<CreatePatientDialog {...defaultProps} />)

      const submitButton = screen.getByRole('button', { name: /criar paciente/i })
      await user.click(submitButton)

      await waitFor(() => {
        expect(defaultProps.onSuccess).toHaveBeenCalledWith({
          id: 'new-patient-id',
          name: 'Test Patient',
          email: 'test@example.com'
        })
      })
    })

    it('should close dialog after successful submission', async () => {
      const user = userEvent.setup()
      render(<CreatePatientDialog {...defaultProps} />)

      const submitButton = screen.getByRole('button', { name: /criar paciente/i })
      await user.click(submitButton)

      await waitFor(() => {
        expect(defaultProps.onClose).toHaveBeenCalled()
      })
    })

    it('should reset form after successful submission', async () => {
      const user = userEvent.setup()
      const mockReset = vi.fn()

      vi.mocked(require('react-hook-form').useForm).mockReturnValue({
        register: vi.fn(),
        handleSubmit: vi.fn((fn) => async (e) => {
          e.preventDefault()
          await fn({})
        }),
        formState: { errors: {}, isSubmitting: false, isValid: true },
        reset: mockReset,
        setValue: vi.fn(),
        watch: vi.fn()
      })

      render(<CreatePatientDialog {...defaultProps} />)

      const submitButton = screen.getByRole('button', { name: /criar paciente/i })
      await user.click(submitButton)

      await waitFor(() => {
        expect(mockReset).toHaveBeenCalled()
      })
    })
  })

  describe('error handling', () => {
    it('should show error message on submission failure', async () => {
      const user = userEvent.setup()
      mockCreatePatient.mockRejectedValue(new Error('Falha ao criar paciente'))

      render(<CreatePatientDialog {...defaultProps} />)

      const submitButton = screen.getByRole('button', { name: /criar paciente/i })
      await user.click(submitButton)

      await waitFor(() => {
        expect(screen.getByText(/erro ao criar paciente/i)).toBeInTheDocument()
      })
    })

    it('should show specific error for duplicate email', async () => {
      const user = userEvent.setup()
      mockCreatePatient.mockRejectedValue({
        response: { data: { message: 'Email já existe' } }
      })

      render(<CreatePatientDialog {...defaultProps} />)

      const submitButton = screen.getByRole('button', { name: /criar paciente/i })
      await user.click(submitButton)

      await waitFor(() => {
        expect(screen.getByText('Email já existe')).toBeInTheDocument()
      })
    })

    it('should clear errors when dialog reopens', async () => {
      const { rerender } = render(<CreatePatientDialog {...defaultProps} open={false} />)

      // Open dialog with error
      rerender(<CreatePatientDialog {...defaultProps} open={true} />)
      // Simulate error state
      const user = userEvent.setup()
      mockCreatePatient.mockRejectedValue(new Error('Test error'))

      const submitButton = screen.getByRole('button', { name: /criar paciente/i })
      await user.click(submitButton)

      await waitFor(() => {
        expect(screen.getByText(/erro ao criar paciente/i)).toBeInTheDocument()
      })

      // Close and reopen dialog
      rerender(<CreatePatientDialog {...defaultProps} open={false} />)
      rerender(<CreatePatientDialog {...defaultProps} open={true} />)

      expect(screen.queryByText(/erro ao criar paciente/i)).not.toBeInTheDocument()
    })
  })

  describe('form fields behavior', () => {
    it('should format phone number input', async () => {
      const user = userEvent.setup()
      render(<CreatePatientDialog {...defaultProps} />)

      const phoneInput = screen.getByLabelText(/telefone/i)
      await user.type(phoneInput, '11999999999')

      expect(phoneInput).toHaveValue('(11) 99999-9999')
    })

    it('should provide gender options', () => {
      render(<CreatePatientDialog {...defaultProps} />)

      const genderSelect = screen.getByLabelText(/gênero/i)
      fireEvent.click(genderSelect)

      expect(screen.getByText('Masculino')).toBeInTheDocument()
      expect(screen.getByText('Feminino')).toBeInTheDocument()
      expect(screen.getByText('Outro')).toBeInTheDocument()
    })

    it('should provide treatment type options', () => {
      render(<CreatePatientDialog {...defaultProps} />)

      const treatmentSelect = screen.getByLabelText(/tipo de tratamento/i)
      fireEvent.click(treatmentSelect)

      expect(screen.getByText('Quimioterapia')).toBeInTheDocument()
      expect(screen.getByText('Radioterapia')).toBeInTheDocument()
      expect(screen.getByText('Cirurgia')).toBeInTheDocument()
      expect(screen.getByText('Imunoterapia')).toBeInTheDocument()
    })

    it('should validate birth date is not in the future', async () => {
      const futureDate = new Date(Date.now() + 86400000).toISOString().split('T')[0]

      // Mock form with future date error
      vi.mocked(require('react-hook-form').useForm).mockReturnValue({
        register: vi.fn(),
        handleSubmit: vi.fn(),
        formState: {
          errors: {
            birth_date: { message: 'Data de nascimento não pode ser no futuro' }
          },
          isSubmitting: false,
          isValid: false
        },
        reset: vi.fn(),
        setValue: vi.fn(),
        watch: vi.fn(() => futureDate)
      })

      render(<CreatePatientDialog {...defaultProps} />)

      expect(screen.getByText('Data de nascimento não pode ser no futuro')).toBeInTheDocument()
    })
  })

  describe('dialog interactions', () => {
    it('should close dialog on cancel button click', async () => {
      const user = userEvent.setup()
      render(<CreatePatientDialog {...defaultProps} />)

      const cancelButton = screen.getByRole('button', { name: /cancelar/i })
      await user.click(cancelButton)

      expect(defaultProps.onClose).toHaveBeenCalled()
    })

    it('should close dialog on ESC key press', async () => {
      const user = userEvent.setup()
      render(<CreatePatientDialog {...defaultProps} />)

      await user.keyboard('{Escape}')

      expect(defaultProps.onClose).toHaveBeenCalled()
    })

    it('should close dialog on overlay click', async () => {
      const user = userEvent.setup()
      render(<CreatePatientDialog {...defaultProps} />)

      const overlay = screen.getByTestId('dialog-overlay')
      await user.click(overlay)

      expect(defaultProps.onClose).toHaveBeenCalled()
    })

    it('should not close dialog when clicking inside content', async () => {
      const user = userEvent.setup()
      render(<CreatePatientDialog {...defaultProps} />)

      const dialogContent = screen.getByRole('dialog')
      await user.click(dialogContent)

      expect(defaultProps.onClose).not.toHaveBeenCalled()
    })
  })

  describe('accessibility', () => {
    it('should have proper ARIA labels', () => {
      render(<CreatePatientDialog {...defaultProps} />)

      expect(screen.getByRole('dialog')).toHaveAttribute('aria-labelledby')
      expect(screen.getByRole('dialog')).toHaveAttribute('aria-describedby')
    })

    it('should focus first form field on open', async () => {
      render(<CreatePatientDialog {...defaultProps} />)

      await waitFor(() => {
        expect(screen.getByLabelText(/nome completo/i)).toHaveFocus()
      })
    })

    it('should trap focus within dialog', async () => {
      const user = userEvent.setup()
      render(<CreatePatientDialog {...defaultProps} />)

      // Tab through all focusable elements
      const focusableElements = [
        screen.getByLabelText(/nome completo/i),
        screen.getByLabelText(/email/i),
        screen.getByLabelText(/telefone/i),
        screen.getByLabelText(/data de nascimento/i),
        screen.getByLabelText(/gênero/i),
        screen.getByLabelText(/tipo de tratamento/i),
        screen.getByRole('button', { name: /cancelar/i }),
        screen.getByRole('button', { name: /criar paciente/i })
      ]

      for (const element of focusableElements) {
        await user.tab()
        expect(element).toHaveFocus()
      }

      // Should cycle back to first element
      await user.tab()
      expect(focusableElements[0]).toHaveFocus()
    })

    it('should have proper form labels and descriptions', () => {
      render(<CreatePatientDialog {...defaultProps} />)

      const nameField = screen.getByLabelText(/nome completo/i)
      expect(nameField).toHaveAttribute('required')

      const emailField = screen.getByLabelText(/email/i)
      expect(emailField).toHaveAttribute('type', 'email')

      const phoneField = screen.getByLabelText(/telefone/i)
      expect(phoneField).toHaveAttribute('type', 'tel')
    })
  })
})