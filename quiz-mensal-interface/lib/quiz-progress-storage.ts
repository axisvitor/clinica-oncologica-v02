/**
 * Quiz Progress Storage Utilities
 *
 * Security contract: quiz answers, free text, session identifiers, patient labels,
 * template labels, tokens, and cookie-derived state must never be persisted in web
 * storage. Previous versions used quiz-progress-* localStorage keys; this module now
 * only removes those legacy keys and reports no locally resumable progress.
 */

import type { SingleAnswer, MultipleAnswer } from '@/types/quiz'

export interface QuizProgress {
  sessionId: string
  currentQuestionIndex: number
  answers: Record<string, SingleAnswer | MultipleAnswer>
  otherTexts: Record<string, string>
  lastSaved: number
  patientName: string
  templateName: string
  totalQuestions: number
}

const LEGACY_STORAGE_KEY = 'quiz-progress'
const LEGACY_STORAGE_PREFIX = `${LEGACY_STORAGE_KEY}-`

function getLocalStorage(): Storage | null {
  try {
    if (typeof window === 'undefined') {
      return null
    }

    return window.localStorage ?? null
  } catch {
    return null
  }
}

function isLegacyQuizProgressKey(key: string): boolean {
  return key === LEGACY_STORAGE_KEY || key.startsWith(LEGACY_STORAGE_PREFIX)
}

function removeLegacyQuizProgressKeys(): void {
  const storage = getLocalStorage()
  if (!storage) {
    return
  }

  try {
    const keysToRemove: string[] = []

    for (let index = 0; index < storage.length; index += 1) {
      const key = storage.key(index)
      if (key && isLegacyQuizProgressKey(key)) {
        keysToRemove.push(key)
      }
    }

    keysToRemove.forEach((key) => {
      try {
        storage.removeItem(key)
      } catch {
        // Ignore individual removal failures; storage cleanup must not block quiz use.
      }
    })
  } catch {
    // Ignore unavailable/quota/security storage failures without logging PHI-bearing data.
  }
}

/**
 * Intentionally does not write quiz progress. Backend session state plus the HttpOnly
 * quiz_session_state cookie are the only supported resume mechanism.
 */
export function saveQuizProgress(_progress: QuizProgress): void {
  removeLegacyQuizProgressKeys()
}

/**
 * Local answer restore is disabled. Loading removes any legacy quiz-progress-* data
 * and always reports that there is no client-side progress to resume.
 */
export function loadQuizProgress(_sessionId: string): QuizProgress | null {
  removeLegacyQuizProgressKeys()
  return null
}

/**
 * Clears all legacy quiz progress entries generically, without relying on or logging
 * session identifiers.
 */
export function clearQuizProgress(_sessionId?: string): void {
  removeLegacyQuizProgressKeys()
}

/**
 * Client-side quiz progress no longer exists. This remains for compatibility with
 * older callers while opportunistically removing legacy records.
 */
export function hasQuizProgress(_sessionId: string): boolean {
  removeLegacyQuizProgressKeys()
  return false
}

/**
 * Client-side saved sessions no longer exist. This remains for compatibility with
 * older callers while opportunistically removing legacy records.
 */
export function getAllSavedSessions(): QuizProgress[] {
  removeLegacyQuizProgressKeys()
  return []
}

/**
 * Remove all historical quiz-progress-* localStorage records, including malformed or
 * oversized entries, while preserving unrelated web-storage keys.
 */
export function cleanupOldProgress(): void {
  removeLegacyQuizProgressKeys()
}
