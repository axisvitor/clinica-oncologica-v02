import { describe, it, expect } from 'vitest'
import { render, screen } from '../../test-utils'
import QuickStats from '../../../src/features/dashboard/QuickStats'
import type { DashboardMainData } from '../../../src/lib/api-client/dashboard'

const mockData = {
  active_patients: 120,
  patients_change: 5,
  active_patients_percentage: 82.5,
  response_rate: 87.5,
  response_rate_change: 2.1,
  alerts_pending: 3,
  alerts_change: -1,
  completed_quizzes: 10,
  quizzes_change: 4
} as DashboardMainData

describe('QuickStats Component', () => {
  it('renders stat labels and values', () => {
    render(<QuickStats data={mockData} />)

    expect(screen.getByText('Pacientes Ativos')).toBeInTheDocument()
    expect(screen.getByText('Taxa de Resposta')).toBeInTheDocument()
    expect(screen.getByText('Alertas Ativos')).toBeInTheDocument()
    expect(screen.getByText('Questionarios')).toBeInTheDocument()

    expect(screen.getByText('120')).toBeInTheDocument()
    expect(screen.getByText('87.5%')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText('10')).toBeInTheDocument()
  })

  it('shows loading skeletons when loading', () => {
    render(<QuickStats isLoading />)

    expect(screen.getAllByRole('status').length).toBeGreaterThan(0)
    expect(screen.queryByText('Pacientes Ativos')).not.toBeInTheDocument()
  })

  it('shows error state when error is provided', () => {
    render(<QuickStats error={new Error('fail')} />)

    expect(screen.getByText('Erro ao carregar metricas do dashboard')).toBeInTheDocument()
  })
})
