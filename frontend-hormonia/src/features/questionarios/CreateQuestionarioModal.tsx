import React from 'react'
import { UseFormReturn } from 'react-hook-form'
import {
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { LoadingSpinner } from '@/components/ui/loading-spinner'
import { QuestionForm } from './QuestionForm'
import { QuizQuestion } from '@/types/api'

/**
 * Form data interface for creating quiz
 */
export interface CreateQuizFormData {
  name: string
  version: string
  questions: QuizQuestion[]
  is_active: boolean
}

/**
 * Props for CreateQuestionarioModal component
 */
interface CreateQuestionarioModalProps {
  /** React Hook Form instance */
  form: UseFormReturn<CreateQuizFormData>
  /** Handler for form submission */
  onSubmit: (data: CreateQuizFormData) => void
  /** Handler for closing modal */
  onClose: () => void
  /** Whether the form is submitting */
  isSubmitting: boolean
  /** Array of questions */
  questions: QuizQuestion[]
  /** Handler to add a new question */
  onAddQuestion: () => void
  /** Handler to remove a question */
  onRemoveQuestion: (index: number) => void
  /** Handler to update a question field */
  onUpdateQuestion: (index: number, field: string, value: unknown) => void
}

/**
 * Modal component for creating a new questionnaire
 *
 * @component
 * @example
 * ```tsx
 * <CreateQuestionarioModal
 *   form={form}
 *   onSubmit={handleSubmit}
 *   onClose={handleClose}
 *   isSubmitting={false}
 *   questions={questions}
 *   onAddQuestion={addQuestion}
 *   onRemoveQuestion={removeQuestion}
 *   onUpdateQuestion={updateQuestion}
 * />
 * ```
 */
export const CreateQuestionarioModal = React.memo<CreateQuestionarioModalProps>(
  ({
    form,
    onSubmit,
    onClose,
    isSubmitting,
    questions,
    onAddQuestion,
    onRemoveQuestion,
    onUpdateQuestion,
  }) => {
    const {
      register,
      handleSubmit,
      formState: { errors },
    } = form

    return (
      <DialogContent className="max-w-[95vw] sm:max-w-4xl max-h-[85vh] sm:max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Criar Novo Questionário</DialogTitle>
          <DialogDescription>
            Crie um questionário personalizado para seus pacientes
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 sm:space-y-6">
          {/* Basic Info */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
            <div className="space-y-2">
              <Label htmlFor="name">Nome do Questionário</Label>
              <Input
                id="name"
                {...register('name')}
                placeholder="Ex: Avaliação de Sintomas Pós-Quimio"
                disabled={isSubmitting}
              />
              {errors.name && <p className="text-sm text-destructive">{errors.name.message}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="version">Versão</Label>
              <Input
                id="version"
                {...register('version')}
                placeholder="1.0"
                disabled={isSubmitting}
              />
              {errors.version && (
                <p className="text-sm text-destructive">{errors.version.message}</p>
              )}
            </div>
          </div>

          {/* Questions */}
          <QuestionForm
            questions={questions}
            onUpdateQuestion={onUpdateQuestion}
            onRemoveQuestion={onRemoveQuestion}
            onAddQuestion={onAddQuestion}
            isSubmitting={isSubmitting}
          />

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose} disabled={isSubmitting}>
              Cancelar
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? (
                <>
                  <LoadingSpinner size="sm" className="mr-2" />
                  Criando...
                </>
              ) : (
                'Criar Questionário'
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    )
  }
)

CreateQuestionarioModal.displayName = 'CreateQuestionarioModal'
