import { ApiError, api } from '@/lib/api-client'

type JsonValue = Record<string, unknown>

const createResponse = (payload: JsonValue, status = 200) => ({
  ok: status >= 200 && status < 300,
  status,
  json: async () => payload,
  headers: {
    get: () => null,
  },
})

describe('api-client boundary guards', () => {
  beforeEach(() => {
    api.clearSecurityState()
    jest.clearAllMocks()
  })

  it('rejects malformed accessQuiz payload with friendly error', async () => {
    const fetchMock = jest.fn()
    fetchMock.mockResolvedValueOnce(createResponse({ csrf_token: 'csrf-ok' }))
    fetchMock.mockResolvedValueOnce(createResponse({ success: true }))
    global.fetch = fetchMock as unknown as typeof fetch

    await expect(api.accessQuiz('token-123')).rejects.toEqual(
      expect.objectContaining<ApiError>({
        name: 'ApiError',
        message: 'Nao foi possivel carregar o questionario. Tente novamente.',
      }),
    )
  })

  it('rejects malformed recoverSession payload instead of returning unsafe data', async () => {
    const fetchMock = jest.fn()
    fetchMock.mockResolvedValueOnce(createResponse({ active: true }))
    global.fetch = fetchMock as unknown as typeof fetch

    await expect(api.recoverSession()).rejects.toEqual(
      expect.objectContaining<ApiError>({
        name: 'ApiError',
        message: 'Nao foi possivel recuperar sua sessao. Abra o link novamente.',
      }),
    )
  })

  it('keeps valid backend payload behavior for access and submit', async () => {
    const fetchMock = jest.fn()
    fetchMock.mockResolvedValueOnce(createResponse({ csrf_token: 'csrf-ok' }))
    fetchMock.mockResolvedValueOnce(
      createResponse({
        quiz_session_id: 'qs-1',
        patient_name: 'Paciente',
        template_name: 'Mensal',
        expires_at: '2099-01-01T00:00:00Z',
        questions: [
          {
            id: 'q1',
            text: 'Pergunta 1',
            type: 'single_choice',
          },
        ],
      }),
    )
    fetchMock.mockResolvedValueOnce(
      createResponse({
        success: true,
        is_last_question: false,
        next_question: {
          id: 'q2',
          text: 'Pergunta 2',
          type: 'text',
        },
        session_status: 'in_progress',
      }),
    )
    global.fetch = fetchMock as unknown as typeof fetch

    const session = await api.accessQuiz('token-123')
    expect(session.quiz_session_id).toBe('qs-1')
    expect(session.questions).toHaveLength(1)

    const submit = await api.submitAnswer('q1', 'ok')
    expect(submit.success).toBe(true)
    expect(submit.next_question?.id).toBe('q2')
  })
})
