/**
 * Quiz Progress Storage Utilities
 * Manages localStorage persistence for quiz progress recovery
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

const STORAGE_KEY = 'quiz-progress'
const STORAGE_VERSION = 'v1'
const MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000 // 7 days

/**
 * Generate storage key for a specific session
 */
function getStorageKey(sessionId: string): string {
  return `${STORAGE_KEY}-${STORAGE_VERSION}-${sessionId}`
}

/**
 * Save quiz progress to localStorage
 */
export function saveQuizProgress(progress: QuizProgress): void {
  try {
    const key = getStorageKey(progress.sessionId)
    const data = {
      ...progress,
      lastSaved: Date.now(),
    }
    localStorage.setItem(key, JSON.stringify(data))
    console.log(`Quiz progress saved for session ${progress.sessionId}`)
  } catch (error) {
    console.error('Failed to save quiz progress:', error)
    // Don't throw - localStorage may be full or disabled
  }
}

/**
 * Load quiz progress from localStorage
 */
export function loadQuizProgress(sessionId: string): QuizProgress | null {
  try {
    const key = getStorageKey(sessionId)
    const raw = localStorage.getItem(key)

    if (!raw) {
      return null
    }

    const progress = JSON.parse(raw) as QuizProgress

    // Validate progress data
    if (
      !progress.sessionId ||
      !progress.answers ||
      typeof progress.currentQuestionIndex !== 'number'
    ) {
      console.warn('Invalid quiz progress data, ignoring')
      clearQuizProgress(sessionId)
      return null
    }

    // Check if progress is too old
    const age = Date.now() - progress.lastSaved
    if (age > MAX_AGE_MS) {
      console.log('Quiz progress expired, clearing')
      clearQuizProgress(sessionId)
      return null
    }

    console.log(`Quiz progress loaded for session ${sessionId}`)
    return progress
  } catch (error) {
    console.error('Failed to load quiz progress:', error)
    return null
  }
}

/**
 * Clear quiz progress from localStorage
 */
export function clearQuizProgress(sessionId: string): void {
  try {
    const key = getStorageKey(sessionId)
    localStorage.removeItem(key)
    console.log(`Quiz progress cleared for session ${sessionId}`)
  } catch (error) {
    console.error('Failed to clear quiz progress:', error)
  }
}

/**
 * Check if quiz progress exists for a session
 */
export function hasQuizProgress(sessionId: string): boolean {
  try {
    const key = getStorageKey(sessionId)
    return localStorage.getItem(key) !== null
  } catch (error) {
    return false
  }
}

/**
 * Get all saved quiz sessions
 */
export function getAllSavedSessions(): QuizProgress[] {
  try {
    const sessions: QuizProgress[] = []
    const prefix = `${STORAGE_KEY}-${STORAGE_VERSION}-`

    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i)
      if (key && key.startsWith(prefix)) {
        const raw = localStorage.getItem(key)
        if (raw) {
          try {
            const progress = JSON.parse(raw) as QuizProgress
            sessions.push(progress)
          } catch {
            // Skip invalid entries
          }
        }
      }
    }

    return sessions
  } catch (error) {
    console.error('Failed to get saved sessions:', error)
    return []
  }
}

/**
 * Clean up old progress data
 */
export function cleanupOldProgress(): void {
  try {
    const sessions = getAllSavedSessions()
    const now = Date.now()

    sessions.forEach((progress) => {
      const age = now - progress.lastSaved
      if (age > MAX_AGE_MS) {
        clearQuizProgress(progress.sessionId)
      }
    })
  } catch (error) {
    console.error('Failed to cleanup old progress:', error)
  }
}
