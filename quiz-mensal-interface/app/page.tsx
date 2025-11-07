"use client"

import { useEffect, useState } from "react"
import QuizInterface from "@/components/quiz-interface"
import { extractTokenFromURL, isTokenExpired } from "@/lib/auth-utils"
import type { QuizSession, QuizError } from "@/types/quiz"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { AlertCircle, RefreshCcw } from "lucide-react"
import { ErrorBoundary } from "@/components/error/ErrorBoundary"
import { ResumeQuizDialog } from "@/components/quiz/ResumeQuizDialog"
import { loadQuizProgress, clearQuizProgress, cleanupOldProgress, type QuizProgress } from "@/lib/quiz-progress-storage"

export default function Home() {
  const [quizSession, setQuizSession] = useState<QuizSession | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<QuizError | null>(null)
  const [savedProgress, setSavedProgress] = useState<QuizProgress | null>(null)
  const [showResumeDialog, setShowResumeDialog] = useState(false)
  const [shouldResume, setShouldResume] = useState(false)

  useEffect(() => {
    // Cleanup old progress data on mount
    cleanupOldProgress()
    initializeQuiz()
  }, [])

  async function initializeQuiz() {
    setIsLoading(true)
    setError(null)

    try {
      // Get token from URL and clean it immediately
      const urlToken = extractTokenFromURL()

      if (!urlToken) {
        setError({
          detail: "Token de acesso não encontrado. Por favor, use o link enviado para você.",
          status: 400
        })
        setIsLoading(false)
        return
      }

      // SECURITY FIX: Use API route to initialize session with httpOnly cookie
      // Get CSRF token first
      const csrfResponse = await fetch('/api/csrf-token')
      const { csrfToken } = await csrfResponse.json()

      // Initialize session via API route (sets httpOnly cookie)
      const response = await fetch('/api/quiz/initialize-session', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': csrfToken
        },
        body: JSON.stringify({ token: urlToken }),
        credentials: 'include' // Important: include cookies
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.error || 'Failed to initialize session')
      }

      const session = await response.json()

      // Check if token is expired
      if (isTokenExpired(session.expires_at)) {
        setError({
          detail: "Este link expirou. Por favor, solicite um novo link ao seu médico.",
          status: 401
        })
        setIsLoading(false)
        return
      }

      // Check for saved progress
      const progress = loadQuizProgress(session.quiz_session_id)
      if (progress && progress.currentQuestionIndex < session.total_questions) {
        // Found saved progress - show resume dialog
        setSavedProgress(progress)
        setShowResumeDialog(true)
      }

      // Session is now stored in httpOnly cookie - no token in JavaScript!
      setQuizSession(session)
    } catch (err) {
      console.error("Error accessing quiz:", err)

      if (err instanceof Error) {
        setError({
          detail: err.message || "Erro ao carregar o questionário. Por favor, tente novamente.",
          status: (err as any).status
        })
      } else {
        setError({
          detail: "Erro inesperado ao carregar o questionário."
        })
      }
    } finally {
      setIsLoading(false)
    }
  }

  // Loading state
  if (isLoading) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-background via-muted/30 to-accent/20 flex items-center justify-center p-4">
        <Card className="p-8 text-center space-y-4">
          <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-lg text-muted-foreground">Carregando questionário...</p>
        </Card>
      </main>
    )
  }

  // Error state
  if (error) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-background via-muted/30 to-accent/20 flex items-center justify-center p-4">
        <Card className="p-8 max-w-md w-full space-y-6">
          <div className="text-center space-y-4">
            <AlertCircle className="w-16 h-16 text-destructive mx-auto" />
            <h2 className="text-2xl font-bold">Ops! Algo deu errado</h2>
            <p className="text-muted-foreground">{error.detail}</p>
          </div>

          {error.status !== 401 && (
            <Button
              onClick={initializeQuiz}
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
    if (quizSession) {
      clearQuizProgress(quizSession.quiz_session_id)
    }
    setShouldResume(false)
    setShowResumeDialog(false)
  }

  // Success state - show quiz
  if (quizSession) {
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
            session={quizSession}
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
