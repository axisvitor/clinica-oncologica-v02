"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Checkbox } from "@/components/ui/checkbox"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { CheckCircle, Circle, ArrowRight, ArrowLeft, Send, Loader2 } from "lucide-react"
import Image from "next/image"
import type { QuizSession, QuestionType, QuizQuestion, SingleAnswer, MultipleAnswer, OtherAnswer } from "@/types/quiz"
import { useQuizState } from "@/hooks/quiz/useQuizState"
import { useToast } from "@/hooks/use-toast"

interface QuizInterfaceProps {
  session: QuizSession
  onComplete?: () => void
}

export default function QuizInterface({ session, onComplete }: QuizInterfaceProps) {
  const { toast } = useToast()
  const {
    currentQuestionIndex,
    selectedAnswer,
    answers,
    otherTexts,
    isSubmitting,
    isCompleted,
    currentQuestion,
    totalQuestions,
    progress,
    isLastQuestion,
    setCurrentQuestionIndex,
    setSelectedAnswer,
    setAnswers,
    setOtherTexts,
    handleSubmitAnswer
  } = useQuizState({ session, onComplete })

  // Reset selected answer when question changes
  useEffect(() => {
    const savedAnswer = answers.get(currentQuestion.id)
    setSelectedAnswer(savedAnswer || null)
    // Restore other text if it was saved
    const savedOtherText = otherTexts.get(currentQuestion.id)
    if (savedOtherText && savedAnswer && typeof savedAnswer === 'object' && 'value' in savedAnswer) {
      // Text is already in the OtherAnswer object
    }
  }, [currentQuestionIndex, currentQuestion.id, answers, otherTexts])

  const handleAnswerChange = (value: SingleAnswer | MultipleAnswer) => {
    setSelectedAnswer(value)
  }

  const handleOtherTextChange = (text: string, otherOptionValue: string) => {
    setOtherTexts(new Map(otherTexts.set(currentQuestion.id, text)))
    // Update selected answer if "Outra" is selected
    if (typeof selectedAnswer === 'object' && selectedAnswer && 'value' in selectedAnswer) {
      setSelectedAnswer({ value: otherOptionValue, customText: text } as OtherAnswer)
    }
  }

  const handleAnswerSubmit = async () => {
    if (!selectedAnswer) {
      toast({
        title: "Resposta obrigatória",
        description: "Por favor, selecione uma resposta antes de continuar.",
        variant: "destructive"
      })
      return
    }

    // Validate "Outra" option has text
    if (typeof selectedAnswer === 'object' && selectedAnswer && 'value' in selectedAnswer) {
      if (!selectedAnswer.customText || selectedAnswer.customText.trim() === '') {
        toast({
          title: "Texto obrigatório",
          description: "Por favor, digite sua resposta personalizada.",
          variant: "destructive"
        })
        return
      }
    }

    try {
      // Prepare the answer value and other_text
      let answerValue: string | string[]
      let otherText: string | undefined

      if (typeof selectedAnswer === 'object' && selectedAnswer && 'value' in selectedAnswer) {
        // Single choice with "Outra" option - use the real option value
        answerValue = selectedAnswer.value
        otherText = selectedAnswer.customText
      } else if (typeof selectedAnswer === 'object' && selectedAnswer && 'options' in selectedAnswer) {
        // Multiple choice (potentially with other text)
        answerValue = selectedAnswer.options
        otherText = selectedAnswer.otherText
      } else {
        // Regular answer (string or string[])
        answerValue = selectedAnswer as string | string[]
      }

      // Submit answer using secure authentication
      await handleSubmitAnswer(
        currentQuestion.id,
        answerValue,
        { question_index: currentQuestionIndex, other_text: otherText }
      )

      // Save answer locally
      setAnswers(new Map(answers.set(currentQuestion.id, selectedAnswer)))

      toast({
        title: "Resposta enviada!",
        description: isLastQuestion
          ? "Questionário concluído com sucesso!"
          : "Sua resposta foi registrada.",
      })

    } catch (error) {
      console.error("Error submitting answer:", error)
      toast({
        title: "Erro ao enviar resposta",
        description: error instanceof Error ? error.message : "Tente novamente em alguns instantes.",
        variant: "destructive"
      })
    }
  }

  const handlePreviousQuestion = () => {
    if (currentQuestionIndex > 0) {
      setCurrentQuestionIndex(prev => prev - 1)
    }
  }

  const renderQuestionInput = () => {
    switch (currentQuestion.type) {
      case "single_choice":
        const singleValue = typeof selectedAnswer === 'object' && selectedAnswer && 'value' in selectedAnswer
          ? selectedAnswer.value
          : (selectedAnswer as string || "")
        const otherTextValue = otherTexts.get(currentQuestion.id) || ""

        // Find the "other" option value dynamically
        const otherOption = currentQuestion.options?.find(opt => {
          if (typeof opt === 'string') return false
          return opt.allow_other === true || opt.value.toLowerCase() === 'other' || opt.value.toLowerCase() === 'outro' || opt.value.toLowerCase() === 'outra'
        })
        const otherOptionValue = typeof otherOption === 'object' ? otherOption.value : 'other'

        return (
          <div className="space-y-3">
            <RadioGroup
              value={singleValue}
              onValueChange={(value) => {
                if (value === otherOptionValue) {
                  handleAnswerChange({ value: otherOptionValue, customText: otherTextValue } as OtherAnswer)
                } else {
                  handleAnswerChange(value)
                }
              }}
              className="space-y-3"
            >
              {currentQuestion.options?.map((option, index) => {
                const optionValue = typeof option === 'string' ? option : option.value
                const optionText = typeof option === 'string' ? option : option.text
                return (
                  <div
                    key={typeof option === 'string' ? index : option.id}
                    className="flex items-center space-x-3 p-4 rounded-xl border-2 border-border hover:border-primary/50 hover:bg-primary/5 transition-all cursor-pointer"
                  >
                    <RadioGroupItem value={optionValue} id={`option-${index}`} />
                    <Label
                      htmlFor={`option-${index}`}
                      className="flex-1 cursor-pointer font-medium"
                    >
                      {optionText}
                    </Label>
                  </div>
                )
              })}

              {/* "Outra" option if allowed */}
              {currentQuestion.allow_other && (
                <div className="space-y-3">
                  <div className="flex items-center space-x-3 p-4 rounded-xl border-2 border-border hover:border-primary/50 hover:bg-primary/5 transition-all cursor-pointer">
                    <RadioGroupItem value={otherOptionValue} id="option-other" />
                    <Label
                      htmlFor="option-other"
                      className="flex-1 cursor-pointer font-medium"
                    >
                      Outra
                    </Label>
                  </div>

                  {/* Show text input when "Outra" is selected */}
                  {singleValue === otherOptionValue && (
                    <Textarea
                      value={otherTextValue}
                      onChange={(e) => handleOtherTextChange(e.target.value, otherOptionValue)}
                      placeholder="Digite sua resposta personalizada..."
                      className="min-h-24 resize-none ml-7"
                      required
                    />
                  )}
                </div>
              )}
            </RadioGroup>
          </div>
        )

      case "multiple_choice":
        let multipleAnswers: string[] = []
        let hasOtherSelected = false

        // Find the "other" option value dynamically for multiple choice
        const multiOtherOption = currentQuestion.options?.find(opt => {
          if (typeof opt === 'string') return false
          return opt.allow_other === true || opt.value.toLowerCase() === 'other' || opt.value.toLowerCase() === 'outro' || opt.value.toLowerCase() === 'outra'
        })
        const multiOtherOptionValue = typeof multiOtherOption === 'object' ? multiOtherOption.value : 'other'

        if (selectedAnswer) {
          if (Array.isArray(selectedAnswer)) {
            multipleAnswers = selectedAnswer
          } else if (typeof selectedAnswer === 'object' && 'options' in selectedAnswer) {
            multipleAnswers = selectedAnswer.options
            hasOtherSelected = multipleAnswers.includes(multiOtherOptionValue)
          }
        }

        const multiOtherTextValue = otherTexts.get(currentQuestion.id) || ""

        return (
          <div className="space-y-3">
            {currentQuestion.options?.map((option, index) => {
              const optionValue = typeof option === 'string' ? option : option.value
              const optionText = typeof option === 'string' ? option : option.text
              return (
                <div
                  key={typeof option === 'string' ? index : option.id}
                  className="flex items-center space-x-3 p-4 rounded-xl border-2 border-border hover:border-primary/50 hover:bg-primary/5 transition-all"
                >
                  <Checkbox
                    id={`option-${index}`}
                    checked={multipleAnswers.includes(optionValue)}
                    onCheckedChange={(checked) => {
                      let newAnswers: string[]
                      if (checked) {
                        newAnswers = [...multipleAnswers, optionValue]
                      } else {
                        newAnswers = multipleAnswers.filter(a => a !== optionValue)
                      }

                      if (newAnswers.includes(multiOtherOptionValue)) {
                        handleAnswerChange({ options: newAnswers, otherText: multiOtherTextValue })
                      } else {
                        handleAnswerChange(newAnswers)
                      }
                    }}
                  />
                  <Label
                    htmlFor={`option-${index}`}
                    className="flex-1 cursor-pointer font-medium"
                  >
                    {optionText}
                  </Label>
                </div>
              )
            })}

            {/* "Outra" option if allowed */}
            {currentQuestion.allow_other && (
              <div className="space-y-3">
                <div className="flex items-center space-x-3 p-4 rounded-xl border-2 border-border hover:border-primary/50 hover:bg-primary/5 transition-all">
                  <Checkbox
                    id="option-other"
                    checked={multipleAnswers.includes(multiOtherOptionValue)}
                    onCheckedChange={(checked) => {
                      let newAnswers: string[]
                      if (checked) {
                        newAnswers = [...multipleAnswers, multiOtherOptionValue]
                        handleAnswerChange({ options: newAnswers, otherText: multiOtherTextValue })
                      } else {
                        newAnswers = multipleAnswers.filter(a => a !== multiOtherOptionValue)
                        if (newAnswers.length > 0) {
                          handleAnswerChange(newAnswers)
                        } else {
                          handleAnswerChange([])
                        }
                      }
                    }}
                  />
                  <Label
                    htmlFor="option-other"
                    className="flex-1 cursor-pointer font-medium"
                  >
                    Outra
                  </Label>
                </div>

                {/* Show text input when "Outra" is selected */}
                {multipleAnswers.includes(multiOtherOptionValue) && (
                  <Textarea
                    value={multiOtherTextValue}
                    onChange={(e) => {
                      handleOtherTextChange(e.target.value, multiOtherOptionValue)
                      handleAnswerChange({ options: multipleAnswers, otherText: e.target.value })
                    }}
                    placeholder="Digite sua resposta personalizada..."
                    className="min-h-24 resize-none ml-7"
                    required
                  />
                )}
              </div>
            )}
          </div>
        )

      case "scale":
        const scaleMin = currentQuestion.min_value || 0
        const scaleMax = currentQuestion.max_value || 10
        const scaleValues = Array.from({ length: scaleMax - scaleMin + 1 }, (_, i) => scaleMin + i)

        return (
          <div className="space-y-4">
            <div className="flex justify-between items-center gap-2">
              {scaleValues.map((value) => (
                <button
                  key={value}
                  onClick={() => handleAnswerChange(value.toString())}
                  className={`
                    flex-1 h-12 rounded-lg border-2 transition-all font-semibold
                    ${selectedAnswer === value.toString()
                      ? "border-primary bg-primary text-primary-foreground shadow-lg scale-110"
                      : "border-border hover:border-primary/50 hover:bg-primary/5"
                    }
                  `}
                >
                  {value}
                </button>
              ))}
            </div>
            <div className="flex justify-between text-sm text-muted-foreground">
              <span>Mínimo ({scaleMin})</span>
              <span>Máximo ({scaleMax})</span>
            </div>
          </div>
        )

      case "text":
        return (
          <Textarea
            value={selectedAnswer as string || ""}
            onChange={(e) => handleAnswerChange(e.target.value)}
            placeholder="Digite sua resposta aqui..."
            className="min-h-32 resize-none"
          />
        )

      case "yes_no":
        return (
          <RadioGroup
            value={selectedAnswer as string || ""}
            onValueChange={handleAnswerChange}
            className="space-y-3"
          >
            <div className="flex items-center space-x-3 p-4 rounded-xl border-2 border-border hover:border-primary/50 hover:bg-primary/5 transition-all cursor-pointer">
              <RadioGroupItem value="yes" id="yes" />
              <Label htmlFor="yes" className="flex-1 cursor-pointer font-medium">
                Sim
              </Label>
            </div>
            <div className="flex items-center space-x-3 p-4 rounded-xl border-2 border-border hover:border-primary/50 hover:bg-primary/5 transition-all cursor-pointer">
              <RadioGroupItem value="no" id="no" />
              <Label htmlFor="no" className="flex-1 cursor-pointer font-medium">
                Não
              </Label>
            </div>
          </RadioGroup>
        )

      default:
        return <p>Tipo de questão não suportado</p>
    }
  }

  // Completion screen
  if (isCompleted) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <div className="w-full max-w-md mx-auto space-y-6">
          <Card className="p-8 text-center space-y-6">
            <div className="w-20 h-20 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center mx-auto">
              <CheckCircle className="w-12 h-12 text-green-600 dark:text-green-400" />
            </div>
            <div className="space-y-2">
              <h2 className="text-2xl font-bold">Questionário Concluído!</h2>
              <p className="text-muted-foreground">
                Obrigado por responder ao questionário mensal. Suas respostas foram registradas com sucesso.
              </p>
            </div>
            <div className="pt-4 border-t space-y-2">
              <p className="text-sm text-muted-foreground">
                Suas respostas ajudam nossa equipe a acompanhar seu bem-estar e oferecer o melhor cuidado possível.
              </p>
            </div>
          </Card>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-2xl mx-auto space-y-6">
        {/* Header */}
        <div className="text-center space-y-4">
          <div className="inline-flex items-center gap-2 bg-primary/10 text-primary px-4 py-2 rounded-full text-sm font-medium">
            <Circle className="w-4 h-4 fill-current" />
            Quiz Mensal - {session.patient_name}
          </div>
          <h1 className="text-2xl font-bold">{session.template_name}</h1>
        </div>

        {/* Progress */}
        <div className="space-y-2">
          <div className="flex justify-between text-sm text-muted-foreground">
            <span>Pergunta {currentQuestionIndex + 1} de {totalQuestions}</span>
            <span>{Math.round(progress)}%</span>
          </div>
          <Progress value={progress} className="h-2" />
        </div>

        {/* Question Card */}
        <Card className="p-6 space-y-6">
          <div className="space-y-4">
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold flex-shrink-0">
                {currentQuestionIndex + 1}
              </div>
              <h2 className="text-lg font-semibold text-balance leading-relaxed flex-1">
                {currentQuestion.text}
              </h2>
            </div>

            {/* Question Input */}
            <div className="pl-11">
              {renderQuestionInput()}
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-4 border-t">
            {currentQuestionIndex > 0 && (
              <Button
                onClick={handlePreviousQuestion}
                variant="outline"
                disabled={isSubmitting}
                className="flex-1"
              >
                <ArrowLeft className="w-4 h-4 mr-2" />
                Voltar
              </Button>
            )}

            <Button
              onClick={handleAnswerSubmit}
              disabled={!selectedAnswer || isSubmitting}
              className="flex-1"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Enviando...
                </>
              ) : isLastQuestion ? (
                <>
                  <Send className="w-4 h-4 mr-2" />
                  Finalizar Quiz
                </>
              ) : (
                <>
                  Próxima
                  <ArrowRight className="w-4 h-4 ml-2" />
                </>
              )}
            </Button>
          </div>
        </Card>

        {/* Footer */}
        <div className="text-center text-sm text-muted-foreground space-y-1">
          <p>Suas respostas são confidenciais e seguras</p>
          <p className="text-xs">Link válido até: {new Date(session.expires_at).toLocaleDateString("pt-BR")}</p>
        </div>
      </div>
    </div>
  )
}