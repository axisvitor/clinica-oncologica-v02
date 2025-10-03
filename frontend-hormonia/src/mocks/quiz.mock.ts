/**
 * Mock Quiz Data
 */

export interface MockQuizTemplate {
  id: string
  title: string
  description: string
  questions: any[]
  is_active: boolean
  created_at: string
}

export interface MockQuizSession {
  id: string
  patient_id: string
  quiz_template_id: string
  status: 'pending' | 'in_progress' | 'completed' | 'expired'
  link: string
  created_at: string
  expires_at: string
  completed_at?: string
  score?: number
}

export const MOCK_QUIZ_TEMPLATES: MockQuizTemplate[] = [
  {
    id: 'quiz-template-001',
    title: 'Avaliação Mensal de Sintomas',
    description: 'Questionário para acompanhamento mensal de sintomas',
    questions: [],
    is_active: true,
    created_at: '2024-01-01T00:00:00Z'
  },
  {
    id: 'quiz-template-002',
    title: 'Qualidade de Vida - QoL',
    description: 'Avaliação de qualidade de vida durante tratamento',
    questions: [],
    is_active: true,
    created_at: '2024-01-01T00:00:00Z'
  }
]

export const MOCK_QUIZ_SESSIONS: MockQuizSession[] = [
  {
    id: 'session-001',
    patient_id: 'patient-001',
    quiz_template_id: 'quiz-template-001',
    status: 'completed',
    link: 'https://sistema.com/quiz/session-001',
    created_at: '2024-09-01T10:00:00Z',
    expires_at: '2024-09-08T10:00:00Z',
    completed_at: '2024-09-02T14:30:00Z',
    score: 85
  },
  {
    id: 'session-002',
    patient_id: 'patient-002',
    quiz_template_id: 'quiz-template-001',
    status: 'completed',
    link: 'https://sistema.com/quiz/session-002',
    created_at: '2024-09-01T10:00:00Z',
    expires_at: '2024-09-08T10:00:00Z',
    completed_at: '2024-09-03T09:15:00Z',
    score: 92
  },
  {
    id: 'session-003',
    patient_id: 'patient-003',
    quiz_template_id: 'quiz-template-001',
    status: 'pending',
    link: 'https://sistema.com/quiz/session-003',
    created_at: '2024-10-01T10:00:00Z',
    expires_at: '2024-10-08T10:00:00Z'
  }
]

/**
 * Get mock quiz templates
 */
export function getMockQuizTemplates(): {
  items: MockQuizTemplate[]
  total: number
  page: number
  size: number
} {
  const templates = MOCK_QUIZ_TEMPLATES.filter(t => t.is_active)
  return {
    items: templates,
    total: templates.length,
    page: 1,
    size: templates.length
  }
}

/**
 * Get mock quiz sessions
 */
export function getMockQuizSessions(params?: {
  patient_id?: string
  status?: string
}): { items: MockQuizSession[]; total: number; page: number; size: number } {
  let filtered = [...MOCK_QUIZ_SESSIONS]

  if (params?.patient_id) {
    filtered = filtered.filter(s => s.patient_id === params.patient_id)
  }

  if (params?.status) {
    filtered = filtered.filter(s => s.status === params.status)
  }

  return {
    items: filtered,
    total: filtered.length,
    page: 1,
    size: filtered.length
  }
}

/**
 * Get mock quiz stats for monthly quiz dashboard
 */
export function getMockMonthlyQuizStats(): {
  total_sent: number
  total_completed: number
  total_expired: number
  total_active: number
  average_score: number
  completion_rate: number
  expiration_rate: number
} {
  const totalSent = MOCK_QUIZ_SESSIONS.length
  const completed = MOCK_QUIZ_SESSIONS.filter(s => s.status === 'completed').length
  const expired = MOCK_QUIZ_SESSIONS.filter(s => s.status === 'expired').length
  const active = MOCK_QUIZ_SESSIONS.filter(s => s.status === 'pending' || s.status === 'in_progress').length

  const completedSessions = MOCK_QUIZ_SESSIONS.filter(s => s.score !== undefined)
  const avgScore = completedSessions.reduce((sum, s) => sum + (s.score || 0), 0) / completedSessions.length || 0

  return {
    total_sent: totalSent,
    total_completed: completed,
    total_expired: expired,
    total_active: active,
    average_score: Math.round(avgScore * 10) / 10,
    completion_rate: Math.round((completed / totalSent) * 100 * 10) / 10,
    expiration_rate: Math.round((expired / totalSent) * 100 * 10) / 10
  }
}
