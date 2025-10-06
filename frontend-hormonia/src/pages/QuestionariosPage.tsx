import React, { useState, useMemo, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as z from 'zod'
import { Search, Plus, ListFilter as Filter, MoveHorizontal as MoreHorizontal, FileText, Users, TrendingUp, Clock, Check, X, CircleAlert as AlertCircle, ChevronDown, Eye, CreditCard as Edit, Trash2, ChartBar as BarChart3, Calendar } from 'lucide-react'

import { apiClient } from '@/lib/api-client'
import { useAuth } from '@/contexts/AuthContext'
import { useToast } from '@/components/ui/use-toast'
import { useQuestionarios } from '@/hooks/api/useQuestionarios'

// UI Components
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { LoadingSpinner, LoadingOverlay } from '@/components/ui/loading-spinner'
import { Separator } from '@/components/ui/separator'
import { createLogger } from '@/lib/logger'

const logger = createLogger('QuestionariosPage');

// Types
interface QuizTemplate {
  id: string
  name: string
  version: string
  questions: QuizQuestion[]
  is_active: boolean
  created_at: string
  updated_at: string
}

interface QuizQuestion {
  id: string
  type: 'multiple_choice' | 'open_text' | 'scale' | 'yes_no' | 'date' | 'number'
  text: string
  description?: string
  required: boolean
  options?: QuestionOption[]
  validation_rules?: ValidationRule[]
  metadata?: Record<string, any>
}

interface QuestionOption {
  id: string
  text: string
  value: string | number
  is_correct?: boolean
}

interface ValidationRule {
  type: string
  value: any
  message: string
}

interface QuizAnalytics {
  quiz_template_id: string
  total_responses: number
  completion_rate: number
  average_completion_time?: number
  question_analytics: Array<Record<string, any>>
  trends: Record<string, any>
}

// Form schemas
const questionSchema = z.object({
  id: z.string().min(1, 'ID é obrigatório'),
  type: z.enum(['multiple_choice', 'open_text', 'scale', 'yes_no', 'date', 'number']),
  text: z.string().min(1, 'Texto da pergunta é obrigatório'),
  description: z.string().optional(),
  required: z.boolean().default(true),
  options: z.array(z.object({
    id: z.string(),
    text: z.string(),
    value: z.union([z.string(), z.number()]),
    is_correct: z.boolean().optional()
  })).optional(),
})

const createQuizSchema = z.object({
  name: z.string().min(1, 'Nome é obrigatório').max(255, 'Nome muito longo'),
  version: z.string().min(1, 'Versão é obrigatória').max(50, 'Versão muito longa'),
  questions: z.array(questionSchema).min(1, 'Pelo menos uma pergunta é obrigatória'),
  is_active: z.boolean().default(true)
})

type CreateQuizForm = z.infer<typeof createQuizSchema>

// Filter types
interface Filters {
  search: string
  type: 'all' | 'medical' | 'wellness'
  status: 'all' | 'active' | 'inactive'
  sortBy: 'created_at' | 'name' | 'responses'
  sortOrder: 'asc' | 'desc'
}

export function QuestionariosPage() {
  const { user } = useAuth()
  const { toast } = useToast()
  const queryClient = useQueryClient()

  // State
  const [filters, setFilters] = useState<Filters>({
    search: '',
    type: 'all',
    status: 'all',
    sortBy: 'created_at',
    sortOrder: 'desc'
  })
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false)
  const [currentPage, setCurrentPage] = useState(1)
  const pageSize = 12

  // Queries - Using useQuestionarios hook with server-side filtering
  const {
    data: templatesData,
    isLoading: isLoadingTemplates,
    error: templatesError,
    refetch: refetchTemplates
  } = useQuestionarios({
    search: filters.search,
    type: filters.type,
    status: filters.status,
    sortBy: filters.sortBy,
    sortOrder: filters.sortOrder,
    page: currentPage,
    size: pageSize
  })

  // Create mutation
  const createMutation = useMutation({
    mutationFn: (data: CreateQuizForm) => {
      logger.info('Creating quiz template', { name: data.name, version: data.version });
      return apiClient.quizzes.createTemplate(data);
    },
    onSuccess: () => {
      logger.info('Quiz template created successfully');
      toast({
        title: 'Questionário criado',
        description: 'O questionário foi criado com sucesso.',
      })
      queryClient.invalidateQueries({ queryKey: ['quiz-templates'] })
      setIsCreateDialogOpen(false)
      reset()
    },
    onError: (error: any) => {
      logger.error('Create quiz error', { error });
      toast({
        title: 'Erro ao criar questionário',
        description: error?.data?.message || 'Não foi possível criar o questionário.',
        variant: 'destructive',
      })
    }
  })

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => {
      logger.info('Deleting quiz template', { templateId: id });
      return apiClient.quizzes.deleteTemplate(id);
    },
    onSuccess: () => {
      logger.info('Quiz template deleted successfully');
      toast({
        title: 'Questionário excluído',
        description: 'O questionário foi desativado com sucesso.',
      })
      queryClient.invalidateQueries({ queryKey: ['quiz-templates'] })
    },
    onError: (error: any) => {
      logger.error('Delete quiz error', { error });
      toast({
        title: 'Erro ao excluir questionário',
        description: error?.data?.message || 'Não foi possível excluir o questionário.',
        variant: 'destructive',
      })
    }
  })

  // Form
  const {
    register,
    handleSubmit,
    reset,
    watch,
    setValue,
    formState: { errors, isSubmitting }
  } = useForm<CreateQuizForm>({
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
            { id: 'opt2', text: 'Opção 2', value: 'option2' }
          ]
        }
      ],
      is_active: true
    }
  })

  const questions = watch('questions')

  // Performance logging - Server-side filtering
  useEffect(() => {
    if (process.env['NODE_ENV'] === 'development' && templatesData) {
      logger.info('QuestionariosPage Performance', {
        serverSideFiltering: true,
        totalTemplates: templatesData.total,
        currentPage: templatesData.page,
        loadedCount: templatesData.data.length,
        filters: {
          search: filters.search || 'none',
          type: filters.type,
          status: filters.status,
          sortBy: filters.sortBy,
          sortOrder: filters.sortOrder
        }
      })
    }
  }, [templatesData, filters])

  // Event handlers
  const handleSearch = (value: string) => {
    setFilters(prev => ({ ...prev, search: value }))
    setCurrentPage(1)
  }

  const handleFilterChange = (key: keyof Filters, value: any) => {
    setFilters(prev => ({ ...prev, [key]: value }))
    setCurrentPage(1)
  }

  const onSubmit = (data: CreateQuizForm) => {
    createMutation.mutate(data)
  }

  const handleDeleteTemplate = (id: string) => {
    if (window.confirm('Tem certeza que deseja desativar este questionário?')) {
      deleteMutation.mutate(id)
    }
  }

  const addQuestion = () => {
    const newQuestion = {
      id: `q${questions.length + 1}`,
      type: 'multiple_choice' as const,
      text: '',
      description: '',
      required: true,
      options: [
        { id: 'opt1', text: 'Opção 1', value: 'option1' },
        { id: 'opt2', text: 'Opção 2', value: 'option2' }
      ]
    }
    const updatedQuestions = [...questions, newQuestion]
    setValue('questions', updatedQuestions)
  }

  const removeQuestion = (index: number) => {
    setValue('questions', questions.filter((_, i) => i !== index))
  }

  const updateQuestion = (index: number, field: string, value: any) => {
    const updatedQuestions = [...questions]
    const currentQuestion = updatedQuestions[index]
    if (!currentQuestion) return

    updatedQuestions[index] = {
      id: currentQuestion.id,
      type: currentQuestion.type,
      text: currentQuestion.text,
      required: currentQuestion.required,
      description: currentQuestion.description,
      options: currentQuestion.options,
      [field]: value
    }
    setValue('questions', updatedQuestions)
  }

  // Get summary statistics from server data
  const totalTemplates = templatesData?.total || 0
  const activeTemplates = (templatesData?.data || []).filter((t: any) => t.is_active).length
  const totalResponses = (templatesData?.data || []).reduce((sum: number, t: any) => sum + (t.analytics?.total_responses || 0), 0)
  const averageCompletionRate = templatesData?.data && templatesData.data.length > 0 ?
    templatesData.data.reduce((sum: number, t: any) => sum + (t.analytics?.completion_rate || 0), 0) / templatesData.data.length : 0

  return (
    <div className="container mx-auto py-4 sm:py-6 lg:py-8 px-3 sm:px-4 lg:px-6 max-w-7xl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 sm:gap-4 mb-6 sm:mb-8">
        <div className="flex-1">
          <h1 className="text-2xl sm:text-3xl font-bold">Questionários</h1>
          <p className="text-sm sm:text-base text-muted-foreground mt-1">
            Gerencie questionários médicos e de bem-estar para seus pacientes
          </p>
        </div>
        <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
          <DialogTrigger asChild>
            <Button className="w-full sm:w-auto">
              <Plus className="h-4 w-4 mr-2" />
              <span className="hidden sm:inline">Novo Questionário</span>
              <span className="sm:hidden">Novo</span>
            </Button>
          </DialogTrigger>
        </Dialog>
      </div>

      {/* Summary Statistics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mb-6 sm:mb-8">
        <Card>
          <CardContent className="p-4 sm:p-6">
            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-2 sm:gap-0">
              <FileText className="h-6 w-6 sm:h-8 sm:w-8 text-blue-500" />
              <div className="sm:ml-4">
                <p className="text-xl sm:text-2xl font-bold">{totalTemplates}</p>
                <p className="text-xs text-muted-foreground">Total de Questionários</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 sm:p-6">
            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-2 sm:gap-0">
              <Check className="h-6 w-6 sm:h-8 sm:w-8 text-green-500" />
              <div className="sm:ml-4">
                <p className="text-xl sm:text-2xl font-bold">{activeTemplates}</p>
                <p className="text-xs text-muted-foreground">Ativos</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 sm:p-6">
            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-2 sm:gap-0">
              <Users className="h-6 w-6 sm:h-8 sm:w-8 text-purple-500" />
              <div className="sm:ml-4">
                <p className="text-xl sm:text-2xl font-bold">{totalResponses}</p>
                <p className="text-xs text-muted-foreground">Total de Respostas</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 sm:p-6">
            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-2 sm:gap-0">
              <TrendingUp className="h-6 w-6 sm:h-8 sm:w-8 text-orange-500" />
              <div className="sm:ml-4">
                <p className="text-xl sm:text-2xl font-bold">{averageCompletionRate.toFixed(1)}%</p>
                <p className="text-xs text-muted-foreground">Taxa de Conclusão</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters and Search */}
      <Card className="mb-6">
        <CardContent className="p-4 sm:p-6">
          <div className="flex flex-col gap-3 sm:gap-4">
            {/* Search */}
            <div className="w-full">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Buscar questionários..."
                  value={filters.search}
                  onChange={(e) => handleSearch(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>

            {/* Filters */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <Select
                value={filters.type}
                onValueChange={(value) => handleFilterChange('type', value)}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Tipo" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todos os tipos</SelectItem>
                  <SelectItem value="medical">Médico</SelectItem>
                  <SelectItem value="wellness">Bem-estar</SelectItem>
                </SelectContent>
              </Select>

              <Select
                value={filters.status}
                onValueChange={(value) => handleFilterChange('status', value)}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todos</SelectItem>
                  <SelectItem value="active">Ativos</SelectItem>
                  <SelectItem value="inactive">Inativos</SelectItem>
                </SelectContent>
              </Select>

              <Select
                value={`${filters.sortBy}-${filters.sortOrder}`}
                onValueChange={(value) => {
                  const [sortBy, sortOrder] = value.split('-')
                  handleFilterChange('sortBy', sortBy)
                  handleFilterChange('sortOrder', sortOrder)
                }}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Ordenar por" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="created_at-desc">Mais recentes</SelectItem>
                  <SelectItem value="created_at-asc">Mais antigos</SelectItem>
                  <SelectItem value="name-asc">Nome A-Z</SelectItem>
                  <SelectItem value="name-desc">Nome Z-A</SelectItem>
                  <SelectItem value="responses-desc">Mais respostas</SelectItem>
                  <SelectItem value="responses-asc">Menos respostas</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Content */}
      <LoadingOverlay isLoading={isLoadingTemplates}>
        {templatesError ? (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              Erro ao carregar questionários: {(templatesError as any)?.message || 'Erro desconhecido'}
              <Button
                variant="outline"
                size="sm"
                onClick={() => refetchTemplates()}
                className="ml-2"
              >
                Tentar novamente
              </Button>
            </AlertDescription>
          </Alert>
        ) : !templatesData?.data || templatesData.data.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center">
              <FileText className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
              <h3 className="text-lg font-semibold mb-2">
                {filters.search || filters.type !== 'all' || filters.status !== 'all'
                  ? 'Nenhum questionário encontrado'
                  : 'Nenhum questionário criado ainda'
                }
              </h3>
              <p className="text-muted-foreground mb-6">
                {filters.search || filters.type !== 'all' || filters.status !== 'all'
                  ? 'Tente ajustar os filtros de busca.'
                  : 'Crie seu primeiro questionário para começar a coletar respostas dos pacientes.'
                }
              </p>
              {(!filters.search && filters.type === 'all' && filters.status === 'all') && (
                <Button onClick={() => setIsCreateDialogOpen(true)}>
                  <Plus className="h-4 w-4 mr-2" />
                  Criar Primeiro Questionário
                </Button>
              )}
            </CardContent>
          </Card>
        ) : (
          <>
            {/* Templates Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 sm:gap-6">
              {templatesData.data.map((template: any) => (
                <QuestionnaireCard
                  key={template.id}
                  template={template}
                  onDelete={handleDeleteTemplate}
                />
              ))}
            </div>

            {/* Pagination */}
            {templatesData && templatesData.total > pageSize && (
              <div className="flex justify-center mt-6 sm:mt-8">
                <div className="flex flex-col sm:flex-row items-center gap-2 sm:gap-0 sm:space-x-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                    disabled={currentPage === 1}
                    className="w-full sm:w-auto"
                  >
                    Anterior
                  </Button>
                  <span className="text-sm text-muted-foreground whitespace-nowrap px-2">
                    Página {currentPage} de {Math.ceil(templatesData.total / pageSize)}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPage(prev => prev + 1)}
                    disabled={currentPage >= Math.ceil(templatesData.total / pageSize)}
                    className="w-full sm:w-auto"
                  >
                    Próxima
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </LoadingOverlay>

      {/* Create Dialog */}
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
              {errors.name && (
                <p className="text-sm text-destructive">{errors.name.message}</p>
              )}
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
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Label>Perguntas</Label>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={addQuestion}
                disabled={isSubmitting}
              >
                <Plus className="h-4 w-4 mr-2" />
                Adicionar Pergunta
              </Button>
            </div>

            {questions.map((question, index) => (
              <Card key={index}>
                <CardHeader className="pb-3 px-4 sm:px-6">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-sm sm:text-base">Pergunta {index + 1}</CardTitle>
                    {questions.length > 1 && (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => removeQuestion(index)}
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
                      onChange={(e) => updateQuestion(index, 'text', e.target.value)}
                      placeholder="Digite sua pergunta aqui..."
                      disabled={isSubmitting}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label>Descrição (opcional)</Label>
                    <Textarea
                      value={question.description || ''}
                      onChange={(e) => updateQuestion(index, 'description', e.target.value)}
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
                        onValueChange={(value) => updateQuestion(index, 'type', value)}
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
                        onChange={(e) => updateQuestion(index, 'required', e.target.checked)}
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
                              updatedOptions[optionIndex] = { ...option, text: e.target.value, value: e.target.value.toLowerCase() }
                              updateQuestion(index, 'options', updatedOptions)
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
                                const updatedOptions = question.options?.filter((_, i) => i !== optionIndex) || []
                                updateQuestion(index, 'options', updatedOptions)
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
                          const updatedOptions = [...(question.options || []), {
                            id: `opt${(question.options?.length || 0) + 1}`,
                            text: '',
                            value: ''
                          }]
                          updateQuestion(index, 'options', updatedOptions)
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

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setIsCreateDialogOpen(false)}
              disabled={isSubmitting}
            >
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
    </div>
  )
}

// Questionnaire Card Component
interface QuestionnaireCardProps {
  template: any
  onDelete: (id: string) => void
}

function QuestionnaireCard({ template, onDelete }: QuestionnaireCardProps) {
  const analytics = template.analytics || {}

  const getStatusColor = (isActive: boolean) => {
    return isActive ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
  }

  const getTypeFromName = (name: string) => {
    const lowerName = name.toLowerCase()
    if (lowerName.includes('medical') || lowerName.includes('oncolog') || lowerName.includes('sintoma')) {
      return { label: 'Médico', color: 'bg-blue-100 text-blue-800' }
    }
    return { label: 'Bem-estar', color: 'bg-purple-100 text-purple-800' }
  }

  const typeInfo = getTypeFromName(template.name)

  return (
    <Card className="hover:shadow-md transition-shadow duration-200 flex flex-col h-full">
      <CardHeader className="pb-3 px-4 sm:px-6">
        <div className="flex items-start justify-between gap-2">
          <div className="space-y-2 flex-1 min-w-0">
            <CardTitle className="text-base sm:text-lg leading-tight break-words">{template.name}</CardTitle>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="secondary" className={getStatusColor(template.is_active)}>
                {template.is_active ? 'Ativo' : 'Inativo'}
              </Badge>
              <Badge variant="outline" className={typeInfo.color}>
                {typeInfo.label}
              </Badge>
            </div>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>Ações</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem>
                <Eye className="h-4 w-4 mr-2" />
                Visualizar
              </DropdownMenuItem>
              <DropdownMenuItem>
                <Edit className="h-4 w-4 mr-2" />
                Editar
              </DropdownMenuItem>
              <DropdownMenuItem>
                <BarChart3 className="h-4 w-4 mr-2" />
                Relatórios
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                className="text-destructive"
                onClick={() => onDelete(template.id)}
              >
                <Trash2 className="h-4 w-4 mr-2" />
                Desativar
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </CardHeader>

      <CardContent className="space-y-3 sm:space-y-4 px-4 sm:px-6 flex-1">
        <div className="text-sm text-muted-foreground space-y-1">
          <p>{template.questions?.length || 0} pergunta(s)</p>
          <p>Versão {template.version}</p>
        </div>

        <Separator />

        {/* Statistics */}
        <div className="grid grid-cols-2 gap-3 sm:gap-4 text-sm">
          <div className="space-y-1">
            <div className="flex items-center gap-1">
              <Users className="h-4 w-4 text-muted-foreground flex-shrink-0" />
              <span className="font-medium">{analytics.total_responses || 0}</span>
            </div>
            <p className="text-xs text-muted-foreground">Respostas</p>
          </div>
          <div className="space-y-1">
            <div className="flex items-center gap-1">
              <TrendingUp className="h-4 w-4 text-muted-foreground flex-shrink-0" />
              <span className="font-medium">{(analytics.completion_rate || 0).toFixed(1)}%</span>
            </div>
            <p className="text-xs text-muted-foreground">Taxa de Conclusão</p>
          </div>
        </div>

        {analytics.average_completion_time && (
          <div className="text-sm">
            <div className="flex items-center gap-1">
              <Clock className="h-4 w-4 text-muted-foreground flex-shrink-0" />
              <span className="font-medium">{Math.round(analytics.average_completion_time)} min</span>
            </div>
            <p className="text-xs text-muted-foreground mt-1">Tempo Médio</p>
          </div>
        )}
      </CardContent>

      <CardFooter className="pt-0 px-4 sm:px-6 pb-4 sm:pb-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between w-full gap-2 sm:gap-0 text-xs text-muted-foreground">
          <div className="flex items-center gap-1">
            <Calendar className="h-3 w-3 flex-shrink-0" />
            <span>{new Date(template.created_at).toLocaleDateString('pt-BR')}</span>
          </div>
          <span className="sm:text-right">v{template.version}</span>
        </div>
      </CardFooter>
    </Card>
  )
}