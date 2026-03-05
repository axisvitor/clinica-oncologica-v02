/**
 * MSW Request Handlers
 * Mock API endpoints for testing
 */
import { http, HttpResponse } from 'msw'
import type { QuizSession, QuizSubmitResponse } from '@/types/quiz'

const API_BASE_URL =
  process.env.NEXT_PUBLIC_QUIZ_PUBLIC_API_URL || 'http://localhost:8000/api/v2/quiz-extensions'

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
      allow_other: false,
    },
    {
      id: 'q2',
      order_index: 1,
      text: 'Você está tomando seus medicamentos conforme prescrito?',
      type: 'yes_no',
      required: true,
      allow_other: false,
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
        { id: 'opt4', value: 'insomnia', text: 'Insônia' },
      ],
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
        { id: 'opt7', value: 'fatigue', text: 'Fadiga' },
      ],
    },
    {
      id: 'q5',
      order_index: 4,
      text: 'Há algo mais que você gostaria de compartilhar com sua equipe médica?',
      type: 'text',
      required: false,
      allow_other: false,
    },
  ],
}

/**
 * Mock Expired Session
 */
export const mockExpiredSession: QuizSession = {
  ...mockQuizSession,
  quiz_session_id: 'session-expired',
  expires_at: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(), // 1 day ago
}

/**
 * API Request Handlers
 */
export const handlers = [
  // Access Quiz - Success
  http.post(`${API_BASE_URL}/access`, async ({ request }) => {
    const body = (await request.json()) as { token: string }

    if (body.token === 'valid-token') {
      return HttpResponse.json(mockQuizSession)
    }

    if (body.token === 'expired-token') {
      return HttpResponse.json(mockExpiredSession)
    }

    if (body.token === 'token-with-rotation') {
      return HttpResponse.json({
        ...mockQuizSession,
        new_token: 'rotated-token-123',
      })
    }

    return HttpResponse.json({ detail: 'Token inválido ou expirado' }, { status: 401 })
  }),

  // Submit Answer - Success
  http.post(`${API_BASE_URL}/submit`, async ({ request }) => {
    const body = (await request.json()) as {
      token: string
      question_id: string
      response_value: string | string[]
      other_text?: string
    }

    // Validate token
    if (!body.token || body.token === 'invalid-token') {
      return HttpResponse.json({ detail: 'Token inválido' }, { status: 401 })
    }

    const questionIndex = mockQuizSession.questions.findIndex(
      (question) => question.id === body.question_id,
    )
    const hasKnownQuestion = questionIndex >= 0
    const isLastQuestion =
      hasKnownQuestion && questionIndex === mockQuizSession.questions.length - 1

    const response: QuizSubmitResponse = {
      success: true,
      is_last_question: isLastQuestion,
      session_status: isLastQuestion ? 'completed' : 'in_progress',
      message: isLastQuestion ? 'Questionário concluído com sucesso' : 'Resposta salva com sucesso',
      next_question:
        !isLastQuestion && hasKnownQuestion
          ? mockQuizSession.questions[questionIndex + 1]
          : undefined,
    }

    if (body.question_id === 'q2') {
      response.new_token = 'rotated-token-456'
    }

    return HttpResponse.json(response)
  }),

  // Health Check
  http.get(`${API_BASE_URL}/health`, () => {
    return HttpResponse.json({ status: 'healthy' })
  }),

  // Simulate Network Error
  http.post(`${API_BASE_URL}/network-error`, () => {
    return HttpResponse.error()
  }),

  // Simulate Timeout
  http.post(`${API_BASE_URL}/timeout`, async () => {
    await new Promise((resolve) => setTimeout(resolve, 35000)) // Longer than default timeout
    return HttpResponse.json({ success: true })
  }),

  // Server Error
  http.post(`${API_BASE_URL}/server-error`, () => {
    return HttpResponse.json({ detail: 'Internal server error' }, { status: 500 })
  }),
]
