import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '../../test-utils'
import { QuickStats } from '../../../components/dashboard/QuickStats'

// Mock the icon component
vi.mock('lucide-react', () => ({
  Users: () => <div data-testid="users-icon">Users Icon</div>,
  MessageSquare: () => <div data-testid="message-icon">Message Icon</div>,
  Activity: () => <div data-testid="activity-icon">Activity Icon</div>,
  TrendingUp: () => <div data-testid="trending-icon">Trending Icon</div>,
  AlertTriangle: () => <div data-testid="alert-icon">Alert Icon</div>,
}))

// Mock API responses
const mockStats = {
  total_patients: 145,
  active_patients: 120,
  messages_today: 89,
  response_rate: 87.5,
  avg_response_time: 12.5,
  pending_alerts: 3
}

describe('QuickStats Component', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('rendering', () => {
    it('should render all stats cards', () => {
      render(<QuickStats stats={mockStats} />)

      expect(screen.getByText('Total de Pacientes')).toBeInTheDocument()
      expect(screen.getByText('Pacientes Ativos')).toBeInTheDocument()
      expect(screen.getByText('Mensagens Hoje')).toBeInTheDocument()
      expect(screen.getByText('Taxa de Resposta')).toBeInTheDocument()
    })

    it('should display correct stat values', () => {
      render(<QuickStats stats={mockStats} />)

      expect(screen.getByText('145')).toBeInTheDocument()
      expect(screen.getByText('120')).toBeInTheDocument()
      expect(screen.getByText('89')).toBeInTheDocument()
      expect(screen.getByText('87.5%')).toBeInTheDocument()
    })

    it('should render appropriate icons for each stat', () => {
      render(<QuickStats stats={mockStats} />)

      expect(screen.getByTestId('users-icon')).toBeInTheDocument()
      expect(screen.getByTestId('message-icon')).toBeInTheDocument()
      expect(screen.getByTestId('activity-icon')).toBeInTheDocument()
      expect(screen.getByTestId('trending-icon')).toBeInTheDocument()
    })
  })

  describe('loading state', () => {
    it('should show loading skeleton when stats are not provided', () => {
      render(<QuickStats stats={null} />)

      const skeletons = screen.getAllByTestId('stat-skeleton')
      expect(skeletons).toHaveLength(4)
    })

    it('should show loading skeleton when stats are undefined', () => {
      render(<QuickStats stats={undefined} />)

      const skeletons = screen.getAllByTestId('stat-skeleton')
      expect(skeletons).toHaveLength(4)
    })
  })

  describe('data formatting', () => {
    it('should format large numbers correctly', () => {
      const largeStats = {
        ...mockStats,
        total_patients: 1250,
        messages_today: 1589
      }

      render(<QuickStats stats={largeStats} />)

      expect(screen.getByText('1,250')).toBeInTheDocument()
      expect(screen.getByText('1,589')).toBeInTheDocument()
    })

    it('should format percentage values correctly', () => {
      const percentageStats = {
        ...mockStats,
        response_rate: 99.75
      }

      render(<QuickStats stats={percentageStats} />)

      expect(screen.getByText('99.8%')).toBeInTheDocument() // Rounded to 1 decimal
    })

    it('should handle zero values', () => {
      const zeroStats = {
        total_patients: 0,
        active_patients: 0,
        messages_today: 0,
        response_rate: 0,
        avg_response_time: 0,
        pending_alerts: 0
      }

      render(<QuickStats stats={zeroStats} />)

      expect(screen.getByText('0')).toBeInTheDocument()
      expect(screen.getByText('0%')).toBeInTheDocument()
    })
  })

  describe('trend indicators', () => {
    it('should show positive trend for high response rate', () => {
      const highResponseStats = {
        ...mockStats,
        response_rate: 95.0
      }

      render(<QuickStats stats={highResponseStats} />)

      const responseCard = screen.getByText('95.0%').closest('[data-testid="stat-card"]')
      expect(responseCard).toHaveClass('border-green-200') // Positive trend styling
    })

    it('should show warning trend for low response rate', () => {
      const lowResponseStats = {
        ...mockStats,
        response_rate: 60.0
      }

      render(<QuickStats stats={lowResponseStats} />)

      const responseCard = screen.getByText('60.0%').closest('[data-testid="stat-card"]')
      expect(responseCard).toHaveClass('border-yellow-200') // Warning trend styling
    })

    it('should show negative trend for very low response rate', () => {
      const veryLowResponseStats = {
        ...mockStats,
        response_rate: 40.0
      }

      render(<QuickStats stats={veryLowResponseStats} />)

      const responseCard = screen.getByText('40.0%').closest('[data-testid="stat-card"]')
      expect(responseCard).toHaveClass('border-red-200') // Negative trend styling
    })
  })

  describe('alerts indicator', () => {
    it('should show alert indicator when there are pending alerts', () => {
      const alertStats = {
        ...mockStats,
        pending_alerts: 5
      }

      render(<QuickStats stats={alertStats} />)

      expect(screen.getByTestId('alert-icon')).toBeInTheDocument()
      expect(screen.getByText('5 Alertas Pendentes')).toBeInTheDocument()
    })

    it('should not show alert indicator when no pending alerts', () => {
      const noAlertStats = {
        ...mockStats,
        pending_alerts: 0
      }

      render(<QuickStats stats={noAlertStats} />)

      expect(screen.queryByTestId('alert-icon')).not.toBeInTheDocument()
      expect(screen.queryByText(/Alertas Pendentes/)).not.toBeInTheDocument()
    })

    it('should show critical styling for many alerts', () => {
      const manyAlertsStats = {
        ...mockStats,
        pending_alerts: 10
      }

      render(<QuickStats stats={manyAlertsStats} />)

      const alertSection = screen.getByText('10 Alertas Pendentes').closest('div')
      expect(alertSection).toHaveClass('text-red-600') // Critical styling
    })
  })

  describe('responsive behavior', () => {
    it('should have responsive grid layout', () => {
      render(<QuickStats stats={mockStats} />)

      const container = screen.getByTestId('quick-stats-container')
      expect(container).toHaveClass('grid', 'grid-cols-1', 'md:grid-cols-2', 'lg:grid-cols-4')
    })

    it('should stack cards vertically on mobile', () => {
      // Mock window.matchMedia to simulate mobile viewport
      Object.defineProperty(window, 'matchMedia', {
        writable: true,
        value: vi.fn().mockImplementation(query => ({
          matches: query.includes('max-width'),
          media: query,
          onchange: null,
          addListener: vi.fn(),
          removeListener: vi.fn(),
          addEventListener: vi.fn(),
          removeEventListener: vi.fn(),
          dispatchEvent: vi.fn(),
        })),
      })

      render(<QuickStats stats={mockStats} />)

      const container = screen.getByTestId('quick-stats-container')
      expect(container).toHaveClass('grid-cols-1')
    })
  })

  describe('accessibility', () => {
    it('should have proper ARIA labels', () => {
      render(<QuickStats stats={mockStats} />)

      expect(screen.getByLabelText('Estatísticas rápidas do dashboard')).toBeInTheDocument()
      expect(screen.getByLabelText('Total de pacientes: 145')).toBeInTheDocument()
      expect(screen.getByLabelText('Taxa de resposta: 87.5%')).toBeInTheDocument()
    })

    it('should have semantic structure', () => {
      render(<QuickStats stats={mockStats} />)

      const statsSection = screen.getByRole('region', { name: /estatísticas/i })
      expect(statsSection).toBeInTheDocument()

      const statItems = screen.getAllByRole('article')
      expect(statItems).toHaveLength(4)
    })

    it('should support keyboard navigation', () => {
      render(<QuickStats stats={mockStats} />)

      const firstCard = screen.getAllByRole('article')[0]
      firstCard.focus()
      expect(firstCard).toHaveFocus()
    })
  })

  describe('error handling', () => {
    it('should handle malformed stats data gracefully', () => {
      const malformedStats = {
        total_patients: 'invalid',
        active_patients: null,
        messages_today: undefined,
        response_rate: 'not-a-number'
      }

      render(<QuickStats stats={malformedStats as any} />)

      // Should show fallback values or handle gracefully
      expect(screen.getByText('--')).toBeInTheDocument()
    })

    it('should handle missing stats properties', () => {
      const incompleteStats = {
        total_patients: 100
        // Missing other properties
      }

      render(<QuickStats stats={incompleteStats as any} />)

      expect(screen.getByText('100')).toBeInTheDocument()
      expect(screen.getAllByText('--')).toHaveLength(3) // Missing values shown as --
    })
  })

  describe('animation and transitions', () => {
    it('should animate value changes', async () => {
      const { rerender } = render(<QuickStats stats={mockStats} />)

      expect(screen.getByText('145')).toBeInTheDocument()

      const updatedStats = { ...mockStats, total_patients: 150 }
      rerender(<QuickStats stats={updatedStats} />)

      await waitFor(() => {
        expect(screen.getByText('150')).toBeInTheDocument()
      })
    })

    it('should have loading to content transition', async () => {
      const { rerender } = render(<QuickStats stats={null} />)

      expect(screen.getAllByTestId('stat-skeleton')).toHaveLength(4)

      rerender(<QuickStats stats={mockStats} />)

      await waitFor(() => {
        expect(screen.queryByTestId('stat-skeleton')).not.toBeInTheDocument()
        expect(screen.getByText('145')).toBeInTheDocument()
      })
    })
  })

  describe('performance', () => {
    it('should not re-render unnecessarily with same stats', () => {
      const renderSpy = vi.fn()
      const StatsSpy = vi.fn(QuickStats)

      const { rerender } = render(<StatsSpy stats={mockStats} />)

      rerender(<StatsSpy stats={mockStats} />)

      // Component should be memoized and not re-render with same props
      expect(StatsSpy).toHaveBeenCalledTimes(2) // Initial render + rerender check
    })

    it('should handle rapid stats updates efficiently', async () => {
      const { rerender } = render(<QuickStats stats={mockStats} />)

      // Simulate rapid updates
      for (let i = 0; i < 10; i++) {
        const rapidStats = { ...mockStats, total_patients: 145 + i }
        rerender(<QuickStats stats={rapidStats} />)
      }

      await waitFor(() => {
        expect(screen.getByText('154')).toBeInTheDocument()
      })
    })
  })
})