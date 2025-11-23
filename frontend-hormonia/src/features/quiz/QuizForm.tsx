import React, { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { CheckCircle, Circle, Star } from 'lucide-react'
import { apiClient } from '../../lib/api-client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Checkbox } from '@/components/ui/checkbox'
import { Slider } from '@/components/ui/slider'
import { useToast } from '@/components/ui/use-toast'
import { LoadingSpinner } from '@/components/ui/loading-spinner'
import { getErrorMessage } from '@/lib/utils/type-guards'

import type { QuizSession as BaseQuizSession } from '@/lib/api-client/types'

interface Question {
  id: string
  type: 'multiple_choice' | 'yes_no' | 'scale' | 'text' | 'checkbox'
  question: string
  options?: string[]
  min?: number
  max?: number
  required: boolean
}

// Extend QuizSession with UI-specific fields (questions array)
interface QuizSession extends Partial<BaseQuizSession> {
  id: string
  patient_id: string
  template_id?: string
  quiz_template_id?: string
  template_name?: string
  questions: Question[]
  status: 'completed' | 'pending' | 'in_progress' | 'abandoned'
  responses: Record<string, unknown>
}

interface QuizFormProps {
  session: QuizSession
  onComplete?: () => void
}

export function QuizForm({ session, onComplete }: QuizFormProps) {
  const [responses, setResponses] = useState<Record<string, unknown>>(session.responses || {})
  const { toast } = useToast()
  const queryClient = useQueryClient()

  const submitResponseMutation = useMutation({
    mutationFn: async (data: { session_id: string; responses: Record<string, unknown> }) => {
      // Submit each question response individually
      const submissions = Object.entries(data.responses).map(([questionId, answer]) =>
        apiClient.quiz.submitResponse(data.session_id, questionId, String(answer))
      )

      // Wait for all submissions to complete
      await Promise.all(submissions)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['quiz-sessions'] })
      queryClient.invalidateQueries({ queryKey: ['quiz-session', session.id] })
      toast({
        title: 'Questionário enviado',
        description: 'Suas respostas foram salvas com sucesso.',
      })
      onComplete?.()
    },
    onError: (error: unknown) => {
      toast({
        title: 'Erro ao enviar questionário',
        description: getErrorMessage(error) || 'Ocorreu um erro inesperado.',
        variant: 'destructive'
      })
    }
  })

  const handleResponseChange = (questionId: string, value: string | number | boolean | string[]) => {
    setResponses(prev => ({
      ...prev,
      [questionId]: value
    }))
  }

  const handleSubmit = () => {
    // Validate required questions
    const requiredQuestions = session.questions.filter(q => q.required)
    const missingResponses = requiredQuestions.filter(q =>
      !responses[q.id] || responses[q.id] === '' || responses[q.id] === null
    )

    if (missingResponses.length > 0) {
      toast({
        title: 'Campos obrigatórios',
        description: `Por favor, responda todas as perguntas obrigatórias (${missingResponses.length} restantes).`,
        variant: 'destructive'
      })
      return
    }

    submitResponseMutation.mutate({
      session_id: session.id,
      responses
    })
  }

  const renderQuestion = (question: Question) => {
    const value = responses[question.id]

    switch (question.type) {
      case 'multiple_choice':
        return (
          <RadioGroup
            value={(value as string) || ''}
            onValueChange={(newValue) => handleResponseChange(question.id, newValue)}
          >
            {question.options?.map((option, index) => (
              <div key={index} className="flex items-center space-x-2">
                <RadioGroupItem value={option} id={`${question.id}-${index}`} />
                <Label htmlFor={`${question.id}-${index}`}>{option}</Label>
              </div>
            ))}
          </RadioGroup>
        )

      case 'yes_no':
        return (
          <RadioGroup
            value={(value as string) || ''}
            onValueChange={(newValue) => handleResponseChange(question.id, newValue)}
          >
            <div className="flex items-center space-x-2">
              <RadioGroupItem value="yes" id={`${question.id}-yes`} />
              <Label htmlFor={`${question.id}-yes`}>Sim</Label>
            </div>
            <div className="flex items-center space-x-2">
              <RadioGroupItem value="no" id={`${question.id}-no`} />
              <Label htmlFor={`${question.id}-no`}>Não</Label>
            </div>
          </RadioGroup>
        )

      case 'scale': {
        const scaleValue = (value as number) || question.min || 1
        return (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-500">{question.min}</span>
              <span className="font-medium text-lg">{scaleValue}</span>
              <span className="text-sm text-gray-500">{question.max}</span>
            </div>
            <Slider
              value={[scaleValue as number]}
              onValueChange={(newValue) => handleResponseChange(question.id, newValue[0] as number)}
              min={question.min || 1}
              max={question.max || 10}
              step={1}
              className="w-full"
            />
            <div className="flex justify-between text-xs text-gray-400">
              {Array.from({ length: (question.max || 10) - (question.min || 1) + 1 }, (_, i) => (
                <span key={i}>{(question.min || 1) + i}</span>
              ))}
            </div>
          </div>
        )
      }

      case 'text':
        return (
          <Textarea
            value={(value as string) || ''}
            onChange={(e) => handleResponseChange(question.id, e.target.value)}
            placeholder="Digite sua resposta..."
            rows={4}
          />
        )

      case 'checkbox': {
        const checkboxValues = Array.isArray(value) ? value : []
        return (
          <div className="space-y-2">
            {question.options?.map((option, index) => (
              <div key={index} className="flex items-center space-x-2">
                <Checkbox
                  id={`${question.id}-${index}`}
                  checked={checkboxValues.includes(option)}
                  onCheckedChange={(checked) => {
                    if (checked) {
                      handleResponseChange(question.id, [...checkboxValues, option])
                    } else {
                      handleResponseChange(question.id, checkboxValues.filter((v: string) => v !== option))
                    }
                  }}
                />
                <Label htmlFor={`${question.id}-${index}`}>{option}</Label>
              </div>
            ))}
          </div>
        )
      }

      default:
        return <div>Tipo de pergunta não suportado</div>
    }
  }

  const completedQuestions = session.questions.filter(q =>
    responses[q.id] !== undefined && responses[q.id] !== '' && responses[q.id] !== null
  ).length

  const progressPercentage = (completedQuestions / session.questions.length) * 100

  return (
    <div className="space-y-6">
      {/* Header */}
      <Card>
        <CardHeader>
          <CardTitle>{session.template_name || 'Questionário'}</CardTitle>
          <CardDescription>
            Responda todas as perguntas para completar o questionário
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span>Progresso</span>
              <span>{completedQuestions} de {session.questions.length} perguntas</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                style={{ width: `${progressPercentage}%` }}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Questions */}
      <div className="space-y-6">
        {session.questions.map((question, index) => {
          const isAnswered = responses[question.id] !== undefined &&
            responses[question.id] !== '' &&
            responses[question.id] !== null

          return (
            <Card key={question.id} className={isAnswered ? 'border-green-200 bg-green-50' : ''}>
              <CardHeader>
                <div className="flex items-start space-x-3">
                  <div className="flex items-center justify-center w-8 h-8 rounded-full bg-blue-100 text-blue-600 font-medium text-sm">
                    {isAnswered ? (
                      <CheckCircle className="w-5 h-5 text-green-600" />
                    ) : (
                      <span>{index + 1}</span>
                    )}
                  </div>
                  <div className="flex-1">
                    <CardTitle className="text-lg">
                      {question.question}
                      {question.required && (
                        <span className="text-red-500 ml-1">*</span>
                      )}
                    </CardTitle>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                {renderQuestion(question)}
              </CardContent>
            </Card>
          )
        })}
      </div>

      {/* Submit Button */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            <div className="text-sm text-gray-600">
              {completedQuestions === session.questions.length ? (
                <span className="text-green-600 font-medium">
                  ✓ Todas as perguntas foram respondidas
                </span>
              ) : (
                <span>
                  {session.questions.length - completedQuestions} perguntas restantes
                </span>
              )}
            </div>

            <Button
              onClick={handleSubmit}
              disabled={submitResponseMutation.isPending}
              size="lg"
            >
              {submitResponseMutation.isPending ? (
                <>
                  <LoadingSpinner size="sm" className="mr-2" />
                  Enviando...
                </>
              ) : (
                <>
                  <CheckCircle className="mr-2 h-4 w-4" />
                  Enviar Questionário
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
