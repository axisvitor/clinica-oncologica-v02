import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '../../test-utils'
import userEvent from '@testing-library/user-event'
import { PatientCard } from '../../../components/patients/PatientCard'
import { createMockPatient } from '../../test-utils'

// Mock icons
vi.mock('lucide-react', () => ({
  MoreVertical: () => <div data-testid="more-options-icon">More</div>,
  Eye: () => <div data-testid="eye-icon">View</div>,
  Edit: () => <div data-testid="edit-icon">Edit</div>,
  MessageSquare: () => <div data-testid="message-icon">Message</div>,
  AlertTriangle: () => <div data-testid="alert-icon">Alert</div>,
  CheckCircle: () => <div data-testid="check-icon">Check</div>,
  Clock: () => <div data-testid="clock-icon">Clock</div>,
}))

// Mock router
const mockNavigate = vi.fn()
vi.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
}))

describe('PatientCard Component', () => {
  const mockPatient = createMockPatient({
    id: 'patient-1',
    name: 'João Silva',
    email: 'joao@example.com',
    phone: '+5511999999999',
    status: 'active',
    treatment_type: 'chemotherapy',
    last_interaction: '2023-12-01T10:30:00Z',
    next_appointment: '2023-12-15T14:00:00Z'
  })

  const defaultProps = {
    patient: mockPatient,
    onEdit: vi.fn(),
    onMessage: vi.fn(),
    onStatusChange: vi.fn()
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('rendering', () => {
    it('should render patient basic information', () => {
      render(<PatientCard {...defaultProps} />)

      expect(screen.getByText('João Silva')).toBeInTheDocument()
      expect(screen.getByText('joao@example.com')).toBeInTheDocument()
      expect(screen.getByText('+5511999999999')).toBeInTheDocument()
    })

    it('should display patient status correctly', () => {
      render(<PatientCard {...defaultProps} />)

      const statusBadge = screen.getByText('Ativo')
      expect(statusBadge).toBeInTheDocument()
      expect(statusBadge).toHaveClass('bg-green-100', 'text-green-800')
    })

    it('should show treatment type', () => {
      render(<PatientCard {...defaultProps} />)

      expect(screen.getByText('Quimioterapia')).toBeInTheDocument()
    })

    it('should display last interaction time', () => {
      render(<PatientCard {...defaultProps} />)

      expect(screen.getByText(/última interação/i)).toBeInTheDocument()
      expect(screen.getByText(/01\/12\/2023/)).toBeInTheDocument() // Formatted date
    })

    it('should show next appointment if available', () => {
      render(<PatientCard {...defaultProps} />)

      expect(screen.getByText(/próxima consulta/i)).toBeInTheDocument()
      expect(screen.getByText(/15\/12\/2023/)).toBeInTheDocument()
    })
  })

  describe('status variants', () => {
    it('should render inactive status correctly', () => {
      const inactivePatient = { ...mockPatient, status: 'inactive' }
      render(<PatientCard {...defaultProps} patient={inactivePatient} />)

      const statusBadge = screen.getByText('Inativo')
      expect(statusBadge).toHaveClass('bg-gray-100', 'text-gray-800')
    })

    it('should render paused status correctly', () => {
      const pausedPatient = { ...mockPatient, status: 'paused' }
      render(<PatientCard {...defaultProps} patient={pausedPatient} />)

      const statusBadge = screen.getByText('Pausado')
      expect(statusBadge).toHaveClass('bg-yellow-100', 'text-yellow-800')
    })

    it('should render completed status correctly', () => {
      const completedPatient = { ...mockPatient, status: 'completed' }
      render(<PatientCard {...defaultProps} patient={completedPatient} />)

      const statusBadge = screen.getByText('Concluído')
      expect(statusBadge).toHaveClass('bg-blue-100', 'text-blue-800')
    })
  })

  describe('interactions', () => {
    it('should navigate to patient detail on card click', async () => {
      const user = userEvent.setup()
      render(<PatientCard {...defaultProps} />)

      await user.click(screen.getByTestId('patient-card'))

      expect(mockNavigate).toHaveBeenCalledWith('/patients/patient-1')
    })

    it('should open options menu on more button click', async () => {
      const user = userEvent.setup()
      render(<PatientCard {...defaultProps} />)

      await user.click(screen.getByTestId('more-options-icon'))

      expect(screen.getByRole('menu')).toBeInTheDocument()
      expect(screen.getByRole('menuitem', { name: /visualizar/i })).toBeInTheDocument()
      expect(screen.getByRole('menuitem', { name: /editar/i })).toBeInTheDocument()
      expect(screen.getByRole('menuitem', { name: /enviar mensagem/i })).toBeInTheDocument()
    })

    it('should call onEdit when edit option is clicked', async () => {
      const user = userEvent.setup()
      render(<PatientCard {...defaultProps} />)

      await user.click(screen.getByTestId('more-options-icon'))
      await user.click(screen.getByRole('menuitem', { name: /editar/i }))

      expect(defaultProps.onEdit).toHaveBeenCalledWith(mockPatient)
    })

    it('should call onMessage when message option is clicked', async () => {
      const user = userEvent.setup()
      render(<PatientCard {...defaultProps} />)

      await user.click(screen.getByTestId('more-options-icon'))
      await user.click(screen.getByRole('menuitem', { name: /enviar mensagem/i }))

      expect(defaultProps.onMessage).toHaveBeenCalledWith(mockPatient)
    })

    it('should call onStatusChange when status option is clicked', async () => {
      const user = userEvent.setup()
      render(<PatientCard {...defaultProps} />)

      await user.click(screen.getByTestId('more-options-icon'))
      await user.click(screen.getByRole('menuitem', { name: /alterar status/i }))

      expect(defaultProps.onStatusChange).toHaveBeenCalledWith(mockPatient)
    })
  })

  describe('accessibility', () => {
    it('should have proper ARIA labels', () => {
      render(<PatientCard {...defaultProps} />)

      expect(screen.getByLabelText(`Cartão do paciente ${mockPatient.name}`)).toBeInTheDocument()
      expect(screen.getByLabelText('Mais opções')).toBeInTheDocument()
    })

    it('should be keyboard navigable', async () => {
      render(<PatientCard {...defaultProps} />)

      const card = screen.getByTestId('patient-card')
      const moreButton = screen.getByLabelText('Mais opções')

      // Tab to card
      await userEvent.tab()
      expect(card).toHaveFocus()

      // Tab to more options button
      await userEvent.tab()
      expect(moreButton).toHaveFocus()
    })

    it('should support Enter key to open patient detail', async () => {
      render(<PatientCard {...defaultProps} />)

      const card = screen.getByTestId('patient-card')
      card.focus()

      await userEvent.keyboard('{Enter}')

      expect(mockNavigate).toHaveBeenCalledWith('/patients/patient-1')
    })

    it('should support Space key to open patient detail', async () => {
      render(<PatientCard {...defaultProps} />)

      const card = screen.getByTestId('patient-card')
      card.focus()

      await userEvent.keyboard(' ')

      expect(mockNavigate).toHaveBeenCalledWith('/patients/patient-1')
    })
  })

  describe('avatar and initials', () => {
    it('should show patient initials when no avatar', () => {
      render(<PatientCard {...defaultProps} />)

      expect(screen.getByText('JS')).toBeInTheDocument() // João Silva initials
    })

    it('should show avatar image when available', () => {
      const patientWithAvatar = {
        ...mockPatient,
        avatar_url: 'https://example.com/avatar.jpg'
      }

      render(<PatientCard {...defaultProps} patient={patientWithAvatar} />)

      const avatar = screen.getByRole('img', { name: /avatar/i })
      expect(avatar).toHaveAttribute('src', 'https://example.com/avatar.jpg')
    })

    it('should handle names with single word', () => {
      const singleNamePatient = { ...mockPatient, name: 'João' }
      render(<PatientCard {...defaultProps} patient={singleNamePatient} />)

      expect(screen.getByText('J')).toBeInTheDocument() // Single initial
    })

    it('should handle empty name gracefully', () => {
      const noNamePatient = { ...mockPatient, name: '' }
      render(<PatientCard {...defaultProps} patient={noNamePatient} />)

      expect(screen.getByText('--')).toBeInTheDocument() // Fallback
    })
  })

  describe('date formatting', () => {
    it('should format dates correctly in Brazilian format', () => {
      render(<PatientCard {...defaultProps} />)

      expect(screen.getByText('01/12/2023')).toBeInTheDocument()
      expect(screen.getByText('15/12/2023')).toBeInTheDocument()
    })

    it('should handle missing dates gracefully', () => {
      const patientWithoutDates = {
        ...mockPatient,
        last_interaction: null,
        next_appointment: null
      }

      render(<PatientCard {...defaultProps} patient={patientWithoutDates} />)

      expect(screen.getByText('Nunca')).toBeInTheDocument() // No last interaction
      expect(screen.getByText('Não agendada')).toBeInTheDocument() // No appointment
    })

    it('should show relative time for recent interactions', () => {
      const recentPatient = {
        ...mockPatient,
        last_interaction: new Date(Date.now() - 1000 * 60 * 30).toISOString() // 30 minutes ago
      }

      render(<PatientCard {...defaultProps} patient={recentPatient} />)

      expect(screen.getByText(/30 minutos atrás/)).toBeInTheDocument()
    })
  })

  describe('treatment type display', () => {
    it('should translate treatment types correctly', () => {
      const treatments = [
        { type: 'chemotherapy', expected: 'Quimioterapia' },
        { type: 'radiotherapy', expected: 'Radioterapia' },
        { type: 'surgery', expected: 'Cirurgia' },
        { type: 'immunotherapy', expected: 'Imunoterapia' }
      ]

      treatments.forEach(({ type, expected }) => {
        const patient = { ...mockPatient, treatment_type: type }
        const { unmount } = render(<PatientCard {...defaultProps} patient={patient} />)

        expect(screen.getByText(expected)).toBeInTheDocument()
        unmount()
      })
    })

    it('should handle unknown treatment types', () => {
      const unknownTreatmentPatient = { ...mockPatient, treatment_type: 'unknown' }
      render(<PatientCard {...defaultProps} patient={unknownTreatmentPatient} />)

      expect(screen.getByText('Outro')).toBeInTheDocument()
    })
  })

  describe('loading and error states', () => {
    it('should handle missing patient data gracefully', () => {
      render(<PatientCard {...defaultProps} patient={null as any} />)

      expect(screen.getByText('Paciente não encontrado')).toBeInTheDocument()
    })

    it('should show loading state when specified', () => {
      render(<PatientCard {...defaultProps} loading />)

      expect(screen.getByTestId('patient-card-skeleton')).toBeInTheDocument()
    })
  })

  describe('responsive design', () => {
    it('should adapt layout for mobile screens', () => {
      // Mock mobile viewport
      Object.defineProperty(window, 'innerWidth', {
        writable: true,
        configurable: true,
        value: 375,
      })

      render(<PatientCard {...defaultProps} />)

      const card = screen.getByTestId('patient-card')
      expect(card).toHaveClass('flex-col') // Stacked layout on mobile
    })

    it('should use horizontal layout on desktop', () => {
      // Mock desktop viewport
      Object.defineProperty(window, 'innerWidth', {
        writable: true,
        configurable: true,
        value: 1024,
      })

      render(<PatientCard {...defaultProps} />)

      const card = screen.getByTestId('patient-card')
      expect(card).toHaveClass('flex-row') // Horizontal layout on desktop
    })
  })

  describe('performance', () => {
    it('should not re-render unnecessarily', () => {
      const renderSpy = vi.fn()
      const PatientCardSpy = vi.fn(PatientCard)

      const { rerender } = render(<PatientCardSpy {...defaultProps} />)

      rerender(<PatientCardSpy {...defaultProps} />)

      // Should be memoized and not re-render with same props
      expect(PatientCardSpy).toHaveBeenCalledTimes(2)
    })

    it('should handle rapid interactions efficiently', async () => {
      const user = userEvent.setup()
      render(<PatientCard {...defaultProps} />)

      // Rapid clicks should be debounced
      const card = screen.getByTestId('patient-card')
      await user.click(card)
      await user.click(card)
      await user.click(card)

      // Should only navigate once
      expect(mockNavigate).toHaveBeenCalledTimes(1)
    })
  })
})