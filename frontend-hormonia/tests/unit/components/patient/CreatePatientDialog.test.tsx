import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { CreatePatientDialog } from '@/features/patients/dialogs/CreatePatientDialog'
import { useAuth } from '@/app/providers/AuthContext'
import { usePatientForm } from '@/features/patients/dialogs/hooks/usePatientForm'

const hoisted = vi.hoisted(() => ({
  mockToast: vi.fn(),
  mockAdminUsersList: vi.fn(),
  mockUsePatientForm: vi.fn(),
  latestPatientFormProps: null as Record<string, unknown> | null,
}))

vi.mock('@/components/ui/dialog', () => ({
  Dialog: ({ children, open, onOpenChange }: any) => (
    open ? (
      <div data-testid="dialog-root">
        <button data-testid="dialog-close" onClick={() => onOpenChange(false)}>Close</button>
        {children}
      </div>
    ) : null
  ),
  DialogContent: ({ children }: any) => <div data-testid="dialog-content">{children}</div>,
  DialogDescription: ({ children }: any) => <div>{children}</div>,
  DialogHeader: ({ children }: any) => <div>{children}</div>,
  DialogTitle: ({ children }: any) => <h2>{children}</h2>,
}))

vi.mock('@/components/ui/use-toast', () => ({
  useToast: () => ({ toast: hoisted.mockToast }),
}))

vi.mock('@/app/providers/AuthContext', () => ({
  useAuth: vi.fn(),
}))

vi.mock('@/lib/api-client', () => ({
  apiClient: {
    adminUsers: {
      list: hoisted.mockAdminUsersList,
    },
  },
}))

vi.mock('@/features/patients/dialogs/hooks/usePatientForm', () => ({
  usePatientForm: hoisted.mockUsePatientForm,
}))

vi.mock('@/features/patients/dialogs/components/PatientForm', () => ({
  PatientForm: (props: any) => {
    hoisted.latestPatientFormProps = props

    return (
      <div data-testid="patient-form">
        <button
          data-testid="patient-submit"
          onClick={() => props.onSubmit({
            name: 'Paciente Teste',
            phone: '+55 11 99999-9999',
            treatment_type: 'Terapia Hormonal Feminina',
            timezone: 'America/Sao_Paulo',
          })}
        >
          Submit
        </button>
        <button data-testid="patient-cancel" onClick={props.onCancel}>Cancel</button>
      </div>
    )
  },
}))

const mockedUseAuth = vi.mocked(useAuth)
const mockedUsePatientForm = vi.mocked(usePatientForm)

function renderWithQueryClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      {ui}
    </QueryClientProvider>
  )
}

describe('CreatePatientDialog (canonical)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    hoisted.latestPatientFormProps = null

    hoisted.mockAdminUsersList.mockResolvedValue([])
    mockedUseAuth.mockReturnValue({
      user: {
        id: 'doctor-1',
        role: 'doctor',
        full_name: 'Dr. Teste',
        email: 'doctor@example.com',
      },
    } as ReturnType<typeof useAuth>)

    mockedUsePatientForm.mockReturnValue({
      form: {},
      onSubmit: vi.fn(),
      isPending: false,
      reset: vi.fn(),
      resetIdempotencyKey: vi.fn(),
    })
  })

  it('renders dialog and uses current doctor id for non-admin user', () => {
    renderWithQueryClient(
      <CreatePatientDialog open={true} onOpenChange={vi.fn()} />
    )

    expect(screen.getByText('Novo Paciente')).toBeInTheDocument()
    expect(mockedUsePatientForm).toHaveBeenCalledWith(
      expect.objectContaining({
        mode: 'create',
        doctorId: 'doctor-1',
      })
    )
    expect(hoisted.mockAdminUsersList).not.toHaveBeenCalled()
  })

  it('loads doctor options for admin users and forwards them to PatientForm', async () => {
    mockedUseAuth.mockReturnValue({
      user: {
        id: 'admin-1',
        role: 'admin',
        full_name: 'Admin One',
        email: 'admin@example.com',
      },
    } as ReturnType<typeof useAuth>)

    hoisted.mockAdminUsersList.mockResolvedValue([
      { id: 'doctor-9', full_name: 'Dr. Silva', email: 'silva@example.com' },
    ])

    renderWithQueryClient(
      <CreatePatientDialog open={true} onOpenChange={vi.fn()} />
    )

    await waitFor(() => {
      expect(hoisted.mockAdminUsersList).toHaveBeenCalled()
      expect(hoisted.latestPatientFormProps).not.toBeNull()
      expect((hoisted.latestPatientFormProps as any).isAdmin).toBe(true)
      expect((hoisted.latestPatientFormProps as any).doctorOptions).toEqual(
        expect.arrayContaining([
          expect.objectContaining({ id: 'admin-1' }),
          expect.objectContaining({ id: 'doctor-9', label: 'Dr. Silva' }),
        ])
      )
    })
  })

  it('prevents admin submission without selected doctor and shows destructive toast', async () => {
    const user = userEvent.setup()
    const formOnSubmit = vi.fn()

    mockedUseAuth.mockReturnValue({
      user: {
        id: '',
        role: 'admin',
        full_name: 'Admin Sem ID',
        email: 'admin@example.com',
      },
    } as ReturnType<typeof useAuth>)

    hoisted.mockAdminUsersList.mockResolvedValue([])
    mockedUsePatientForm.mockReturnValue({
      form: {},
      onSubmit: formOnSubmit,
      isPending: false,
      reset: vi.fn(),
      resetIdempotencyKey: vi.fn(),
    })

    renderWithQueryClient(
      <CreatePatientDialog open={true} onOpenChange={vi.fn()} />
    )

    await user.click(screen.getByTestId('patient-submit'))

    expect(formOnSubmit).not.toHaveBeenCalled()
    expect(hoisted.mockToast).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Selecione o médico responsável',
        variant: 'destructive',
      })
    )
  })

  it('resets idempotency key and closes dialog when onOpenChange is triggered', async () => {
    const user = userEvent.setup()
    const onOpenChange = vi.fn()
    const resetIdempotencyKey = vi.fn()

    mockedUsePatientForm.mockReturnValue({
      form: {},
      onSubmit: vi.fn(),
      isPending: false,
      reset: vi.fn(),
      resetIdempotencyKey,
    })

    renderWithQueryClient(
      <CreatePatientDialog open={true} onOpenChange={onOpenChange} />
    )

    await user.click(screen.getByTestId('dialog-close'))

    expect(resetIdempotencyKey).toHaveBeenCalled()
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it('resets idempotency key and closes dialog when PatientForm cancel is clicked', async () => {
    const user = userEvent.setup()
    const onOpenChange = vi.fn()
    const resetIdempotencyKey = vi.fn()

    mockedUsePatientForm.mockReturnValue({
      form: {},
      onSubmit: vi.fn(),
      isPending: false,
      reset: vi.fn(),
      resetIdempotencyKey,
    })

    renderWithQueryClient(
      <CreatePatientDialog open={true} onOpenChange={onOpenChange} />
    )

    await user.click(screen.getByTestId('patient-cancel'))

    expect(resetIdempotencyKey).toHaveBeenCalled()
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })
})
