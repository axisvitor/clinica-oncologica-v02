"use client"

import { useEffect, useState } from "react"
import QuizInterface from "@/components/quiz-interface"
import { extractTokenFromURL, isTokenExpired } from "@/lib/auth-utils"
import { secureTokenManager } from "@/lib/secure-token-manager"
import { quizAPI } from "@/lib/api"
import type { QuizSession, QuizError } from "@/types/quiz"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { AlertCircle, RefreshCcw } from "lucide-react"

export default function Home() {
  const [quizSession, setQuizSession] = useState<QuizSession | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<QuizError | null>(null)

  useEffect(() => {
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

      // Access quiz directly via API (no cookies needed)
      const session = await quizAPI.accessQuiz(urlToken)

      // Check if token is expired
      if (isTokenExpired(session.expires_at)) {
        setError({
          detail: "Este link expirou. Por favor, solicite um novo link ao seu médico.",
          status: 401
        })
        setIsLoading(false)
        return
      }

      // Store the initial token for the session
      if (!session.new_token) {
        session.new_token = urlToken
      }

      // Persist token locally for refresh scenarios
      secureTokenManager.updateToken(session.new_token, session.expires_at)

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

  // Success state - show quiz
  if (quizSession) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-background via-muted/30 to-accent/20">
        <QuizInterface
          session={quizSession}
          onComplete={() => {
            // Quiz completed - could redirect or show completion message
            console.log("Quiz completed successfully!")
          }}
        />
      </main>
    )
  }

  return null
}
