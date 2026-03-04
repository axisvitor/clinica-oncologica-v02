import React from 'react'
import { Plus, X, Trash2 } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

import { QuizQuestion } from '@/types/api'

/**
 * Props for QuestionForm component
 */
interface QuestionFormProps {
  /** Array of questions */
  questions: QuizQuestion[]
  /** Handler to update a question field */
  onUpdateQuestion: (index: number, field: string, value: unknown) => void
  /** Handler to remove a question */
  onRemoveQuestion: (index: number) => void
  /** Handler to add a new question */
  onAddQuestion: () => void
  /** Whether the form is submitting */
  isSubmitting?: boolean
}

/**
 * Shared component for editing quiz questions
 * Used by both CreateQuestionarioModal and EditQuestionarioModal
 *
 * @component
 * @example
 * ```tsx
 * <QuestionForm
 *   questions={questions}
 *   onUpdateQuestion={updateQuestion}
 *   onRemoveQuestion={removeQuestion}
 *   onAddQuestion={addQuestion}
 *   isSubmitting={false}
 * />
 * ```
 */
export const QuestionForm = React.memo<QuestionFormProps>(
  ({ questions, onUpdateQuestion, onRemoveQuestion, onAddQuestion, isSubmitting = false }) => {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <Label className="text-base font-semibold">Perguntas</Label>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onAddQuestion}
            disabled={isSubmitting}
          >
            <Plus className="h-4 w-4 mr-2" />
            Adicionar Pergunta
          </Button>
        </div>

        {questions.map((question, index) => (
          <Card key={question.id}>
            <CardHeader className="pb-3 px-4 sm:px-6">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm sm:text-base">Pergunta {index + 1}</CardTitle>
                {questions.length > 1 && (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => onRemoveQuestion(index)}
                    disabled={isSubmitting}
                  >
                    <Trash2 className="h-3 w-3 sm:h-4 sm:w-4" />
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent className="space-y-3 sm:space-y-4 px-4 sm:px-6">
              <div className="space-y-2">
                <Label>Texto da Pergunta</Label>
                <Textarea
                  value={question.text}
                  onChange={(e) => onUpdateQuestion(index, 'text', e.target.value)}
                  placeholder="Digite sua pergunta aqui..."
                  disabled={isSubmitting}
                />
              </div>

              <div className="space-y-2">
                <Label>Descrição (opcional)</Label>
                <Textarea
                  value={question.description || ''}
                  onChange={(e) => onUpdateQuestion(index, 'description', e.target.value)}
                  placeholder="Instruções adicionais para a pergunta..."
                  rows={2}
                  disabled={isSubmitting}
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
                <div className="space-y-2">
                  <Label>Tipo de Pergunta</Label>
                  <Select
                    value={question.type}
                    onValueChange={(value) => onUpdateQuestion(index, 'type', value)}
                    disabled={isSubmitting}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="multiple_choice">Múltipla escolha</SelectItem>
                      <SelectItem value="open_text">Texto livre</SelectItem>
                      <SelectItem value="scale">Escala (1-10)</SelectItem>
                      <SelectItem value="yes_no">Sim/Não</SelectItem>
                      <SelectItem value="date">Data</SelectItem>
                      <SelectItem value="number">Número</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="flex items-center space-x-2 pt-8">
                  <input
                    type="checkbox"
                    id={`required-${index}`}
                    checked={question.required}
                    onChange={(e) => onUpdateQuestion(index, 'required', e.target.checked)}
                    disabled={isSubmitting}
                  />
                  <Label htmlFor={`required-${index}`}>Pergunta obrigatória</Label>
                </div>
              </div>

              {question.type === 'multiple_choice' && question.options && (
                <div className="space-y-2">
                  <Label>Opções</Label>
                  {question.options.map((option, optionIndex) => (
                    <div key={optionIndex} className="flex items-center space-x-2">
                      <Input
                        value={option.text}
                        onChange={(e) => {
                          const updatedOptions = [...(question.options || [])]
                          updatedOptions[optionIndex] = {
                            ...option,
                            text: e.target.value,
                            value: e.target.value.toLowerCase(),
                          }
                          onUpdateQuestion(index, 'options', updatedOptions)
                        }}
                        placeholder={`Opção ${optionIndex + 1}`}
                        disabled={isSubmitting}
                      />
                      {question.options && question.options.length > 2 && (
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            const updatedOptions =
                              question.options?.filter((_, i) => i !== optionIndex) || []
                            onUpdateQuestion(index, 'options', updatedOptions)
                          }}
                          disabled={isSubmitting}
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  ))}
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      const updatedOptions = [
                        ...(question.options || []),
                        {
                          id: `opt${(question.options?.length || 0) + 1}`,
                          text: '',
                          value: '',
                        },
                      ]
                      onUpdateQuestion(index, 'options', updatedOptions)
                    }}
                    disabled={isSubmitting}
                  >
                    <Plus className="h-4 w-4 mr-2" />
                    Adicionar Opção
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    )
  }
)

QuestionForm.displayName = 'QuestionForm'
