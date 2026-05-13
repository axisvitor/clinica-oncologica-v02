'use client'

import { useEffect } from 'react'
import { Suspense } from 'react'
import QuizInterface from '@/components/quiz-interface'
import { useQuizSession } from '@/hooks/use-quiz-session'
import type { QuizError } from '@/types/quiz'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { AlertCircle, RefreshCcw } from 'lucide-react'
import { ErrorBoundary } from '@/components/error/ErrorBoundary'
import { QuizSkeleton } from '@/components/quiz/QuizSkeleton'
import { QUIZ_CENTERED_SHELL_CLASS, QUIZ_SHELL_CLASS } from '@/lib/quiz-shell'
import { cleanupOldProgress } from '@/lib/quiz-progress-storage'

/**
 * Quiz Page Component
 *
 * Uses the unified useQuizSession hook for stateless security:
 * - CSRF token in RAM only (XSS immune)
 * - HttpOnly cookies for session (browser-managed)
 * - Direct connection to Python backend (no Next.js proxy)
 * - Resume position comes from backend session.current_question_index only
 */
function QuizPage() {
  const { session, isLoading, error, retry } = useQuizSession()

  useEffect(() => {
    // Remove any legacy localStorage answer cache without reading or restoring it.
    cleanupOldProgress()
  }, [])

  // Loading state - show skeleton for better perceived performance
  if (isLoading) {
    return (
      <main className={QUIZ_SHELL_CLASS}>
        <QuizSkeleton />
      </main>
    )
  }

  // Error state
  if (error) {
    const quizError: QuizError = {
      detail: error,
      status: error.includes('expirado') || error.includes('inválido') ? 401 : 500,
    }

    return (
      <main className={`${QUIZ_CENTERED_SHELL_CLASS} p-4`}>
        <Card className="p-8 max-w-md w-full space-y-6">
          <div className="text-center space-y-4">
            <AlertCircle className="w-16 h-16 text-destructive mx-auto" />
            <h2 className="text-2xl font-bold">Ops! Algo deu errado</h2>
            <p className="text-muted-foreground">{quizError.detail}</p>
          </div>

          {quizError.status !== 401 && (
            <Button onClick={retry} className="w-full" size="lg">
              <RefreshCcw className="w-5 h-5 mr-2" />
              Tentar Novamente
            </Button>
          )}

          <div className="text-center text-sm text-muted-foreground">
            <p>Precisa de ajuda? Entre em contato com nossa equipe.</p>
          </div>
        </Card>
      </main>
    )
  }

  // Success state - show quiz
  if (session) {
    return (
      <ErrorBoundary>
        <main className={QUIZ_SHELL_CLASS}>
          <QuizInterface
            session={session}
            onComplete={() => {
              // Quiz completed - could redirect or show completion message
              console.log('Quiz completed successfully!')
            }}
          />
        </main>
      </ErrorBoundary>
    )
  }

  return null
}

/**
 * Home Page with Suspense Boundary
 *
 * Required for Next.js App Router with useSearchParams
 */
export default function Home() {
  return (
    <Suspense
      fallback={
        <main className={QUIZ_SHELL_CLASS}>
          <QuizSkeleton />
        </main>
      }
    >
      <QuizPage />
    </Suspense>
  )
}
