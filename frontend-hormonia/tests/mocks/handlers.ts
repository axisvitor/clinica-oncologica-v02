import { http, HttpResponse } from 'msw'

// Mock data
const mockPatients = [
  {
    id: 'patient-1',
    name: 'João Silva',
    email: 'joao@example.com',
    phone: '+5511999999999',
    birth_date: '1990-01-01',
    gender: 'male',
    treatment_type: 'chemotherapy',
    status: 'active',
    created_at: '2023-01-01T00:00:00Z',
    updated_at: '2023-01-01T00:00:00Z',
    last_interaction: '2023-12-01T10:30:00Z',
    next_appointment: '2023-12-15T14:00:00Z'
  },
  {
    id: 'patient-2',
    name: 'Maria Santos',
    email: 'maria@example.com',
    phone: '+5521987654321',
    birth_date: '1985-05-15',
    gender: 'female',
    treatment_type: 'radiotherapy',
    status: 'active',
    created_at: '2023-01-02T00:00:00Z',
    updated_at: '2023-01-02T00:00:00Z',
    last_interaction: '2023-11-30T15:45:00Z',
    next_appointment: '2023-12-20T09:00:00Z'
  }
]

const mockMessages = [
  {
    id: 'message-1',
    patient_id: 'patient-1',
    content: 'Como você está se sentindo hoje?',
    type: 'text',
    direction: 'outbound',
    status: 'delivered',
    sent_at: '2023-12-01T10:00:00Z',
    delivered_at: '2023-12-01T10:01:00Z'
  },
  {
    id: 'message-2',
    patient_id: 'patient-1',
    content: 'Estou me sentindo bem, obrigado!',
    type: 'text',
    direction: 'inbound',
    status: 'received',
    sent_at: '2023-12-01T10:30:00Z',
    received_at: '2023-12-01T10:30:00Z'
  }
]

const mockQuizzes = [
  {
    id: 'quiz-1',
    title: 'Avaliação de Bem-estar',
    description: 'Questionário sobre seu estado atual',
    questions: [
      {
        id: 'q1',
        text: 'Como você se sente hoje?',
        type: 'scale',
        options: ['1', '2', '3', '4', '5'],
        required: true
      },
      {
        id: 'q2',
        text: 'Teve algum efeito colateral?',
        type: 'boolean',
        required: true
      }
    ],
    created_at: '2023-01-01T00:00:00Z'
  }
]

const mockReports = [
  {
    id: 'report-1',
    patient_id: 'patient-1',
    type: 'progress',
    title: 'Relatório de Progresso - João Silva',
    status: 'completed',
    generated_at: '2023-12-01T00:00:00Z',
    data: {
      summary: 'Paciente mostra boa evolução no tratamento',
      metrics: {
        response_rate: 85,
        engagement_score: 90
      }
    }
  }
]

const mockAnalyticsOverview = {
  total_patients: 145,
  total_quizzes: 420,
  completed_quizzes: 360,
  completion_rate: 85.7,
  active_patients_30d: 118,
  period: {
    start_date: null,
    end_date: null
  }
}

const mockAnalyticsQuizStatus = {
  distribution: {
    started: 40,
    completed: 360,
    cancelled: 20
  },
  total: 420,
  filters: {}
}

const mockAnalyticsTrend = {
  trend: [
    { year: 2024, month: 11, total: 70, completed: 58, completion_rate: 82.86 },
    { year: 2024, month: 12, total: 80, completed: 65, completion_rate: 81.25 },
    { year: 2025, month: 1, total: 90, completed: 78, completion_rate: 86.67 }
  ],
  period: { months: 6 }
}

const mockAnalyticsEngagement = {
  engagement_levels: {
    no_quizzes: 12,
    low_engagement: 82,
    high_engagement: 51
  },
  average_quizzes_per_patient: 3.4,
  total_active_patients: 145
}

const mockTreatmentDistribution = {
  period: '30d',
  total_patients: 145,
  distribution: [
    { treatment_type: 'Quimioterapia', count: 54, percentage: 37.24, color: '#2563eb' },
    { treatment_type: 'Radioterapia', count: 42, percentage: 28.97, color: '#10b981' },
    { treatment_type: 'Imunoterapia', count: 31, percentage: 21.38, color: '#f59e0b' },
    { treatment_type: 'Acompanhamento', count: 18, percentage: 12.41, color: '#ef4444' }
  ],
  trend_data: [
    { week: '2024-12-02', count: 120 },
    { week: '2024-12-09', count: 130 },
    { week: '2024-12-16', count: 140 },
    { week: '2024-12-23', count: 145 }
  ],
  last_updated: new Date().toISOString()
}

// API handlers
export const handlers = [
  // Auth endpoints
  http.get('/api/v2/auth/me', () => {
    return HttpResponse.json({
      id: 'user-1',
      email: 'admin@clinica.com',
      name: 'Admin User',
      role: 'admin',
      permissions: ['read:patients', 'write:patients', 'read:reports', 'write:reports']
    })
  }),

  http.post('/api/v2/auth/logout', () => {
    return HttpResponse.json({ message: 'Logged out successfully' })
  }),

  // Patients endpoints
  http.get('/api/v2/patients', ({ request }) => {
    const url = new URL(request.url)
    const search = url.searchParams.get('search')
    const status = url.searchParams.get('status')
    const page = parseInt(url.searchParams.get('page') || '1')
    const size = parseInt(url.searchParams.get('size') || '10')

    let filteredPatients = [...mockPatients]

    // Apply filters
    if (search) {
      filteredPatients = filteredPatients.filter(patient =>
        patient.name.toLowerCase().includes(search.toLowerCase()) ||
        patient.email.toLowerCase().includes(search.toLowerCase())
      )
    }

    if (status) {
      filteredPatients = filteredPatients.filter(patient =>
        patient.status === status
      )
    }

    // Pagination
    const startIndex = (page - 1) * size
    const endIndex = startIndex + size
    const paginatedPatients = filteredPatients.slice(startIndex, endIndex)

    return HttpResponse.json({
      items: paginatedPatients,
      total: filteredPatients.length,
      page,
      size,
      pages: Math.ceil(filteredPatients.length / size)
    })
  }),

  http.get('/api/v2/patients/:id', ({ params }) => {
    const patient = mockPatients.find(p => p.id === params.id)

    if (!patient) {
      return HttpResponse.json(
        { message: 'Patient not found' },
        { status: 404 }
      )
    }

    return HttpResponse.json(patient)
  }),

  http.post('/api/v2/patients', async ({ request }) => {
    const body = await request.json() as any

    // Validate required fields
    if (!body.name || !body.email) {
      return HttpResponse.json(
        { message: 'Name and email are required' },
        { status: 400 }
      )
    }

    // Check for duplicate email
    if (mockPatients.some(p => p.email === body.email)) {
      return HttpResponse.json(
        { message: 'Email already exists' },
        { status: 409 }
      )
    }

    const newPatient = {
      id: `patient-${Date.now()}`,
      ...body,
      status: 'active',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    }

    mockPatients.push(newPatient)

    return HttpResponse.json(newPatient, { status: 201 })
  }),

  http.patch('/api/v2/patients/:id', async ({ params, request }) => {
    const body = await request.json() as any
    const patientIndex = mockPatients.findIndex(p => p.id === params.id)

    if (patientIndex === -1) {
      return HttpResponse.json(
        { message: 'Patient not found' },
        { status: 404 }
      )
    }

    mockPatients[patientIndex] = {
      ...mockPatients[patientIndex],
      ...body,
      updated_at: new Date().toISOString()
    }

    return HttpResponse.json(mockPatients[patientIndex])
  }),

  http.delete('/api/v2/patients/:id', ({ params }) => {
    const patientIndex = mockPatients.findIndex(p => p.id === params.id)

    if (patientIndex === -1) {
      return HttpResponse.json(
        { message: 'Patient not found' },
        { status: 404 }
      )
    }

    mockPatients.splice(patientIndex, 1)

    return HttpResponse.json({ message: 'Patient deleted successfully' })
  }),

  http.get('/api/v2/patients/:id/timeline', ({ params }) => {
    return HttpResponse.json([
      {
        id: 'event-1',
        type: 'message_sent',
        title: 'Mensagem enviada',
        description: 'Como você está se sentindo hoje?',
        timestamp: '2023-12-01T10:00:00Z'
      },
      {
        id: 'event-2',
        type: 'message_received',
        title: 'Resposta recebida',
        description: 'Estou me sentindo bem!',
        timestamp: '2023-12-01T10:30:00Z'
      }
    ])
  }),

  // Messages endpoints
  http.get('/api/v2/messages', ({ request }) => {
    const url = new URL(request.url)
    const patientId = url.searchParams.get('patient_id')
    const page = parseInt(url.searchParams.get('page') || '1')
    const size = parseInt(url.searchParams.get('size') || '10')

    let filteredMessages = [...mockMessages]

    if (patientId) {
      filteredMessages = filteredMessages.filter(msg =>
        msg.patient_id === patientId
      )
    }

    const startIndex = (page - 1) * size
    const endIndex = startIndex + size
    const paginatedMessages = filteredMessages.slice(startIndex, endIndex)

    return HttpResponse.json({
      items: paginatedMessages,
      total: filteredMessages.length,
      page,
      size,
      pages: Math.ceil(filteredMessages.length / size)
    })
  }),

  http.post('/api/v2/messages/send', async ({ request }) => {
    const body = await request.json() as any

    const newMessage = {
      id: `message-${Date.now()}`,
      ...body,
      direction: 'outbound',
      status: 'sent',
      sent_at: new Date().toISOString()
    }

    mockMessages.push(newMessage)

    // Simulate delivery after delay
    setTimeout(() => {
      newMessage.status = 'delivered'
      newMessage.delivered_at = new Date().toISOString()
    }, 1000)

    return HttpResponse.json(newMessage)
  }),

  // Quiz endpoints
  http.get('/api/v2/quiz/templates', () => {
    return HttpResponse.json({ templates: mockQuizzes })
  }),

  http.post('/api/v2/quiz/sessions', async ({ request }) => {
    const body = await request.json() as any

    const session = {
      id: `session-${Date.now()}`,
      patient_id: body.patient_id,
      template_id: body.template_id,
      status: 'active',
      created_at: new Date().toISOString(),
      responses: []
    }

    return HttpResponse.json(session)
  }),

  http.post('/api/v2/quiz/sessions/:id/submit', async ({ params, request }) => {
    const body = await request.json() as any

    return HttpResponse.json({
      message: 'Responses submitted successfully',
      session_id: params.id,
      score: 85
    })
  }),

  // Reports endpoints
  http.get('/api/v2/reports', () => {
    return HttpResponse.json({
      items: mockReports,
      total: mockReports.length,
      page: 1,
      size: 10,
      pages: 1
    })
  }),

  http.post('/api/v2/reports/generate', async ({ request }) => {
    const body = await request.json() as any

    const report = {
      id: `report-${Date.now()}`,
      patient_id: body.patient_id,
      type: body.type,
      title: `Relatório ${body.type} - ${new Date().toLocaleDateString()}`,
      status: 'generating',
      created_at: new Date().toISOString()
    }

    // Simulate report generation
    setTimeout(() => {
      report.status = 'completed'
    }, 2000)

    return HttpResponse.json(report)
  }),

  // Analytics endpoints (v2)
  http.get('/api/v2/analytics/overview', () => {
    return HttpResponse.json(mockAnalyticsOverview)
  }),

  http.get('/api/v2/analytics/quiz-status', () => {
    return HttpResponse.json(mockAnalyticsQuizStatus)
  }),

  http.get('/api/v2/analytics/completion-trend', () => {
    return HttpResponse.json(mockAnalyticsTrend)
  }),

  http.get('/api/v2/analytics/patient-engagement', () => {
    return HttpResponse.json(mockAnalyticsEngagement)
  }),

  http.get('/api/v2/analytics/treatment-distribution', ({ request }) => {
    const url = new URL(request.url)
    const period = (url.searchParams.get('period') as '7d' | '30d' | '90d' | 'all') ?? '30d'
    return HttpResponse.json({
      ...mockTreatmentDistribution,
      period
    })
  }),

  http.get('/api/v2/analytics/risk-assessment', () => {
    return HttpResponse.json({
      success: true,
      risk_level_filter: 'all',
      total_patients: 2,
      generated_at: new Date().toISOString(),
      lookback_days: 7,
      risk_assessments: [
        {
          id: 'patient-1',
          patient_id: 'patient-1',
          name: 'João Silva',
          risk_level: 'high',
          risk_factors: ['Sem resposta há 7 dias'],
          last_response: new Date(Date.now() - 7 * 86400000).toISOString(),
          recommended_actions: ['Entrar em contato', 'Revisar tratamento']
        },
        {
          id: 'patient-2',
          patient_id: 'patient-2',
          name: 'Maria Santos',
          risk_level: 'medium',
          risk_factors: ['Baixo engajamento'],
          last_response: new Date(Date.now() - 3 * 86400000).toISOString(),
          recommended_actions: []
        }
      ]
    })
  }),

  // Flow endpoints
  http.get('/api/v2/flows', () => {
    return HttpResponse.json({
      items: [
        {
          id: 'flow-1',
          patient_id: 'patient-1',
          type: 'onboarding',
          status: 'active',
          current_step: 2,
          total_steps: 5
        }
      ],
      total: 1,
      page: 1,
      size: 10,
      pages: 1
    })
  }),

  http.post('/api/v2/flows/start', async ({ request }) => {
    const body = await request.json() as any

    return HttpResponse.json({
      id: `flow-${Date.now()}`,
      patient_id: body.patient_id,
      type: body.flow_type,
      status: 'active',
      current_step: 1,
      total_steps: 5,
      started_at: new Date().toISOString()
    })
  }),

  // Error simulation endpoints
  http.get('/api/v2/error/500', () => {
    return HttpResponse.json(
      { message: 'Internal server error' },
      { status: 500 }
    )
  }),

  http.get('/api/v2/error/timeout', () => {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve(HttpResponse.json({ message: 'Timeout' }))
      }, 10000) // 10 second delay to simulate timeout
    })
  }),

  // Fallback handler for unmatched requests
  http.all('*', ({ request }) => {
    console.warn('Unhandled request:', request.method, request.url)
    return HttpResponse.json(
      { message: 'Endpoint not found' },
      { status: 404 }
    )
  })
]
