/**
 * Quiz Editor Dialog Component
 *
 * Modal dialog for editing quiz templates with full question management.
 */

import React, { memo, useState, useEffect } from 'react'
import { Plus, RefreshCw } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import { QuestionEditor } from './QuestionEditor'
import { Card } from '@/components/ui/card'
import {
  useTemplates,
  type QuizTemplate,
  type QuizQuestion,
  type QuizTemplateUpdate,
} from '@/hooks/useTemplates'
import { useToast } from '@/components/ui/use-toast'
import { logger } from '@/lib/logger'

interface QuizEditorDialogProps {
  quiz: QuizTemplate | null
  onClose: () => void
  onSuccess: () => void
}

export const QuizEditorDialog = memo<QuizEditorDialogProps>(({ quiz, onClose, onSuccess }) => {
  const { toast } = useToast()
  const { updateQuizTemplate } = useTemplates()
  const [isSaving, setIsSaving] = useState(false)

  const [formData, setFormData] = useState({
    name: '',
    version: '',
    description: '',
    category: '',
    is_active: true,
    questions: [] as QuizQuestion[],
  })

  // Initialize form when quiz changes
  useEffect(() => {
    if (quiz) {
      setFormData({
        name: quiz.name,
        version: quiz.version,
        description: quiz.description || '',
        category: quiz.category,
        is_active: quiz.is_active,
        questions: quiz.questions || [],
      })
    }
  }, [quiz])

  const handleSave = async () => {
    if (!quiz) return

    setIsSaving(true)
    try {
      const updateData: QuizTemplateUpdate = {
        name: formData.name,
        version: formData.version,
        description: formData.description,
        category: formData.category,
        is_active: formData.is_active,
        questions: formData.questions,
      }

      const updated = await updateQuizTemplate(quiz.id, updateData)
      if (updated) {
        toast({
          title: 'Quiz atualizado',
          description: `"${formData.name}" foi atualizado com sucesso.`,
        })
        onSuccess()
      }
    } catch (error) {
      logger.error('Failed to update quiz', error)
      toast({
        title: 'Erro ao atualizar',
        description: 'Não foi possível salvar as alterações.',
        variant: 'destructive',
      })
    } finally {
      setIsSaving(false)
    }
  }

  const handleAddQuestion = () => {
    const newQuestion: QuizQuestion = {
      id: `q${Date.now()}`,
      type: 'multiple_choice',
      text: '',
      required: true,
      options: [
        { text: 'Opção 1', value: 'opt1' },
        { text: 'Opção 2', value: 'opt2' },
      ],
    }
    setFormData((prev) => ({
      ...prev,
      questions: [...prev.questions, newQuestion],
    }))
  }

  const handleRemoveQuestion = (index: number) => {
    setFormData((prev) => ({
      ...prev,
      questions: prev.questions.filter((_, i) => i !== index),
    }))
  }

  const handleUpdateQuestion = (index: number, question: QuizQuestion) => {
    setFormData((prev) => {
      const updatedQuestions = [...prev.questions]
      updatedQuestions[index] = question
      return { ...prev, questions: updatedQuestions }
    })
  }

  return (
    <Dialog open={!!quiz} onOpenChange={() => onClose()}>
      <DialogContent className="max-w-[95vw] sm:max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Editar Quiz: {quiz?.name}</DialogTitle>
          <DialogDescription>Modifique as informações e perguntas do quiz</DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* Basic Info */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="quiz-name">Nome do Quiz</Label>
              <Input
                id="quiz-name"
                value={formData.name}
                onChange={(e) => setFormData((prev) => ({ ...prev, name: e.target.value }))}
                placeholder="Nome do questionário"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="quiz-version">Versão</Label>
              <Input
                id="quiz-version"
                value={formData.version}
                onChange={(e) => setFormData((prev) => ({ ...prev, version: e.target.value }))}
                placeholder="1.0"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="quiz-category">Categoria</Label>
              <Input
                id="quiz-category"
                value={formData.category}
                onChange={(e) => setFormData((prev) => ({ ...prev, category: e.target.value }))}
                placeholder="Categoria do quiz"
              />
            </div>
            <div className="flex items-center space-x-2 pt-6">
              <Switch
                id="quiz-active"
                checked={formData.is_active}
                onCheckedChange={(checked) =>
                  setFormData((prev) => ({ ...prev, is_active: checked }))
                }
              />
              <Label htmlFor="quiz-active">Quiz Ativo</Label>
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="quiz-description">Descrição</Label>
            <Textarea
              id="quiz-description"
              value={formData.description}
              onChange={(e) => setFormData((prev) => ({ ...prev, description: e.target.value }))}
              placeholder="Descrição do questionário"
              rows={3}
            />
          </div>

          {/* Questions */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Label className="text-lg font-semibold">
                Perguntas ({formData.questions.length})
              </Label>
              <Button type="button" variant="outline" size="sm" onClick={handleAddQuestion}>
                <Plus className="h-4 w-4 mr-2" />
                Adicionar Pergunta
              </Button>
            </div>

            {formData.questions.map((question, index) => (
              <QuestionEditor
                key={question.id}
                question={question}
                questionNumber={index + 1}
                onUpdate={(q) => handleUpdateQuestion(index, q)}
                onRemove={() => handleRemoveQuestion(index)}
              />
            ))}

            {formData.questions.length === 0 && (
              <Card className="p-8 text-center">
                <p className="text-muted-foreground">
                  Nenhuma pergunta ainda. Clique em "Adicionar Pergunta" para começar.
                </p>
              </Card>
            )}
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isSaving}>
            Cancelar
          </Button>
          <Button onClick={handleSave} disabled={isSaving || !formData.name}>
            {isSaving ? (
              <>
                <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                Salvando...
              </>
            ) : (
              'Salvar Alterações'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
})

QuizEditorDialog.displayName = 'QuizEditorDialog'
