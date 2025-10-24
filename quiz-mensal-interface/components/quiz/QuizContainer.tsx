"use client"

import { useEffect } from "react"
import { Card } from "@/components/ui/card"
import type { QuizSession } from "@/types/quiz"
import { QuizHeader } from "./QuizHeader"
import { QuizProgress } from "./QuizProgress"
import { QuizNavigation } from "./QuizNavigation"
import { QuizCompletion } from "./QuizCompletion"
import { QuestionRenderer } from "./QuestionRenderer"
import { useQuizState } from "@/hooks/quiz/useQuizState"
import { useQuizAnswer } from "@/hooks/quiz/useQuizAnswer"
import { useQuizNavigation } from "@/hooks/quiz/useQuizNavigation"

interface QuizContainerProps {
  session: QuizSession
  token: string
  onComplete?: () => void
  onTokenUpdate?: (newToken: string) => void
}

export default function QuizContainer({
  session,
  token,
  onComplete,
  onTokenUpdate
}: QuizContainerProps) {
  const quizState = useQuizState({ 
    session, 
    initialToken: token,
    onComplete 
  })
  const quizAnswer = useQuizAnswer()

  // SECURITY: No token handling in JavaScript - using httpOnly cookies
  // Token is managed server-side via /api/quiz/initialize-session
  // All requests use credentials: 'include' to send cookie automatically

  const navigation = useQuizNavigation({
    currentToken: token, // Only used for initial setup, not stored
    currentQuestionIndex: quizState.currentQuestionIndex,
    currentQuestionId: quizState.currentQuestion.id,
    isLastQuestion: quizState.isLastQuestion,
    selectedAnswer: quizState.selectedAnswer,
    validateAnswer: quizAnswer.validateAnswer,
    prepareAnswerPayload: quizAnswer.prepareAnswerPayload,
    onAnswerSaved: (questionId, answer) => {
      quizState.setAnswers(new Map(quizState.answers.set(questionId, answer)))
    },
    onNextQuestion: () => {
      quizState.setCurrentQuestionIndex(prev => prev + 1)
      quizState.setSelectedAnswer(null)
    },
    onComplete: () => {
      quizState.setIsCompleted(true)
      onComplete?.()
    },
    setIsSubmitting: quizState.setIsSubmitting,
  })

  const handleOtherTextChange = (text: string, otherOptionValue: string) => {
    quizState.setOtherTexts(new Map(quizState.otherTexts.set(quizState.currentQuestion.id, text)))
    const updatedAnswer = quizAnswer.handleOtherTextChange(text, otherOptionValue, quizState.selectedAnswer)
    if (updatedAnswer) {
      quizState.setSelectedAnswer(updatedAnswer)
    }
  }

  // Completion screen
  if (quizState.isCompleted) {
    return <QuizCompletion expiresAt={session.expires_at} />
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-2xl mx-auto space-y-6">
        <QuizHeader
          patientName={session.patient_name}
          templateName={session.template_name}
        />

        <QuizProgress
          currentQuestion={quizState.currentQuestionIndex + 1}
          totalQuestions={quizState.totalQuestions}
          progress={quizState.progress}
        />

        <Card className="p-6 space-y-6">
          <div className="space-y-4">
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold flex-shrink-0">
                {quizState.currentQuestionIndex + 1}
              </div>
              <h2 className="text-lg font-semibold text-balance leading-relaxed flex-1">
                {quizState.currentQuestion.text}
              </h2>
            </div>

            <div className="pl-11">
              <QuestionRenderer
                question={quizState.currentQuestion}
                selectedAnswer={quizState.selectedAnswer}
                otherText={quizState.otherTexts.get(quizState.currentQuestion.id) || ""}
                onAnswerChange={quizState.setSelectedAnswer}
                onOtherTextChange={handleOtherTextChange}
              />
            </div>
          </div>

          <QuizNavigation
            currentQuestionIndex={quizState.currentQuestionIndex}
            isLastQuestion={quizState.isLastQuestion}
            isSubmitting={quizState.isSubmitting}
            hasAnswer={!!quizState.selectedAnswer}
            onPrevious={() => navigation.handlePreviousQuestion(quizState.setCurrentQuestionIndex)}
            onSubmit={navigation.handleSubmitAnswer}
          />
        </Card>

        <div className="text-center text-sm text-muted-foreground space-y-1">
          <p>Suas respostas são confidenciais e seguras</p>
          <p className="text-xs">
            Link válido até: {new Date(session.expires_at).toLocaleDateString("pt-BR")}
          </p>
        </div>
      </div>
    </div>
  )
}
