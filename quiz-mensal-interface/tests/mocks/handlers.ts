/**
 * MSW Request Handlers
 * Mock API endpoints for testing
 */
import { rest } from 'msw'
import type { QuizSession, QuizSubmitResponse } from '@/types/quiz'

const API_BASE_URL = process.env.NEXT_PUBLIC_QUIZ_PUBLIC_API_URL ||
                     'http://localhost:8000/api/v2/monthly-quiz-public'

/**
 * Mock Quiz Session Data
 */
export const mockQuizSession: QuizSession = {
  quiz_session_id: 'session-123',
  patient_id: 'patient-456',
  patient_name: 'João Silva',
  template_id: 'template-789',
  template_name: 'Questionário Mensal Oncologia',
  status: 'in_progress',
  current_question_index: 0,
  total_questions: 5,
  expires_at: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(), // 7 days from now
  questions: [
    {
      id: 'q1',
      order_index: 0,
      text: 'Como você avaliaria seu bem-estar geral esta semana?',
      type: 'scale',
      min_value: 0,
      max_value: 10,
      required: true,
      allow_other: false
    },
    {
      id: 'q2',
      order_index: 1,
      text: 'Você está tomando seus medicamentos conforme prescrito?',
      type: 'yes_no',
      required: true,
      allow_other: false
    },
    {
      id: 'q3',
      order_index: 2,
      text: 'Quais sintomas você está experienciando? (Selecione todos que se aplicam)',
      type: 'multiple_choice',
      required: true,
      allow_other: true,
      options: [
        { id: 'opt1', value: 'fatigue', text: 'Fadiga' },
        { id: 'opt2', value: 'nausea', text: 'Náusea' },
        { id: 'opt3', value: 'pain', text: 'Dor' },
        { id: 'opt4', value: 'insomnia', text: 'Insônia' }
      ]
    },
    {
      id: 'q4',
      order_index: 3,
      text: 'Qual é o principal efeito colateral que você está sentindo?',
      type: 'single_choice',
      required: true,
      allow_other: true,
      options: [
        { id: 'opt5', value: 'headache', text: 'Dor de cabeça' },
        { id: 'opt6', value: 'nausea', text: 'Náusea' },
        { id: 'opt7', value: 'fatigue', text: 'Fadiga' }
      ]
    },
    {
      id: 'q5',
      order_index: 4,
      text: 'Há algo mais que você gostaria de compartilhar com sua equipe médica?',
      type: 'text',
      required: false,
      allow_other: false
    }
  ]
}

/**
 * Mock Expired Session
 */
export const mockExpiredSession: QuizSession = {
  ...mockQuizSession,
  quiz_session_id: 'session-expired',
  expires_at: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString() // 1 day ago
}

/**
 * API Request Handlers
 */
export const handlers = [
  // Access Quiz - Success
  rest.post(`${API_BASE_URL}/access`, (req, res, ctx) => {
    const body = req.body as { token: string }

    if (body.token === 'valid-token') {
      return res(ctx.json(mockQuizSession))
    }

    if (body.token === 'expired-token') {
      return res(ctx.json(mockExpiredSession))
    }

    if (body.token === 'token-with-rotation') {
      return res(ctx.json({
        ...mockQuizSession,
        new_token: 'rotated-token-123'
      }))
    }

    return res(
      ctx.status(401),
      ctx.json({ detail: 'Token inválido ou expirado' })
    )
  }),

  // Submit Answer - Success
  rest.post(`${API_BASE_URL}/submit`, (req, res, ctx) => {
    const body = req.body as {
      token: string
      question_id: string
      response_value: string | string[]
      other_text?: string
    }

    // Validate token
    if (!body.token || body.token === 'invalid-token') {
      return res(
        ctx.status(401),
        ctx.json({ detail: 'Token inválido' })
      )
    }

    // Simulate token rotation on second answer
    const response: QuizSubmitResponse = {
      success: true,
      message: 'Resposta salva com sucesso',
      next_question_index: 1
    }

    if (body.question_id === 'q2') {
      response.new_token = 'rotated-token-456'
    }

    return res(ctx.json(response))
  }),

  // Health Check
  rest.get(`${API_BASE_URL}/health`, (req, res, ctx) => {
    return res(ctx.json({ status: 'healthy' }))
  }),

  // Simulate Network Error
  rest.post(`${API_BASE_URL}/network-error`, (req, res, ctx) => {
    return res.networkError('Failed to connect')
  }),

  // Simulate Timeout
  rest.post(`${API_BASE_URL}/timeout`, async (req, res, ctx) => {
    await new Promise(resolve => setTimeout(resolve, 35000)) // Longer than default timeout
    return res(ctx.json({ success: true }))
  }),

  // Server Error
  rest.post(`${API_BASE_URL}/server-error`, (req, res, ctx) => {
    return res(
      ctx.status(500),
      ctx.json({ detail: 'Internal server error' })
    )
  })
]
