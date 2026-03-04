/**
 * Mock Messages Data
 */

export interface MockMessage {
  id: string
  patient_id: string
  content: string
  type: 'sent' | 'received' | 'scheduled'
  status: 'pending' | 'sent' | 'delivered' | 'failed'
  created_at: string
  scheduled_for?: string
  delivered_at?: string
  read_at?: string
}

export const MOCK_MESSAGES: MockMessage[] = [
  {
    id: 'msg-001',
    patient_id: 'patient-001',
    content: 'Olá Ana! Lembramos que sua consulta está marcada para amanhã às 10h.',
    type: 'sent',
    status: 'delivered',
    created_at: '2024-09-30T10:00:00-03:00',
    delivered_at: '2024-09-30T10:00:15-03:00',
  },
  {
    id: 'msg-002',
    patient_id: 'patient-001',
    content: 'Obrigada pelo lembrete! Estarei lá.',
    type: 'received',
    status: 'delivered',
    created_at: '2024-09-30T10:05:00-03:00',
    delivered_at: '2024-09-30T10:05:05-03:00',
    read_at: '2024-09-30T10:06:00-03:00',
  },
  {
    id: 'msg-003',
    patient_id: 'patient-002',
    content: 'Sr. Roberto, como você está se sentindo hoje?',
    type: 'sent',
    status: 'delivered',
    created_at: '2024-09-29T14:00:00-03:00',
    delivered_at: '2024-09-29T14:00:10-03:00',
  },
  {
    id: 'msg-004',
    patient_id: 'patient-002',
    content: 'Estou bem, obrigado. Sem sintomas adversos.',
    type: 'received',
    status: 'delivered',
    created_at: '2024-09-29T14:30:00-03:00',
    delivered_at: '2024-09-29T14:30:05-03:00',
    read_at: '2024-09-29T15:00:00-03:00',
  },
  {
    id: 'msg-005',
    patient_id: 'patient-003',
    content: 'Maria, não esqueça de tomar a medicação prescrita 3x ao dia.',
    type: 'sent',
    status: 'delivered',
    created_at: '2024-10-01T08:00:00-03:00',
    delivered_at: '2024-10-01T08:00:12-03:00',
  },
  {
    id: 'msg-006',
    patient_id: 'patient-004',
    content: 'Sr. Carlos, seus exames ficaram prontos. Agende uma consulta para revisão.',
    type: 'sent',
    status: 'delivered',
    created_at: '2024-09-28T11:00:00-03:00',
    delivered_at: '2024-09-28T11:00:08-03:00',
  },
  {
    id: 'msg-007',
    patient_id: 'patient-005',
    content: 'Juliana, parabéns pelo progresso! Continue assim.',
    type: 'sent',
    status: 'delivered',
    created_at: '2024-10-01T09:00:00-03:00',
    delivered_at: '2024-10-01T09:00:15-03:00',
  },
  {
    id: 'msg-008',
    patient_id: 'patient-005',
    content: 'Muito obrigada! Estou me sentindo muito melhor.',
    type: 'received',
    status: 'delivered',
    created_at: '2024-10-01T09:15:00-03:00',
    delivered_at: '2024-10-01T09:15:05-03:00',
    read_at: '2024-10-01T09:20:00-03:00',
  },
]

/**
 * Get mock messages with pagination
 */
export function getMockMessages(params?: { patient_id?: string; page?: number; size?: number }): {
  items: MockMessage[]
  total: number
  page: number
  size: number
  pages: number
} {
  let filtered = [...MOCK_MESSAGES]

  // Filter by patient
  if (params?.patient_id) {
    filtered = filtered.filter((m) => m.patient_id === params.patient_id)
  }

  // Sort by created_at descending
  filtered.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())

  const page = params?.page || 1
  const size = params?.size || 20
  const total = filtered.length
  const pages = Math.ceil(total / size)
  const start = (page - 1) * size
  const end = start + size

  return {
    items: filtered.slice(start, end),
    total,
    page,
    size,
    pages,
  }
}

/**
 * Get mock messages for patient
 */
export function getMockMessagesByPatient(patientId: string): MockMessage[] {
  return MOCK_MESSAGES.filter((m) => m.patient_id === patientId).sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  )
}
