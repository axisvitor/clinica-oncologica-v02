import React from 'react'
import { UseFormReturn } from 'react-hook-form'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { LoadingSpinner } from '@/components/ui/loading-spinner'
import { QuestionForm } from './QuestionForm'
import { QuizQuestion } from '@/types/api'
import { CreateQuizFormData } from './CreateQuestionarioModal'

/**
 * Props for EditQuestionarioModal component
 */
interface EditQuestionarioModalProps {
  /** Whether the edit dialog is open */
  isOpen: boolean
  /** Handler for dialog state changes */
  onOpenChange: (open: boolean) => void
  /** React Hook Form instance */
  form: UseFormReturn<CreateQuizFormData>
  /** Handler for form submission */
  onSubmit: (data: CreateQuizFormData) => void
  /** Handler for closing modal */
  onClose: () => void
  /** Whether the form is submitting */
  isSubmitting: boolean
  /** Whether the mutation is pending */
  isPending: boolean
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
 * Modal component for editing an existing questionnaire
 *
 * @component
 * @example
 * ```tsx
 * <EditQuestionarioModal
 *   isOpen={true}
 *   onOpenChange={setIsOpen}
 *   form={form}
 *   onSubmit={handleSubmit}
 *   onClose={handleClose}
 *   isSubmitting={false}
 *   isPending={false}
 *   questions={questions}
 *   onAddQuestion={addQuestion}
 *   onRemoveQuestion={removeQuestion}
 *   onUpdateQuestion={updateQuestion}
 * />
 * ```
 */
export const EditQuestionarioModal = React.memo<EditQuestionarioModalProps>(({
  isOpen,
  onOpenChange,
  form,
  onSubmit,
  onClose,
  isSubmitting,
  isPending,
  questions,
  onAddQuestion,
  onRemoveQuestion,
  onUpdateQuestion
}) => {
  const { register, handleSubmit, formState: { errors } } = form

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-[95vw] sm:max-w-4xl max-h-[85vh] sm:max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Editar Questionário</DialogTitle>
          <DialogDescription>
            Edite o questionário selecionado
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 sm:space-y-6">
          {/* Basic Info */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
            <div className="space-y-2">
              <Label htmlFor="edit-name">Nome do Questionário</Label>
              <Input
                id="edit-name"
                {...register('name')}
                placeholder="Ex: Avaliação de Sintomas"
                disabled={isSubmitting}
              />
              {errors.name && (
                <p className="text-sm text-destructive">{errors.name.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="edit-version">Versão</Label>
              <Input
                id="edit-version"
                {...register('version')}
                placeholder="Ex: 1.0"
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
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              disabled={isSubmitting || isPending}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={isSubmitting || isPending}>
              {isSubmitting || isPending ? (
                <>
                  <LoadingSpinner size="sm" className="mr-2" />
                  Atualizando...
                </>
              ) : (
                'Atualizar Questionário'
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
})

EditQuestionarioModal.displayName = 'EditQuestionarioModal'
