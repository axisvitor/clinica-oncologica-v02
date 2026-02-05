"use client"

import { useEffect, useState } from "react"
import { Suspense } from "react"
import QuizInterface from "@/components/quiz-interface"
import { useQuizSession } from "@/hooks/use-quiz-session"
import type { QuizError } from "@/types/quiz"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { AlertCircle, RefreshCcw } from "lucide-react"
import { ErrorBoundary } from "@/components/error/ErrorBoundary"
import { ResumeQuizDialog } from "@/components/quiz/ResumeQuizDialog"
import { QuizSkeleton } from "@/components/quiz/QuizSkeleton"
import { loadQuizProgress, clearQuizProgress, cleanupOldProgress, type QuizProgress } from "@/lib/quiz-progress-storage"

/**
 * Quiz Page Component
 *
 * Uses the unified useQuizSession hook for stateless security:
 * - CSRF token in RAM only (XSS immune)
 * - HttpOnly cookies for session (browser-managed)
 * - Direct connection to Python backend (no Next.js proxy)
 */
function QuizPage() {
  const { session, isLoading, error, retry } = useQuizSession()
  const [savedProgress, setSavedProgress] = useState<QuizProgress | null>(null)
  const [showResumeDialog, setShowResumeDialog] = useState(false)
  const [shouldResume, setShouldResume] = useState(false)

  useEffect(() => {
    // Cleanup old progress data on mount
    cleanupOldProgress()
  }, [])

  // Check for saved progress when session is loaded
  useEffect(() => {
    if (session?.quiz_session_id) {
      const progress = loadQuizProgress(session.quiz_session_id)
      if (progress && progress.currentQuestionIndex < (session.questions?.length ?? 0)) {
        setSavedProgress(progress)
        setShowResumeDialog(true)
      }
    }
  }, [session])

  // Loading state - show skeleton for better perceived performance
  if (isLoading) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-background via-muted/30 to-accent/20">
        <QuizSkeleton />
      </main>
    )
  }

  // Error state
  if (error) {
    const quizError: QuizError = {
      detail: error,
      status: error.includes("expirado") || error.includes("inválido") ? 401 : 500
    }

    return (
      <main className="min-h-screen bg-gradient-to-br from-background via-muted/30 to-accent/20 flex items-center justify-center p-4">
        <Card className="p-8 max-w-md w-full space-y-6">
          <div className="text-center space-y-4">
            <AlertCircle className="w-16 h-16 text-destructive mx-auto" />
            <h2 className="text-2xl font-bold">Ops! Algo deu errado</h2>
            <p className="text-muted-foreground">{quizError.detail}</p>
          </div>

          {quizError.status !== 401 && (
            <Button
              onClick={retry}
              className="w-full"
              size="lg"
            >
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

  const handleResume = () => {
    setShouldResume(true)
    setShowResumeDialog(false)
  }

  const handleStartFresh = () => {
    if (session) {
      clearQuizProgress(session.quiz_session_id)
    }
    setShouldResume(false)
    setShowResumeDialog(false)
  }

  // Success state - show quiz
  if (session) {
    return (
      <ErrorBoundary>
        <main className="min-h-screen bg-gradient-to-br from-background via-muted/30 to-accent/20">
          <ResumeQuizDialog
            open={showResumeDialog}
            progress={savedProgress}
            onResume={handleResume}
            onStartFresh={handleStartFresh}
          />
          <QuizInterface
            session={session}
            resumeFromSaved={shouldResume}
            onComplete={() => {
              // Quiz completed - could redirect or show completion message
              console.log("Quiz completed successfully!")
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
    <Suspense fallback={
      <main className="min-h-screen bg-gradient-to-br from-background via-muted/30 to-accent/20">
        <QuizSkeleton />
      </main>
    }>
      <QuizPage />
    </Suspense>
  )
}
