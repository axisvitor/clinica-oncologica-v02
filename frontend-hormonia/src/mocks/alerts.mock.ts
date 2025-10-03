/**
 * Mock Alerts Data
 */

export interface MockAlert {
  id: string
  patient_id?: string
  type: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  title: string
  message: string
  created_at: string
  acknowledged_at?: string
  resolved_at?: string
  metadata?: Record<string, any>
}

export const MOCK_ALERTS: MockAlert[] = [
  {
    id: 'alert-001',
    patient_id: 'patient-002',
    type: 'no_response',
    severity: 'medium',
    title: 'Paciente sem resposta há 3 dias',
    message: 'Roberto Silva Santos não responde mensagens há 3 dias',
    created_at: '2024-10-01T10:00:00Z'
  },
  {
    id: 'alert-002',
    patient_id: 'patient-004',
    type: 'missed_appointment',
    severity: 'high',
    title: 'Consulta perdida',
    message: 'Carlos Eduardo Lima faltou à consulta agendada',
    created_at: '2024-09-30T14:00:00Z'
  },
  {
    id: 'alert-003',
    type: 'system',
    severity: 'low',
    title: 'Atualização de sistema disponível',
    message: 'Nova versão do sistema disponível para atualização',
    created_at: '2024-09-29T08:00:00Z',
    acknowledged_at: '2024-09-29T09:00:00Z'
  },
  {
    id: 'alert-004',
    patient_id: 'patient-003',
    type: 'medication',
    severity: 'critical',
    title: 'Medicação atrasada',
    message: 'Maria Helena Ferreira não tomou medicação prescrita',
    created_at: '2024-10-02T07:00:00Z'
  }
]

/**
 * Get mock alerts with pagination
 */
export function getMockAlerts(params?: {
  page?: number
  size?: number
  severity?: string
  acknowledged?: boolean
}): { items: MockAlert[]; total: number; page: number; size: number; pages: number } {
  let filtered = [...MOCK_ALERTS]

  if (params?.severity) {
    filtered = filtered.filter(a => a.severity === params.severity)
  }

  if (params?.acknowledged !== undefined) {
    if (params.acknowledged) {
      filtered = filtered.filter(a => a.acknowledged_at !== undefined)
    } else {
      filtered = filtered.filter(a => a.acknowledged_at === undefined)
    }
  }

  // Sort by created_at descending
  filtered.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())

  const page = params?.page || 1
  const size = params?.size || 10
  const total = filtered.length
  const pages = Math.ceil(total / size)
  const start = (page - 1) * size
  const end = start + size

  return {
    items: filtered.slice(start, end),
    total,
    page,
    size,
    pages
  }
}
