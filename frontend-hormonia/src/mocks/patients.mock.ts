/**
 * Mock Patients Data
 */

export interface MockPatient {
  id: string
  name: string
  email: string
  phone: string
  birth_date: string
  diagnosis: string
  treatment_type: string
  status: 'active' | 'inactive' | 'completed'
  registration_date: string
  last_contact?: string
  flow_status?: string
  medico_id?: string
  notes?: string
}

export const MOCK_PATIENTS: MockPatient[] = [
  {
    id: 'patient-001',
    name: 'Ana Paula Costa',
    email: 'ana.costa@email.com',
    phone: '+5548991234567',
    birth_date: '1975-03-15',
    diagnosis: 'Câncer de Mama - Estágio II',
    treatment_type: 'Quimioterapia',
    status: 'active',
    registration_date: '2024-01-10T10:00:00Z',
    last_contact: '2024-10-01T14:30:00Z',
    flow_status: 'active',
    medico_id: 'medico-001',
    notes: 'Paciente respondendo bem ao tratamento'
  },
  {
    id: 'patient-002',
    name: 'Roberto Silva Santos',
    email: 'roberto.santos@email.com',
    phone: '+5548992345678',
    birth_date: '1968-07-22',
    diagnosis: 'Câncer de Próstata - Estágio III',
    treatment_type: 'Radioterapia',
    status: 'active',
    registration_date: '2024-01-15T09:00:00Z',
    last_contact: '2024-09-30T16:00:00Z',
    flow_status: 'active',
    medico_id: 'medico-001',
    notes: 'Acompanhamento semanal necessário'
  },
  {
    id: 'patient-003',
    name: 'Maria Helena Ferreira',
    email: 'maria.ferreira@email.com',
    phone: '+5548993456789',
    birth_date: '1982-11-05',
    diagnosis: 'Câncer de Ovário - Estágio I',
    treatment_type: 'Cirurgia + Quimioterapia',
    status: 'active',
    registration_date: '2024-02-01T11:00:00Z',
    last_contact: '2024-10-02T10:15:00Z',
    flow_status: 'paused',
    medico_id: 'medico-001',
    notes: 'Cirurgia realizada com sucesso, iniciando quimio'
  },
  {
    id: 'patient-004',
    name: 'Carlos Eduardo Lima',
    email: 'carlos.lima@email.com',
    phone: '+5548994567890',
    birth_date: '1955-04-18',
    diagnosis: 'Câncer de Pulmão - Estágio IV',
    treatment_type: 'Imunoterapia',
    status: 'active',
    registration_date: '2024-02-10T14:00:00Z',
    last_contact: '2024-09-28T13:45:00Z',
    flow_status: 'active',
    medico_id: 'medico-002',
    notes: 'Tratamento paliativo em andamento'
  },
  {
    id: 'patient-005',
    name: 'Juliana Oliveira Souza',
    email: 'juliana.souza@email.com',
    phone: '+5548995678901',
    birth_date: '1990-09-12',
    diagnosis: 'Linfoma de Hodgkin - Estágio II',
    treatment_type: 'Quimioterapia',
    status: 'active',
    registration_date: '2024-02-20T08:30:00Z',
    last_contact: '2024-10-01T09:00:00Z',
    flow_status: 'active',
    medico_id: 'medico-002',
    notes: 'Ótima resposta ao tratamento'
  },
  {
    id: 'patient-006',
    name: 'Pedro Henrique Alves',
    email: 'pedro.alves@email.com',
    phone: '+5548996789012',
    birth_date: '1972-06-28',
    diagnosis: 'Câncer Colorretal - Estágio III',
    treatment_type: 'Cirurgia + Radioterapia',
    status: 'active',
    registration_date: '2024-03-01T10:00:00Z',
    last_contact: '2024-09-29T15:20:00Z',
    flow_status: 'completed',
    medico_id: 'medico-003',
    notes: 'Pós-operatório sem complicações'
  },
  {
    id: 'patient-007',
    name: 'Fernanda Costa Ribeiro',
    email: 'fernanda.ribeiro@email.com',
    phone: '+5548997890123',
    birth_date: '1985-12-03',
    diagnosis: 'Câncer de Tireoide - Estágio I',
    treatment_type: 'Cirurgia',
    status: 'completed',
    registration_date: '2023-11-10T09:00:00Z',
    last_contact: '2024-09-15T11:00:00Z',
    flow_status: 'completed',
    notes: 'Tratamento concluído com sucesso'
  },
  {
    id: 'patient-008',
    name: 'João Carlos Martins',
    email: 'joao.martins@email.com',
    phone: '+5548998901234',
    birth_date: '1960-08-20',
    diagnosis: 'Câncer de Bexiga - Estágio II',
    treatment_type: 'Quimioterapia',
    status: 'active',
    registration_date: '2024-03-15T13:00:00Z',
    last_contact: '2024-09-27T14:00:00Z',
    flow_status: 'active',
    notes: 'Em acompanhamento regular'
  }
]

/**
 * Get mock patients with pagination
 */
export function getMockPatients(params?: {
  page?: number
  size?: number
  search?: string
  status?: string
  treatment_type?: string
  medico_id?: string
}): { items: MockPatient[]; total: number; page: number; size: number; pages: number } {
  let filtered = [...MOCK_PATIENTS]

  // Filter by search
  if (params?.search) {
    const searchLower = params.search.toLowerCase()
    filtered = filtered.filter(
      p =>
        p.name.toLowerCase().includes(searchLower) ||
        p.email.toLowerCase().includes(searchLower) ||
        p.diagnosis.toLowerCase().includes(searchLower)
    )
  }

  // Filter by status
  if (params?.status) {
    filtered = filtered.filter(p => p.status === params.status)
  }

  // Filter by treatment type
  if (params?.treatment_type) {
    filtered = filtered.filter(p => p.treatment_type === params.treatment_type)
  }

  // Filter by medico
  if (params?.medico_id) {
    filtered = filtered.filter(p => p.medico_id === params.medico_id)
  }

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

/**
 * Get mock patient by ID
 */
export function getMockPatientById(id: string): MockPatient | null {
  return MOCK_PATIENTS.find(p => p.id === id) || null
}

/**
 * Get mock patients by medico ID
 */
export function getMockPatientsByMedico(medicoId: string): MockPatient[] {
  return MOCK_PATIENTS.filter(p => p.medico_id === medicoId)
}
