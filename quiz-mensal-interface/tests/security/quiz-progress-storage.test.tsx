import {
  cleanupOldProgress,
  clearQuizProgress,
  getAllSavedSessions,
  hasQuizProgress,
  loadQuizProgress,
  saveQuizProgress,
  type QuizProgress,
} from '@/lib/quiz-progress-storage'

const SESSION_ID = 'session-phi-abc-123'
const PATIENT_NAME = 'Paciente Maria PHI'
const TEMPLATE_NAME = 'Template Oncologia Mensal PHI'
const QUESTION_TEXT = 'Descreva dor, febre ou náusea com detalhes privados'
const ANSWER_TEXT = 'Dor intensa e náusea persistente'
const OTHER_TEXT = 'Outro texto livre com histórico clínico privado'
const TOKEN_VALUE = 'quiz-token-secret-abc.123'
const COOKIE_STATE = 'quiz_session_state=signed-cookie-state-abc'

function makeProgress(): QuizProgress {
  return {
    sessionId: SESSION_ID,
    currentQuestionIndex: 2,
    answers: {
      q1: ANSWER_TEXT,
      q2: { value: 'other', customText: OTHER_TEXT },
      q3: { options: ['option-a'], otherText: OTHER_TEXT },
    },
    otherTexts: {
      q2: OTHER_TEXT,
    },
    lastSaved: Date.now(),
    patientName: PATIENT_NAME,
    templateName: TEMPLATE_NAME,
    totalQuestions: 4,
  }
}

function storageKeys(): string[] {
  const keys: string[] = []
  for (let index = 0; index < localStorage.length; index += 1) {
    const key = localStorage.key(index)
    if (key) {
      keys.push(key)
    }
  }
  return keys
}

function storageSnapshot(): string {
  return storageKeys()
    .map((key) => `${key}\n${localStorage.getItem(key) ?? ''}`)
    .join('\n')
}

describe('quiz progress storage no-PHI contract', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    localStorage.clear()
    sessionStorage.clear()
  })

  it('load removes legacy records containing answers, labels, session IDs, tokens, cookies, invalid JSON, and large payloads', () => {
    localStorage.setItem(
      `quiz-progress-v1-${SESSION_ID}`,
      JSON.stringify({
        ...makeProgress(),
        questionText: QUESTION_TEXT,
        token: TOKEN_VALUE,
        cookieState: COOKIE_STATE,
      }),
    )
    localStorage.setItem('quiz-progress-v1-invalid-json', '{not valid json')
    localStorage.setItem(
      'quiz-progress-v1-large-record',
      JSON.stringify({
        ...makeProgress(),
        largePayload: `${ANSWER_TEXT}-${OTHER_TEXT}-`.repeat(500),
      }),
    )
    localStorage.setItem('quiz-progress', JSON.stringify(makeProgress()))
    localStorage.setItem('unrelated-dashboard-cache', 'keep-this-non-quiz-value')

    expect(loadQuizProgress(SESSION_ID)).toBeNull()

    expect(storageKeys().filter((key) => key === 'quiz-progress' || key.startsWith('quiz-progress-'))).toEqual([])
    expect(localStorage.getItem('unrelated-dashboard-cache')).toBe('keep-this-non-quiz-value')
    expect(storageSnapshot()).not.toContain(SESSION_ID)
    expect(storageSnapshot()).not.toContain(PATIENT_NAME)
    expect(storageSnapshot()).not.toContain(TEMPLATE_NAME)
    expect(storageSnapshot()).not.toContain(QUESTION_TEXT)
    expect(storageSnapshot()).not.toContain(ANSWER_TEXT)
    expect(storageSnapshot()).not.toContain(OTHER_TEXT)
    expect(storageSnapshot()).not.toContain(TOKEN_VALUE)
    expect(storageSnapshot()).not.toContain(COOKIE_STATE)
  })

  it('save never persists quiz answers, free text, session identifiers, patient labels, template labels, or token-like fields', () => {
    saveQuizProgress(makeProgress())

    expect(localStorage.length).toBe(0)
    expect(hasQuizProgress(SESSION_ID)).toBe(false)
    expect(getAllSavedSessions()).toEqual([])
    expect(storageSnapshot()).not.toContain(SESSION_ID)
    expect(storageSnapshot()).not.toContain(PATIENT_NAME)
    expect(storageSnapshot()).not.toContain(TEMPLATE_NAME)
    expect(storageSnapshot()).not.toContain(ANSWER_TEXT)
    expect(storageSnapshot()).not.toContain(OTHER_TEXT)
  })

  it('generic cleanup removes every legacy quiz-progress key while preserving unrelated localStorage entries', () => {
    localStorage.setItem(`quiz-progress-v1-${SESSION_ID}`, JSON.stringify(makeProgress()))
    localStorage.setItem('quiz-progress-v0-old', JSON.stringify(makeProgress()))
    localStorage.setItem('quiz-progress-corrupt', '{')
    localStorage.setItem('analytics-preference', 'allowed-non-quiz-value')

    cleanupOldProgress()

    expect(storageKeys().filter((key) => key === 'quiz-progress' || key.startsWith('quiz-progress-'))).toEqual([])
    expect(localStorage.getItem('analytics-preference')).toBe('allowed-non-quiz-value')
  })

  it('clear is generic and does not require a session identifier to remove legacy PHI records', () => {
    localStorage.setItem(`quiz-progress-v1-${SESSION_ID}`, JSON.stringify(makeProgress()))
    localStorage.setItem('quiz-progress-v1-another-session', JSON.stringify(makeProgress()))

    clearQuizProgress()

    expect(storageKeys().filter((key) => key === 'quiz-progress' || key.startsWith('quiz-progress-'))).toEqual([])
  })

  it('swallows unavailable localStorage failures without logging PHI or blocking callers', () => {
    const descriptor = Object.getOwnPropertyDescriptor(window, 'localStorage')

    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      get() {
        throw new Error('localStorage unavailable')
      },
    })

    try {
      expect(() => saveQuizProgress(makeProgress())).not.toThrow()
      expect(() => loadQuizProgress(SESSION_ID)).not.toThrow()
      expect(() => cleanupOldProgress()).not.toThrow()
      expect(() => clearQuizProgress()).not.toThrow()
      expect(hasQuizProgress(SESSION_ID)).toBe(false)
      expect(getAllSavedSessions()).toEqual([])
      expect(console.error).not.toHaveBeenCalled()
      expect(console.warn).not.toHaveBeenCalled()
      expect(console.log).not.toHaveBeenCalled()
    } finally {
      if (descriptor) {
        Object.defineProperty(window, 'localStorage', descriptor)
      }
    }
  })
})
