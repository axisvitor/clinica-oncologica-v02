/**
 * Mock Flows Data
 */

export interface MockFlow {
  id: string
  patient_id: string
  flow_type: string
  status: 'active' | 'paused' | 'completed' | 'cancelled'
  current_day: number
  total_days: number
  started_at: string
  completed_at?: string
  last_activity?: string
}

export interface MockFlowTemplate {
  id: string
  name: string
  description: string
  type: string
  duration_days: number
  is_active: boolean
  created_at: string
}

export const MOCK_FLOWS: MockFlow[] = [
  {
    id: 'flow-001',
    patient_id: 'patient-001',
    flow_type: 'quimioterapia',
    status: 'active',
    current_day: 15,
    total_days: 90,
    started_at: '2024-09-15T10:00:00-03:00',
    last_activity: '2024-10-01T14:30:00-03:00'
  },
  {
    id: 'flow-002',
    patient_id: 'patient-002',
    flow_type: 'radioterapia',
    status: 'active',
    current_day: 20,
    total_days: 60,
    started_at: '2024-09-10T09:00:00-03:00',
    last_activity: '2024-09-30T16:00:00-03:00'
  },
  {
    id: 'flow-003',
    patient_id: 'patient-003',
    flow_type: 'pos_cirurgia',
    status: 'paused',
    current_day: 10,
    total_days: 45,
    started_at: '2024-09-20T11:00:00-03:00',
    last_activity: '2024-09-28T10:15:00-03:00'
  },
  {
    id: 'flow-004',
    patient_id: 'patient-004',
    flow_type: 'imunoterapia',
    status: 'active',
    current_day: 30,
    total_days: 120,
    started_at: '2024-08-25T14:00:00-03:00',
    last_activity: '2024-09-28T13:45:00-03:00'
  },
  {
    id: 'flow-005',
    patient_id: 'patient-005',
    flow_type: 'quimioterapia',
    status: 'active',
    current_day: 25,
    total_days: 90,
    started_at: '2024-09-05T08:30:00-03:00',
    last_activity: '2024-10-01T09:00:00-03:00'
  },
  {
    id: 'flow-006',
    patient_id: 'patient-006',
    flow_type: 'radioterapia',
    status: 'completed',
    current_day: 60,
    total_days: 60,
    started_at: '2024-07-01T10:00:00-03:00',
    completed_at: '2024-08-30T15:20:00-03:00',
    last_activity: '2024-08-30T15:20:00-03:00'
  }
]

export const MOCK_FLOW_TEMPLATES: MockFlowTemplate[] = [
  {
    id: 'template-001',
    name: 'Quimioterapia Padrão',
    description: 'Flow de acompanhamento durante ciclos de quimioterapia',
    type: 'quimioterapia',
    duration_days: 90,
    is_active: true,
    created_at: '2024-01-01T00:00:00-03:00'
  },
  {
    id: 'template-002',
    name: 'Radioterapia Diária',
    description: 'Acompanhamento diário durante sessões de radioterapia',
    type: 'radioterapia',
    duration_days: 60,
    is_active: true,
    created_at: '2024-01-01T00:00:00-03:00'
  },
  {
    id: 'template-003',
    name: 'Pós-Cirúrgico',
    description: 'Recuperação e acompanhamento pós-cirúrgico',
    type: 'pos_cirurgia',
    duration_days: 45,
    is_active: true,
    created_at: '2024-01-01T00:00:00-03:00'
  },
  {
    id: 'template-004',
    name: 'Imunoterapia Mensal',
    description: 'Acompanhamento durante tratamento de imunoterapia',
    type: 'imunoterapia',
    duration_days: 120,
    is_active: true,
    created_at: '2024-01-01T00:00:00-03:00'
  }
]

/**
 * Get mock flows
 */
export function getMockFlows(params?: {
  patient_id?: string
  status?: string
}): MockFlow[] {
  let filtered = [...MOCK_FLOWS]

  if (params?.patient_id) {
    filtered = filtered.filter(f => f.patient_id === params.patient_id)
  }

  if (params?.status) {
    filtered = filtered.filter(f => f.status === params.status)
  }

  return filtered
}

/**
 * Get mock flow by ID
 */
export function getMockFlowById(id: string): MockFlow | null {
  return MOCK_FLOWS.find(f => f.id === id) || null
}

/**
 * Get mock flow templates
 */
export function getMockFlowTemplates(): MockFlowTemplate[] {
  return MOCK_FLOW_TEMPLATES.filter(t => t.is_active)
}
