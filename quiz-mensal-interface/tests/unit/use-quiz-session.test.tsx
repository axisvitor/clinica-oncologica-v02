import { renderHook, waitFor, act } from '@testing-library/react'
import { useQuizSession } from '@/hooks/use-quiz-session'
import { api } from '@/lib/api-client'

const mockGet = jest.fn()

jest.mock('next/navigation', () => ({
  useSearchParams: () => ({
    get: mockGet,
  }),
}))

type JsonValue = Record<string, unknown>

const createResponse = (payload: JsonValue, status = 200) => ({
  ok: status >= 200 && status < 300,
  status,
  json: async () => payload,
  headers: {
    get: () => null,
  },
})

describe('useQuizSession boundary-safe behavior', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    api.clearSecurityState()
  })

  it('shows friendly error and keeps session null on malformed access payload', async () => {
    mockGet.mockReturnValue('token-abc')

    const fetchMock = jest.fn()
    fetchMock.mockResolvedValueOnce(createResponse({ csrf_token: 'csrf-ok' }))
    fetchMock.mockResolvedValueOnce(createResponse({ success: true }))
    global.fetch = fetchMock as unknown as typeof fetch

    const { result } = renderHook(() => useQuizSession())

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })

    expect(result.current.session).toBeNull()
    expect(result.current.error).toBe('Nao foi possivel carregar o questionario. Tente novamente.')
  })

  it('keeps valid payload flow and updates session on submit', async () => {
    mockGet.mockReturnValue('token-abc')

    const fetchMock = jest.fn()
    fetchMock.mockResolvedValueOnce(createResponse({ csrf_token: 'csrf-ok' }))
    fetchMock.mockResolvedValueOnce(
      createResponse({
        quiz_session_id: 'qs-1',
        patient_name: 'Paciente',
        template_name: 'Mensal',
        expires_at: '2099-01-01T00:00:00Z',
        current_question_index: 0,
        questions: [
          { id: 'q1', text: 'Pergunta 1', type: 'single_choice' },
          { id: 'q2', text: 'Pergunta 2', type: 'text' },
        ],
      }),
    )
    fetchMock.mockResolvedValueOnce(
      createResponse({
        success: true,
        is_last_question: false,
        next_question: { id: 'q2', text: 'Pergunta 2', type: 'text' },
        session_status: 'in_progress',
      }),
    )
    global.fetch = fetchMock as unknown as typeof fetch

    const { result } = renderHook(() => useQuizSession())

    await waitFor(() => {
      expect(result.current.session?.quiz_session_id).toBe('qs-1')
    })

    await act(async () => {
      await result.current.submitAnswer('q1', 'resposta')
    })

    await waitFor(() => {
      expect(result.current.session?.current_question_index).toBe(1)
    })
  })
})
