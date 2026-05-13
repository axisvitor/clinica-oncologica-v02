import React from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import '@testing-library/jest-dom'
import QuizInterface from '@/components/quiz-interface'
import { api } from '@/lib/api-client'
import type { QuizSession } from '@/types/quiz'

jest.mock('@/lib/api-client', () => ({
  api: {
    submitAnswer: jest.fn(),
  },
}))

const submitAnswerMock = api.submitAnswer as jest.Mock

const SESSION_ID = 'session-sensitive-abc-123'
const PATIENT_NAME = 'Paciente Ana PHI Silva'
const TEMPLATE_NAME = 'Template Oncologia Mensal Reservado'
const TOKEN_VALUE = 'link-token-secret-phi-123'
const COOKIE_STATE = 'quiz_session_state=signed-cookie-state-phi-456'
const QUESTION_TEXT = 'Você teve dor, febre ou náuseas desde a última consulta?'
const FOLLOWUP_QUESTION_TEXT = 'Descreva sintomas em texto livre para sua equipe clínica'
const OTHER_TEXT = 'Dor neuropática intensa com detalhe privado'
const ANSWER_TEXT = 'Texto livre com diagnóstico reservado e medicação privada'

const sensitiveFixtures = [
  SESSION_ID,
  PATIENT_NAME,
  TEMPLATE_NAME,
  TOKEN_VALUE,
  COOKIE_STATE,
  QUESTION_TEXT,
  FOLLOWUP_QUESTION_TEXT,
  OTHER_TEXT,
  ANSWER_TEXT,
  'diagnóstico reservado',
  'medicação privada',
]

function makeSession(overrides: Partial<QuizSession> = {}): QuizSession {
  return {
    quiz_session_id: SESSION_ID,
    patient_id: 'patient-private-id',
    template_id: 'template-private-id',
    patient_name: PATIENT_NAME,
    template_name: TEMPLATE_NAME,
    current_question_index: 0,
    questions: [
      {
        id: 'q-sensitive-other',
        text: QUESTION_TEXT,
        type: 'single_choice',
        options: ['Sem sintomas relevantes'],
        allow_other: true,
        required: true,
      },
      {
        id: 'q-sensitive-text',
        text: FOLLOWUP_QUESTION_TEXT,
        type: 'text',
        required: false,
      },
    ],
    expires_at: new Date(Date.now() + 3600000).toISOString(),
    ...overrides,
  }
}

function storageSnapshot(storageName: 'localStorage' | 'sessionStorage'): string {
  try {
    const storage = window[storageName]
    const entries: string[] = []

    for (let index = 0; index < storage.length; index += 1) {
      const key = storage.key(index)
      if (key) {
        entries.push(`${key}\n${storage.getItem(key) ?? ''}`)
      }
    }

    return entries.join('\n')
  } catch {
    return ''
  }
}

function expectWebStorageNotToContainSensitiveFixtures(): void {
  const snapshot = `${storageSnapshot('localStorage')}\n${storageSnapshot('sessionStorage')}`

  sensitiveFixtures.forEach((fixture) => {
    expect(snapshot).not.toContain(fixture)
  })
}

describe('quiz PHI web-storage protection', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    localStorage.clear()
    sessionStorage.clear()
  })

  it('does not persist session, patient, template, question, answer, token, cookie, or free-text data after answer submission', async () => {
    const user = userEvent.setup()
    localStorage.setItem(
      `quiz-progress-v1-${SESSION_ID}`,
      JSON.stringify({
        sessionId: SESSION_ID,
        patientName: PATIENT_NAME,
        templateName: TEMPLATE_NAME,
        questionText: QUESTION_TEXT,
        answers: { 'q-sensitive-other': OTHER_TEXT },
        otherTexts: { 'q-sensitive-other': OTHER_TEXT },
        token: TOKEN_VALUE,
        cookieState: COOKIE_STATE,
      }),
    )

    submitAnswerMock.mockResolvedValueOnce({
      success: true,
      is_last_question: false,
      session_status: 'in_progress',
    })

    render(<QuizInterface session={makeSession()} token={TOKEN_VALUE} />)

    await waitFor(() => {
      expect(localStorage.getItem(`quiz-progress-v1-${SESSION_ID}`)).toBeNull()
    })

    await user.click(screen.getByRole('radio', { name: 'Outra' }))
    await waitFor(() => {
      expect(screen.getByRole('radio', { name: 'Outra' })).toHaveAttribute('aria-checked', 'true')
    })
    await user.type(screen.getByPlaceholderText(/resposta personalizada/i), OTHER_TEXT)
    await user.click(screen.getByTestId('next-question'))

    await waitFor(() => {
      expect(submitAnswerMock).toHaveBeenCalledWith(
        'q-sensitive-other',
        'other',
        expect.objectContaining({ other_text: OTHER_TEXT }),
      )
    })
    await waitFor(() => {
      expect(screen.getByText(FOLLOWUP_QUESTION_TEXT)).toBeInTheDocument()
    })

    // Old autosave wrote after 500ms once an answer entered the in-memory answer map.
    await new Promise((resolve) => setTimeout(resolve, 650))

    expect(storageSnapshot('localStorage')).not.toContain('quiz-progress')
    expectWebStorageNotToContainSensitiveFixtures()
  })

  it('does not persist text answers or PHI when submit fails', async () => {
    const user = userEvent.setup()
    const failingSession = makeSession({
      questions: [
        {
          id: 'q-sensitive-text',
          text: FOLLOWUP_QUESTION_TEXT,
          type: 'text',
          required: false,
        },
      ],
    })

    localStorage.setItem(`quiz-progress-v1-${SESSION_ID}`, JSON.stringify({ answer: ANSWER_TEXT }))
    submitAnswerMock.mockRejectedValueOnce(new Error('network unavailable'))

    render(<QuizInterface session={failingSession} token={TOKEN_VALUE} />)

    await user.type(screen.getByPlaceholderText(/Digite sua resposta/i), ANSWER_TEXT)
    await user.click(screen.getByTestId('submit-quiz'))

    await waitFor(() => {
      expect(submitAnswerMock).toHaveBeenCalledWith(
        'q-sensitive-text',
        ANSWER_TEXT,
        expect.objectContaining({ other_text: undefined }),
      )
    })

    await new Promise((resolve) => setTimeout(resolve, 650))

    expect(storageSnapshot('localStorage')).not.toContain('quiz-progress')
    expectWebStorageNotToContainSensitiveFixtures()
  })

  it('renders and submits when browser storage is unavailable', async () => {
    const user = userEvent.setup()
    const localStorageDescriptor = Object.getOwnPropertyDescriptor(window, 'localStorage')
    const sessionStorageDescriptor = Object.getOwnPropertyDescriptor(window, 'sessionStorage')
    const storageBlockedSession = makeSession({
      questions: [
        {
          id: 'q-sensitive-text',
          text: FOLLOWUP_QUESTION_TEXT,
          type: 'text',
          required: false,
        },
      ],
    })

    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      get() {
        throw new Error('localStorage unavailable')
      },
    })
    Object.defineProperty(window, 'sessionStorage', {
      configurable: true,
      get() {
        throw new Error('sessionStorage unavailable')
      },
    })

    submitAnswerMock.mockResolvedValueOnce({
      success: true,
      is_last_question: true,
      session_status: 'completed',
    })

    try {
      render(<QuizInterface session={storageBlockedSession} token={TOKEN_VALUE} />)

      expect(screen.getByText(new RegExp(PATIENT_NAME))).toBeInTheDocument()

      await user.type(screen.getByPlaceholderText(/Digite sua resposta/i), ANSWER_TEXT)
      await user.click(screen.getByTestId('submit-quiz'))

      await waitFor(() => {
        expect(submitAnswerMock).toHaveBeenCalledWith(
          'q-sensitive-text',
          ANSWER_TEXT,
          expect.objectContaining({ other_text: undefined }),
        )
      })
    } finally {
      if (localStorageDescriptor) {
        Object.defineProperty(window, 'localStorage', localStorageDescriptor)
      }
      if (sessionStorageDescriptor) {
        Object.defineProperty(window, 'sessionStorage', sessionStorageDescriptor)
      }
    }
  })
})
