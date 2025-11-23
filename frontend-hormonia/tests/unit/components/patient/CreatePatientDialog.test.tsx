import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { CreatePatientDialog } from '@/components/patients/CreatePatientDialog'

// Mock API client
const mockCreatePatient = vi.fn()
vi.mock('../../lib/api-client', () => ({
  apiClient: {
    patients: {
      create: mockCreatePatient,
    },
  },
}))

// Mock UI components
vi.mock('@/components/ui/dialog', () => ({
  Dialog: ({ children, open, onOpenChange }: any) =>
    open ? <div data-testid="dialog" onClick={() => onOpenChange?.(false)}>{children}</div> : null,
  DialogContent: ({ children }: any) => <div data-testid="dialog-content">{children}</div>,
  DialogDescription: ({ children }: any) => <div data-testid="dialog-description">{children}</div>,
  DialogFooter: ({ children }: any) => <div data-testid="dialog-footer">{children}</div>,
  DialogHeader: ({ children }: any) => <div data-testid="dialog-header">{children}</div>,
  DialogTitle: ({ children }: any) => <h2 data-testid="dialog-title">{children}</h2>,
}))

vi.mock('@/components/ui/button', () => ({
  Button: ({ children, onClick, disabled, type, variant }: any) => (
    <button
      data-testid={variant === 'outline' ? 'cancel-button' : 'submit-button'}
      onClick={onClick}
      disabled={disabled}
      type={type}
    >
      {children}
    </button>
  ),
}))

vi.mock('@/components/ui/input', () => ({
  Input: ({ id, placeholder, type, ...props }: any) => (
    <input
      data-testid={`input-${id}`}
      placeholder={placeholder}
      type={type}
      {...props}
    />
  ),
}))

vi.mock('@/components/ui/label', () => ({
  Label: ({ children, htmlFor }: any) => (
    <label data-testid={`label-${htmlFor}`}>{children}</label>
  ),
}))

vi.mock('@/components/ui/textarea', () => ({
  Textarea: ({ id, placeholder, ...props }: any) => (
    <textarea
      data-testid={`textarea-${id}`}
      placeholder={placeholder}
      {...props}
    />
  ),
}))

vi.mock('@/components/ui/select', () => ({
  Select: ({ children, onValueChange }: any) => (
    <div data-testid="select" onClick={() => onValueChange?.('Terapia Hormonal Feminina')}>
      {children}
    </div>
  ),
  SelectContent: ({ children }: any) => <div data-testid="select-content">{children}</div>,
  SelectItem: ({ children, value }: any) => (
    <div data-testid={`select-item-${value}`}>{children}</div>
  ),
  SelectTrigger: ({ children }: any) => <div data-testid="select-trigger">{children}</div>,
  SelectValue: ({ placeholder }: any) => <div data-testid="select-value">{placeholder}</div>,
}))

vi.mock('@/components/ui/use-toast', () => ({
  useToast: () => ({
    toast: vi.fn(),
  }),
}))

vi.mock('../ui/loading-spinner', () => ({
  LoadingSpinner: ({ size, className }: any) => (
    <div data-testid="loading-spinner" data-size={size} className={className}>
      Loading...
    </div>
  ),
}))

// Mock react-hook-form
const mockRegister = vi.fn()
const mockHandleSubmit = vi.fn()
const mockReset = vi.fn()
const mockSetValue = vi.fn()
const mockWatch = vi.fn()

vi.mock('react-hook-form', () => ({
  useForm: () => ({
    register: mockRegister,
    handleSubmit: mockHandleSubmit,
    formState: { errors: {} },
    reset: mockReset,
    setValue: mockSetValue,
    watch: mockWatch,
  }),
}))

vi.mock('@hookform/resolvers/zod', () => ({
  zodResolver: () => vi.fn(),
}))

describe('CreatePatientDialog', () => {
  const defaultProps = {
    open: true,
    onOpenChange: vi.fn(),
  }

  let queryClient: QueryClient

  beforeEach(() => {
    vi.clearAllMocks()
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    })
    mockCreatePatient.mockResolvedValue({ id: '1', name: 'Test Patient' })
    mockHandleSubmit.mockImplementation((fn) => (e) => {
      e?.preventDefault()
      fn({
        name: 'Test Patient',
        phone: '+55 11 99999-9999',
        email: 'test@example.com',
        birth_date: '1990-01-01',
        treatment_type: 'Terapia Hormonal Feminina',
        treatment_start_date: '2024-01-01',
        notes: 'Test notes',
      })
    })
  })

  const renderWithQueryClient = (component: React.ReactElement) => {
    return render(
      <QueryClientProvider client={queryClient}>
        {component}
      </QueryClientProvider>
    )
  }

  describe('Rendering', () => {
    it('should render dialog when open', () => {
      renderWithQueryClient(<CreatePatientDialog {...defaultProps} />)

      expect(screen.getByTestId('dialog')).toBeInTheDocument()
      expect(screen.getByTestId('dialog-title')).toHaveTextContent('Novo Paciente')
      expect(screen.getByTestId('dialog-description')).toHaveTextContent(
        'Adicione um novo paciente ao sistema de terapia hormonal.'
      )
    })

    it('should not render dialog when closed', () => {
      renderWithQueryClient(<CreatePatientDialog {...defaultProps} open={false} />)

      expect(screen.queryByTestId('dialog')).not.toBeInTheDocument()
    })
  })

  describe('Form Fields', () => {
    it('should render all required form fields', () => {
      renderWithQueryClient(<CreatePatientDialog {...defaultProps} />)

      // Required fields
      expect(screen.getByTestId('input-name')).toBeInTheDocument()
      expect(screen.getByTestId('input-phone')).toBeInTheDocument()
      expect(screen.getByTestId('select')).toBeInTheDocument()

      // Optional fields
      expect(screen.getByTestId('input-email')).toBeInTheDocument()
      expect(screen.getByTestId('input-birth_date')).toBeInTheDocument()
      expect(screen.getByTestId('input-treatment_start_date')).toBeInTheDocument()
      expect(screen.getByTestId('textarea-notes')).toBeInTheDocument()
    })

    it('should display correct field labels', () => {
      renderWithQueryClient(<CreatePatientDialog {...defaultProps} />)

      expect(screen.getByTestId('label-name')).toHaveTextContent('Nome completo *')
      expect(screen.getByTestId('label-phone')).toHaveTextContent('Telefone *')
      expect(screen.getByTestId('label-email')).toHaveTextContent('Email')
      expect(screen.getByTestId('label-birth_date')).toHaveTextContent('Data de nascimento')
      expect(screen.getByTestId('label-treatment_type')).toHaveTextContent('Tipo de tratamento *')
      expect(screen.getByTestId('label-treatment_start_date')).toHaveTextContent('Data de início do tratamento')
      expect(screen.getByTestId('label-notes')).toHaveTextContent('Observações')
    })

    it('should have correct input types and placeholders', () => {
      renderWithQueryClient(<CreatePatientDialog {...defaultProps} />)

      expect(screen.getByTestId('input-name')).toHaveAttribute('placeholder', 'Nome do paciente')
      expect(screen.getByTestId('input-phone')).toHaveAttribute('placeholder', '+55 11 99999-9999')
      expect(screen.getByTestId('input-email')).toHaveAttribute('type', 'email')
      expect(screen.getByTestId('input-email')).toHaveAttribute('placeholder', 'email@exemplo.com')
      expect(screen.getByTestId('input-birth_date')).toHaveAttribute('type', 'date')
      expect(screen.getByTestId('input-treatment_start_date')).toHaveAttribute('type', 'date')
      expect(screen.getByTestId('textarea-notes')).toHaveAttribute(
        'placeholder',
        'Observações sobre o paciente ou tratamento...'
      )
    })
  })

  describe('Treatment Type Selection', () => {
    it('should render treatment type options', () => {
      renderWithQueryClient(<CreatePatientDialog {...defaultProps} />)

      expect(screen.getByTestId('select-value')).toHaveTextContent('Selecione o tratamento')
      expect(screen.getByTestId('select-item-Terapia Hormonal Feminina')).toBeInTheDocument()
      expect(screen.getByTestId('select-item-Terapia Hormonal Masculina')).toBeInTheDocument()
      expect(screen.getByTestId('select-item-Reposição Hormonal')).toBeInTheDocument()
      expect(screen.getByTestId('select-item-Tratamento Personalizado')).toBeInTheDocument()
    })

    it('should handle treatment type selection', () => {
      renderWithQueryClient(<CreatePatientDialog {...defaultProps} />)

      const select = screen.getByTestId('select')
      fireEvent.click(select)

      expect(mockSetValue).toHaveBeenCalledWith('treatment_type', 'Terapia Hormonal Feminina')
    })
  })

  describe('Form Submission', () => {
    it('should call create patient API with correct data', async () => {
      const { toast } = require('@/components/ui/use-toast').useToast()
      renderWithQueryClient(<CreatePatientDialog {...defaultProps} />)

      const form = screen.getByRole('form')
      fireEvent.submit(form)

      await waitFor(() => {
        expect(mockCreatePatient).toHaveBeenCalledWith({
          name: 'Test Patient',
          phone: '+55 11 99999-9999',
          treatment_type: 'Terapia Hormonal Feminina',
          email: 'test@example.com',
          birth_date: '1990-01-01',
          treatment_start_date: '2024-01-01',
          notes: 'Test notes',
        })
      })

      expect(toast).toHaveBeenCalledWith({
        title: 'Paciente criado com sucesso',
        description: 'O novo paciente foi adicionado ao sistema.',
      })
    })

    it('should clean optional empty fields before submission', async () => {
      mockHandleSubmit.mockImplementation((fn) => (e) => {
        e?.preventDefault()
        fn({
          name: 'Test Patient',
          phone: '+55 11 99999-9999',
          email: '', // Empty email
          treatment_type: 'Terapia Hormonal Feminina',
        })
      })

      renderWithQueryClient(<CreatePatientDialog {...defaultProps} />)

      const form = screen.getByRole('form')
      fireEvent.submit(form)

      await waitFor(() => {
        expect(mockCreatePatient).toHaveBeenCalledWith({
          name: 'Test Patient',
          phone: '+55 11 99999-9999',
          treatment_type: 'Terapia Hormonal Feminina',
          // email should be excluded since it's empty
        })
      })
    })

    it('should reset form and close dialog on successful submission', async () => {
      const onOpenChange = vi.fn()
      renderWithQueryClient(
        <CreatePatientDialog {...defaultProps} onOpenChange={onOpenChange} />
      )

      const form = screen.getByRole('form')
      fireEvent.submit(form)

      await waitFor(() => {
        expect(mockReset).toHaveBeenCalled()
        expect(onOpenChange).toHaveBeenCalledWith(false)
      })
    })

    it('should show loading state during submission', async () => {
      mockCreatePatient.mockImplementation(
        () => new Promise(resolve => setTimeout(resolve, 100))
      )

      renderWithQueryClient(<CreatePatientDialog {...defaultProps} />)

      const form = screen.getByRole('form')
      fireEvent.submit(form)

      expect(screen.getByTestId('loading-spinner')).toBeInTheDocument()
      expect(screen.getByText('Criando...')).toBeInTheDocument()
      expect(screen.getByTestId('submit-button')).toBeDisabled()
      expect(screen.getByTestId('cancel-button')).toBeDisabled()

      await waitFor(() => {
        expect(mockCreatePatient).toHaveBeenCalled()
      })
    })

    it('should handle submission errors', async () => {
      const error = { data: { message: 'Patient already exists' } }
      mockCreatePatient.mockRejectedValue(error)
      const { toast } = require('@/components/ui/use-toast').useToast()

      renderWithQueryClient(<CreatePatientDialog {...defaultProps} />)

      const form = screen.getByRole('form')
      fireEvent.submit(form)

      await waitFor(() => {
        expect(toast).toHaveBeenCalledWith({
          title: 'Erro ao criar paciente',
          description: 'Patient already exists',
          variant: 'destructive'
        })
      })
    })

    it('should handle unknown errors gracefully', async () => {
      mockCreatePatient.mockRejectedValue(new Error('Unknown error'))
      const { toast } = require('@/components/ui/use-toast').useToast()

      renderWithQueryClient(<CreatePatientDialog {...defaultProps} />)

      const form = screen.getByRole('form')
      fireEvent.submit(form)

      await waitFor(() => {
        expect(toast).toHaveBeenCalledWith({
          title: 'Erro ao criar paciente',
          description: 'Ocorreu um erro inesperado.',
          variant: 'destructive'
        })
      })
    })
  })

  describe('Dialog Interactions', () => {
    it('should reset form and close dialog when cancel button is clicked', () => {
      const onOpenChange = vi.fn()
      renderWithQueryClient(
        <CreatePatientDialog {...defaultProps} onOpenChange={onOpenChange} />
      )

      fireEvent.click(screen.getByTestId('cancel-button'))

      expect(mockReset).toHaveBeenCalled()
      expect(onOpenChange).toHaveBeenCalledWith(false)
    })

    it('should reset form when dialog is closed', () => {
      const onOpenChange = vi.fn()
      renderWithQueryClient(
        <CreatePatientDialog {...defaultProps} onOpenChange={onOpenChange} />
      )

      // Simulate dialog close
      fireEvent.click(screen.getByTestId('dialog'))

      expect(mockReset).toHaveBeenCalled()
    })
  })

  describe('Form Validation', () => {
    it('should register form fields with react-hook-form', () => {
      renderWithQueryClient(<CreatePatientDialog {...defaultProps} />)

      expect(mockRegister).toHaveBeenCalledWith('name')
      expect(mockRegister).toHaveBeenCalledWith('phone')
      expect(mockRegister).toHaveBeenCalledWith('email')
      expect(mockRegister).toHaveBeenCalledWith('birth_date')
      expect(mockRegister).toHaveBeenCalledWith('treatment_start_date')
      expect(mockRegister).toHaveBeenCalledWith('notes')
    })

    it('should display validation errors when present', () => {
      const mockUseForm = require('react-hook-form').useForm
      mockUseForm.mockReturnValue({
        ...mockUseForm(),
        formState: {
          errors: {
            name: { message: 'Nome é obrigatório' },
            phone: { message: 'Telefone inválido' },
            email: { message: 'Email inválido' },
            treatment_type: { message: 'Selecione um tratamento' },
          },
        },
      })

      renderWithQueryClient(<CreatePatientDialog {...defaultProps} />)

      expect(screen.getByText('Nome é obrigatório')).toBeInTheDocument()
      expect(screen.getByText('Telefone inválido')).toBeInTheDocument()
      expect(screen.getByText('Email inválido')).toBeInTheDocument()
      expect(screen.getByText('Selecione um tratamento')).toBeInTheDocument()
    })
  })

  describe('Action Buttons', () => {
    it('should render cancel and submit buttons', () => {
      renderWithQueryClient(<CreatePatientDialog {...defaultProps} />)

      expect(screen.getByTestId('cancel-button')).toHaveTextContent('Cancelar')
      expect(screen.getByTestId('submit-button')).toHaveTextContent('Criar Paciente')
    })

    it('should have correct button types', () => {
      renderWithQueryClient(<CreatePatientDialog {...defaultProps} />)

      expect(screen.getByTestId('cancel-button')).toHaveAttribute('type', 'button')
      expect(screen.getByTestId('submit-button')).toHaveAttribute('type', 'submit')
    })

    it('should disable buttons during submission', () => {
      mockCreatePatient.mockImplementation(
        () => new Promise(resolve => setTimeout(resolve, 100))
      )

      renderWithQueryClient(<CreatePatientDialog {...defaultProps} />)

      const form = screen.getByRole('form')
      fireEvent.submit(form)

      expect(screen.getByTestId('cancel-button')).toBeDisabled()
      expect(screen.getByTestId('submit-button')).toBeDisabled()
    })
  })

  describe('Accessibility', () => {
    it('should have proper form structure', () => {
      renderWithQueryClient(<CreatePatientDialog {...defaultProps} />)

      expect(screen.getByRole('form')).toBeInTheDocument()
    })

    it('should have proper label associations', () => {
      renderWithQueryClient(<CreatePatientDialog {...defaultProps} />)

      expect(screen.getByTestId('label-name')).toBeInTheDocument()
      expect(screen.getByTestId('label-phone')).toBeInTheDocument()
      expect(screen.getByTestId('label-email')).toBeInTheDocument()
    })
  })
})