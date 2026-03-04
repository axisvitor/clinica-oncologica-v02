import { render, screen } from '@testing-library/react'
import { PatientsTable } from '../PatientsTable'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { expect, test, describe, vi } from 'vitest'
import { Patient } from '@/types/api'

// Mock AutoSizer since it doesn't work well in JSDOM (zero dimensions)
vi.mock('react-virtualized-auto-sizer', () => ({
  default: ({ children }: any) => children({ height: 800, width: 1000 }),
}))

// Mock useResendQuizLink and useMonthlyQuizStatus
vi.mock('@/hooks/useMonthlyQuizStatus', () => ({
  useResendQuizLink: () => ({ isPending: false }),
  useMonthlyQuizStatus: () => ({ data: { status: 'sent' }, isLoading: false }),
}))

const queryClient = new QueryClient()

describe('PatientsTable Performance', () => {
  const generatePatients = (count: number): Patient[] => {
    return Array.from({ length: count }, (_, i) => ({
      id: `id-${i}`,
      name: `Patient ${i}`,
      email: `patient${i}@example.com`,
      phone: `+551199999${i.toString().padStart(4, '0')}`,
      status: 'active',
      treatment_type: 'Terapia Hormonal',
      current_day: i,
      last_contact: new Date().toISOString(),
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    })) as unknown as Patient[]
  }

  test('renders 1000 patients efficiently using virtualization', () => {
    const largePatientList = generatePatients(1000)
    const onPageChange = vi.fn()

    const startTime = performance.now()

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <PatientsTable
            patients={largePatientList}
            currentPage={1}
            totalPages={50}
            onPageChange={onPageChange}
          />
        </MemoryRouter>
      </QueryClientProvider>
    )

    const endTime = performance.now()
    const renderTime = endTime - startTime

    // Virtualized list should render almost instantly regardless of total item count
    // Threshold of 300ms is generous for JSDOM
    expect(renderTime).toBeLessThan(300)

    // Verify that not all 1000 items are in the DOM
    // For a 800px height and 80px itemSize, we expect around 10-15 rows
    const _rows = screen.queryAllByRole('row')
    // Note: PatientRow might not have role='row', checking by name
    const patientNames = screen.queryAllByText(/Patient \d+/)

    // Should be significantly less than 1000
    expect(patientNames.length).toBeLessThan(50)
    expect(patientNames.length).toBeGreaterThan(5)
  })
})
