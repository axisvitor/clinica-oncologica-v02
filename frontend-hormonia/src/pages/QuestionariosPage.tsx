import React, { useState, useEffect, useCallback, useMemo } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as z from 'zod'

import { apiClient } from '@/lib/api-client'
import { useToast } from '@/components/ui/use-toast'
import { useQuestionarios } from '@/hooks/api/useQuestionarios'
import { createLogger } from '@/lib/logger'

// Import extracted components
import { QuestionariosHeader } from '@/features/questionarios/QuestionariosHeader'
import { QuestionariosStats } from '@/features/questionarios/QuestionariosStats'
import { QuestionariosFilters } from '@/features/questionarios/QuestionariosFilters'
import type { QuestionariosFiltersConfig } from '@/features/questionarios/QuestionariosFilters'
import { QuestionariosGrid } from '@/features/questionarios/QuestionariosGrid'
import { CreateQuestionarioModal } from '@/features/questionarios/CreateQuestionarioModal'
import type { CreateQuizFormData } from '@/features/questionarios/CreateQuestionarioModal'
import { EditQuestionarioModal } from '@/features/questionarios/EditQuestionarioModal'
import type { QuizTemplate, QuizQuestion } from '@/types/api'

const logger = createLogger('QuestionariosPage')

type QuizTemplatePayload = Parameters<typeof apiClient.quizzes.createTemplate>[0] & {
  version?: string
  is_active?: boolean
}

type QuizTemplateUpdatePayload = Parameters<typeof apiClient.quizzes.updateTemplate>[1] & {
  version?: string
  is_active?: boolean
}

/**
 * Form schemas for question and quiz validation
 */
const questionSchema = z.object({
  id: z.string().min(1, 'ID é obrigatório'),
  type: z.enum(['multiple_choice', 'open_text', 'scale', 'yes_no', 'date', 'number']),
  text: z.string().min(1, 'Texto da pergunta é obrigatório'),
  description: z.string().optional(),
  required: z.boolean().default(true),
  options: z
    .array(
      z.object({
        id: z.string(),
        text: z.string(),
        value: z.union([z.string(), z.number()]),
        is_correct: z.boolean().optional(),
      })
    )
    .optional(),
})

const createQuizSchema = z.object({
  name: z.string().min(1, 'Nome é obrigatório').max(255, 'Nome muito longo'),
  version: z.string().min(1, 'Versão é obrigatória').max(50, 'Versão muito longa'),
  questions: z.array(questionSchema).min(1, 'Pelo menos uma pergunta é obrigatória'),
  is_active: z.boolean().default(true),
})

/**
 * Questionarios Page Component
 *
 * Main page component for managing questionnaires.
 * Refactored from 1,039 lines to ~250 lines by extracting components.
 *
 * @component
 */
export function QuestionariosPage() {
  const { toast } = useToast()
  const queryClient = useQueryClient()

  // State management
  const [filters, setFilters] = useState<QuestionariosFiltersConfig>({
    search: '',
    type: 'all',
    status: 'all',
    sortBy: 'created_at',
    sortOrder: 'desc',
  })
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false)
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false)
  const [editingTemplate, setEditingTemplate] = useState<QuizTemplate | null>(null)
  const [currentPage, setCurrentPage] = useState(1)
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)
  const pageSize = 12

  // Data fetching with server-side filtering
  const {
    data: templatesData,
    isLoading: isLoadingTemplates,
    error: templatesError,
    refetch: refetchTemplates,
  } = useQuestionarios({
    search: filters.search,
    type: filters.type,
    status: filters.status,
    sortBy: filters.sortBy,
    sortOrder: filters.sortOrder,
    page: currentPage,
    size: pageSize,
  })

  // React Hook Form setup
  const form = useForm<CreateQuizFormData>({
    resolver: zodResolver(createQuizSchema),
    defaultValues: {
      name: '',
      version: '1.0',
      questions: [
        {
          id: 'q1',
          type: 'multiple_choice',
          text: '',
          description: '',
          required: true,
          options: [
            { id: 'opt1', text: 'Opção 1', value: 'option1' },
            { id: 'opt2', text: 'Opção 2', value: 'option2' },
          ],
        },
      ],
      is_active: true,
    },
  })

  const {
    reset,
    watch,
    setValue,
    formState: { isSubmitting = false },
  } = form

  const questions = watch('questions')
  const templatesPayload = useMemo(
    () => templatesData as { items: QuizTemplate[]; total: number; page: number } | undefined,
    [templatesData]
  )

  const { totalTemplates, activeTemplates, totalResponses, averageCompletionRate } = useMemo(() => {
    const items = (templatesData?.items ?? []) as Array<
      QuizTemplate & {
        analytics?: { total_responses?: number; completion_rate?: number }
      }
    >
    let activeCount = 0
    let responsesTotal = 0
    let completionSum = 0

    for (const template of items) {
      if (template.is_active) {
        activeCount += 1
      }
      responsesTotal += template.analytics?.total_responses ?? 0
      completionSum += template.analytics?.completion_rate ?? 0
    }

    return {
      totalTemplates: templatesData?.total ?? 0,
      activeTemplates: activeCount,
      totalResponses: responsesTotal,
      averageCompletionRate: items.length > 0 ? completionSum / items.length : 0,
    }
  }, [templatesData])

  // Mutations
  const createMutation = useMutation({
    mutationFn: (data: CreateQuizFormData) => {
      logger.info('Creating quiz template', { name: data.name, version: data.version })
      const payload: QuizTemplatePayload = {
        ...data,
        questions: data.questions.map((q) => ({
          question_text: q.text,
          question_type: q.type,
          options: q.options?.map((o) => o.text),
          required: q.required,
        })),
      }
      return apiClient.quizzes.createTemplate(payload)
    },
    onSuccess: () => {
      logger.info('Quiz template created successfully')
      toast({
        title: 'Questionário criado',
        description: 'O questionário foi criado com sucesso.',
      })
      queryClient.invalidateQueries({ queryKey: ['quiz-templates'] })
      setIsCreateDialogOpen(false)
      reset()
    },
    onError: (error: unknown) => {
      logger.error('Create quiz error', { error })
      toast({
        title: 'Erro ao criar questionário',
        description:
          (error as { data?: { message?: string } })?.data?.message ||
          'Não foi possível criar o questionário.',
        variant: 'destructive',
      })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => {
      logger.info('Deleting quiz template', { templateId: id })
      return apiClient.quizzes.deleteTemplate(id)
    },
    onSuccess: () => {
      logger.info('Quiz template deleted successfully')
      toast({
        title: 'Questionário excluído',
        description: 'O questionário foi desativado com sucesso.',
      })
      queryClient.invalidateQueries({ queryKey: ['quiz-templates'] })
    },
    onError: (error: unknown) => {
      logger.error('Delete quiz error', { error })
      toast({
        title: 'Erro ao excluir questionário',
        description:
          (error as { data?: { message?: string } })?.data?.message ||
          'Não foi possível excluir o questionário.',
        variant: 'destructive',
      })
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: CreateQuizFormData }) => {
      logger.info('Updating quiz template', { templateId: id, name: data.name })
      const payload: QuizTemplateUpdatePayload = {
        ...data,
        questions: data.questions.map((q) => ({
          question_text: q.text,
          question_type: q.type,
          options: q.options?.map((o) => o.text),
          required: q.required,
        })),
      }
      return apiClient.quizzes.updateTemplate(id, payload)
    },
    onSuccess: () => {
      logger.info('Quiz template updated successfully')
      toast({
        title: 'Questionário atualizado',
        description: 'O questionário foi atualizado com sucesso.',
      })
      queryClient.invalidateQueries({ queryKey: ['quiz-templates'] })
      setIsEditDialogOpen(false)
      setEditingTemplate(null)
      reset()
    },
    onError: (error: unknown) => {
      logger.error('Update quiz error', { error })
      toast({
        title: 'Erro ao atualizar questionário',
        description:
          (error as { data?: { message?: string } })?.data?.message ||
          'Não foi possível atualizar o questionário.',
        variant: 'destructive',
      })
    },
  })

  // Performance logging
  useEffect(() => {
    if (process.env['NODE_ENV'] === 'development' && templatesData) {
      logger.info('QuestionariosPage Performance', {
        serverSideFiltering: true,
        totalTemplates: templatesData.total,
        currentPage: templatesData.page,
        loadedCount: templatesData.items.length,
        filters: {
          search: filters.search || 'none',
          type: filters.type,
          status: filters.status,
          sortBy: filters.sortBy,
          sortOrder: filters.sortOrder,
        },
      })
    }
  }, [templatesData, filters])

  // Event handlers
  const handleSearch = useCallback(
    (value: string) => {
      setFilters((prev: QuestionariosFiltersConfig) => ({ ...prev, search: value }))
      setCurrentPage(1)
    },
    [setFilters, setCurrentPage]
  )

  const handleFilterChange = useCallback(
    <K extends keyof QuestionariosFiltersConfig>(key: K, value: QuestionariosFiltersConfig[K]) => {
      setFilters((prev: QuestionariosFiltersConfig) => ({ ...prev, [key]: value }))
      setCurrentPage(1)
    },
    [setFilters, setCurrentPage]
  )

  const onSubmit = useCallback(
    (data: CreateQuizFormData) => {
      if (editingTemplate) {
        updateMutation.mutate({ id: editingTemplate.id, data })
      } else {
        createMutation.mutate(data)
      }
    },
    [createMutation, editingTemplate, updateMutation]
  )

  const handleDeleteTemplate = useCallback(
    (id: string) => {
      if (confirmDeleteId === id) {
        setConfirmDeleteId(null)
        deleteMutation.mutate(id)
        return
      }
      setConfirmDeleteId(id)
      toast({
        title: 'Confirme a desativação',
        description: 'Clique novamente para desativar este questionário.',
        variant: 'destructive',
      })
      setTimeout(() => {
        setConfirmDeleteId((prev) => (prev === id ? null : prev))
      }, 3000)
    },
    [confirmDeleteId, deleteMutation, toast]
  )

  const handleEditTemplate = useCallback(
    (template: QuizTemplate) => {
      setEditingTemplate(template)
      setValue('name', template.name)
      setValue('version', template.version)
      setValue('questions', template.questions)
      setValue('is_active', template.is_active)
      setIsEditDialogOpen(true)
    },
    [setValue]
  )

  const handleCloseEditDialog = useCallback(() => {
    setIsEditDialogOpen(false)
    setEditingTemplate(null)
    reset()
  }, [reset])

  const addQuestion = useCallback(() => {
    const newQuestion: QuizQuestion = {
      id: `q${questions.length + 1}`,
      type: 'multiple_choice',
      text: '',
      description: '',
      required: true,
      options: [
        { id: 'opt1', text: 'Opção 1', value: 'option1' },
        { id: 'opt2', text: 'Opção 2', value: 'option2' },
      ],
    }
    setValue('questions', [...questions, newQuestion])
  }, [questions, setValue])

  const removeQuestion = useCallback(
    (index: number) => {
      setValue(
        'questions',
        questions.filter((_: unknown, i: number) => i !== index)
      )
    },
    [questions, setValue]
  )

  const updateQuestion = useCallback(
    (index: number, field: string, value: unknown) => {
      const updatedQuestions = [...questions]
      const currentQuestion = updatedQuestions[index]
      if (!currentQuestion) return

      updatedQuestions[index] = {
        ...currentQuestion,
        [field]: value,
      }
      setValue('questions', updatedQuestions)
    },
    [questions, setValue]
  )

  return (
    <div className="container mx-auto py-4 sm:py-6 lg:py-8 px-3 sm:px-4 lg:px-6 max-w-7xl">
      {/* Header */}
      <QuestionariosHeader
        isCreateDialogOpen={isCreateDialogOpen}
        onCreateDialogChange={setIsCreateDialogOpen}
      />

      {/* Summary Statistics */}
      <QuestionariosStats
        totalTemplates={totalTemplates}
        activeTemplates={activeTemplates}
        totalResponses={totalResponses}
        averageCompletionRate={averageCompletionRate}
      />

      {/* Filters and Search */}
      <QuestionariosFilters
        filters={filters}
        onSearchChange={handleSearch}
        onFilterChange={handleFilterChange}
      />

      {/* Templates Grid */}
      <QuestionariosGrid
        templatesData={templatesPayload}
        isLoading={isLoadingTemplates}
        error={templatesError}
        filters={filters}
        pageSize={pageSize}
        currentPage={currentPage}
        onPageChange={setCurrentPage}
        onDelete={handleDeleteTemplate}
        onEdit={handleEditTemplate}
        onCreate={() => setIsCreateDialogOpen(true)}
        onRetry={refetchTemplates}
      />

      {/* Create Dialog */}
      {isCreateDialogOpen && (
        <CreateQuestionarioModal
          form={form}
          onSubmit={onSubmit}
          onClose={() => setIsCreateDialogOpen(false)}
          isSubmitting={isSubmitting}
          questions={questions}
          onAddQuestion={addQuestion}
          onRemoveQuestion={removeQuestion}
          onUpdateQuestion={updateQuestion}
        />
      )}

      {/* Edit Dialog */}
      <EditQuestionarioModal
        isOpen={isEditDialogOpen}
        onOpenChange={handleCloseEditDialog}
        form={form}
        onSubmit={onSubmit}
        onClose={handleCloseEditDialog}
        isSubmitting={isSubmitting}
        isPending={updateMutation.isPending}
        questions={questions}
        onAddQuestion={addQuestion}
        onRemoveQuestion={removeQuestion}
        onUpdateQuestion={updateQuestion}
      />
    </div>
  )
}
