import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Play, Eye, Users, CheckCircle, Send, Clock } from 'lucide-react'
import { apiClient } from '../lib/api-client'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { LoadingSpinner } from '../components/ui/loading-spinner'
import { useToast } from '@/components/ui/use-toast'
import { MonthlyQuizStatus } from '@/components/patients/MonthlyQuizStatus'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

export function QuizPage() {
  const [selectedTemplate, setSelectedTemplate] = useState<string>('')
  const [selectedPatient, setSelectedPatient] = useState<string>('')
  const [showStartDialog, setShowStartDialog] = useState(false)
  const [linkStatusFilter, setLinkStatusFilter] = useState<string>('all')

  const { toast } = useToast()
  const queryClient = useQueryClient()

  const { data: templatesData, isLoading: templatesLoading } = useQuery({
    queryKey: ['quiz-templates'],
    queryFn: () => apiClient.quiz.templates()
  })

  const { data: sessionsData, isLoading: sessionsLoading } = useQuery({
    queryKey: ['quiz-sessions'],
    queryFn: () => apiClient.quiz.sessions({})
  })

  const { data: patientsData } = useQuery({
    queryKey: ['patients', { size: 100 }],
    queryFn: () => apiClient.patients.list({ size: 100 })
  })

  const { data: monthlyQuizStats, isLoading: statsLoading } = useQuery({
    queryKey: ['monthly-quiz-stats'],
    queryFn: () => apiClient.monthlyQuiz.getStats()
  })

  const { data: activeLinks, isLoading: activeLinksLoading } = useQuery({
    queryKey: ['monthly-quiz-active-links'],
    queryFn: () => apiClient.monthlyQuiz.getActiveLinks()
  })

  const startQuizMutation = useMutation({
    mutationFn: ({ patientId, quizTemplateId }: { patientId: string; quizTemplateId: string }) =>
      apiClient.quiz.start(patientId, quizTemplateId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['quiz-sessions'] })
      toast({
        title: 'Questionário iniciado',
        description: 'O questionário foi iniciado com sucesso.',
      })
      setShowStartDialog(false)
      setSelectedTemplate('')
      setSelectedPatient('')
    },
    onError: (error: any) => {
      toast({
        title: 'Erro ao iniciar questionário',
        description: error.data?.message || 'Ocorreu um erro inesperado.',
        variant: 'destructive'
      })
    }
  })

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return <Badge className="bg-green-100 text-green-800">Completado</Badge>
      case 'started':
        return <Badge className="bg-blue-100 text-blue-800">Em andamento</Badge>
      case 'pending':
        return <Badge className="bg-yellow-100 text-yellow-800">Pendente</Badge>
      default:
        return <Badge variant="outline">{status}</Badge>
    }
  }

  const formatDate = (dateString: string) => {
    try {
      return new Date(dateString).toLocaleDateString('pt-BR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      })
    } catch {
      return 'Data inválida'
    }
  }

  const handleStartQuiz = () => {
    if (!selectedPatient || !selectedTemplate) {
      toast({
        title: 'Campos obrigatórios',
        description: 'Selecione um paciente e um template.',
        variant: 'destructive'
      })
      return
    }

    startQuizMutation.mutate({
      patientId: selectedPatient,
      quizTemplateId: selectedTemplate
    })
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Questionários</h1>
          <p className="text-gray-600">
            Gerencie questionários e avaliações dos pacientes
          </p>
        </div>
        <Dialog open={showStartDialog} onOpenChange={setShowStartDialog}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="mr-2 h-4 w-4" />
              Iniciar Questionário
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Iniciar Novo Questionário</DialogTitle>
              <DialogDescription>
                Selecione um paciente e um template para iniciar um questionário
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Paciente</label>
                <Select value={selectedPatient} onValueChange={setSelectedPatient}>
                  <SelectTrigger>
                    <SelectValue placeholder="Selecione um paciente" />
                  </SelectTrigger>
                  <SelectContent>
                    {patientsData?.items?.map((patient: any) => (
                      <SelectItem key={patient.id} value={patient.id}>
                        {patient.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">Template</label>
                <Select value={selectedTemplate} onValueChange={setSelectedTemplate}>
                  <SelectTrigger>
                    <SelectValue placeholder="Selecione um template" />
                  </SelectTrigger>
                  <SelectContent>
                    {templatesData?.items?.map((template: any) => (
                      <SelectItem key={template.id} value={template.id}>
                        {template.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="flex justify-end space-x-2">
                <Button
                  variant="outline"
                  onClick={() => setShowStartDialog(false)}
                >
                  Cancelar
                </Button>
                <Button
                  onClick={handleStartQuiz}
                  disabled={startQuizMutation.isPending}
                >
                  {startQuizMutation.isPending ? (
                    <>
                      <LoadingSpinner size="sm" className="mr-2" />
                      Iniciando...
                    </>
                  ) : (
                    <>
                      <Play className="mr-2 h-4 w-4" />
                      Iniciar
                    </>
                  )}
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Statistics Overview */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Templates Disponíveis
            </CardTitle>
            <CheckCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {templatesData?.items?.length || 0}
            </div>
            <p className="text-xs text-muted-foreground">
              Templates ativos no sistema
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Links Enviados
            </CardTitle>
            <Send className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {statsLoading ? '...' : (monthlyQuizStats?.total_sent ?? monthlyQuizStats?.total_links_created ?? 0)}
            </div>
            <p className="text-xs text-muted-foreground">
              Total de links mensais criados
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Links Ativos
            </CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {statsLoading ? '...' : (monthlyQuizStats?.total_active ?? monthlyQuizStats?.active_links ?? 0)}
            </div>
            <p className="text-xs text-muted-foreground">
              Aguardando resposta
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Taxa de Conclusão
            </CardTitle>
            <CheckCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {statsLoading ? '...' : `${Math.round(monthlyQuizStats?.completion_rate || 0)}%`}
            </div>
            <p className="text-xs text-muted-foreground">
              {(monthlyQuizStats?.total_completed ?? monthlyQuizStats?.completed_quizzes ?? 0)} de {(monthlyQuizStats?.total_sent ?? monthlyQuizStats?.total_links_created ?? 0)}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Templates List */}
      <Card>
        <CardHeader>
          <CardTitle>Templates de Questionários</CardTitle>
          <CardDescription>
            Templates disponíveis para aplicação
          </CardDescription>
        </CardHeader>
        <CardContent>
          {templatesLoading ? (
            <div className="flex items-center justify-center py-8">
              <LoadingSpinner size="lg" />
            </div>
          ) : !templatesData?.items || templatesData.items.length === 0 ? (
            <div className="text-center py-8">
              <CheckCircle className="mx-auto h-12 w-12 text-gray-400 mb-4" />
              <p className="text-gray-500">Nenhum template encontrado</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {templatesData?.items?.map((template: any) => (
                <Card key={template.id} className="hover:shadow-md transition-shadow">
                  <CardHeader>
                    <CardTitle className="text-lg">{template.name}</CardTitle>
                    {template.description && (
                      <CardDescription>{template.description}</CardDescription>
                    )}
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-500">
                        {template.questions?.length || 0} perguntas
                      </span>
                      <Badge variant="outline">Ativo</Badge>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Monthly Quiz Links Activity */}
      <Card>
        <CardHeader>
          <CardTitle>
            Links de Quiz Mensal
            {activeLinks && (
              <span className="text-sm font-normal text-gray-500 ml-2">
                ({activeLinks.length} ativos)
              </span>
            )}
          </CardTitle>
          <CardDescription>
            Atividade recente de links mensais enviados aos pacientes
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="mb-4">
            <Tabs value={linkStatusFilter} onValueChange={setLinkStatusFilter}>
              <TabsList>
                <TabsTrigger value="all">Todos</TabsTrigger>
                <TabsTrigger value="active">Ativos</TabsTrigger>
                <TabsTrigger value="completed">Completados</TabsTrigger>
                <TabsTrigger value="expired">Expirados</TabsTrigger>
              </TabsList>
            </Tabs>
          </div>

          {activeLinksLoading ? (
            <div className="flex items-center justify-center py-8">
              <LoadingSpinner size="lg" />
            </div>
          ) : !activeLinks || activeLinks.length === 0 ? (
            <div className="text-center py-8">
              <Send className="mx-auto h-12 w-12 text-gray-400 mb-4" />
              <p className="text-gray-500">Nenhum link encontrado</p>
              <p className="text-sm text-gray-400">
                Envie um link de quiz mensal para ver a atividade aqui
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Paciente</TableHead>
                  <TableHead>Template</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Enviado em</TableHead>
                  <TableHead>Expira em</TableHead>
                  <TableHead>Método</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {activeLinks
                  .filter((link: any) => {
                    if (linkStatusFilter === 'all') return true
                    return link.status === linkStatusFilter
                  })
                  .map((link: any) => (
                    <TableRow key={link.id}>
                      <TableCell>
                        <div>
                          <p className="font-medium">{link.patient_name}</p>
                          <p className="text-sm text-gray-500">ID: {link.patient_id}</p>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div>
                          <p className="font-medium">{link.template_name}</p>
                          <p className="text-sm text-gray-500">v{link.template_version}</p>
                        </div>
                      </TableCell>
                      <TableCell>
                        <MonthlyQuizStatus
                          status={link.status === 'active' ? 'sent' : link.status}
                          lastSent={link.sent_at}
                          completionDate={link.completed_at}
                          expiresAt={link.expires_at}
                        />
                      </TableCell>
                      <TableCell>
                        <span className="text-sm text-gray-600">
                          {link.sent_at ? formatDate(link.sent_at) : '-'}
                        </span>
                      </TableCell>
                      <TableCell>
                        <span className="text-sm text-gray-600">
                          {link.expires_at ? formatDate(link.expires_at) : '-'}
                        </span>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="capitalize">
                          {link.delivery_method}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Sessions List */}
      <Card>
        <CardHeader>
          <CardTitle>
            Sessões de Questionários
            {sessionsData && (
              <span className="text-sm font-normal text-gray-500 ml-2">
                ({sessionsData.total} total)
              </span>
            )}
          </CardTitle>
          <CardDescription>
            Histórico de questionários aplicados
          </CardDescription>
        </CardHeader>
        <CardContent>
          {sessionsLoading ? (
            <div className="flex items-center justify-center py-8">
              <LoadingSpinner size="lg" />
            </div>
          ) : (!sessionsData?.items || sessionsData?.items?.length === 0) ? (
            <div className="text-center py-8">
              <Users className="mx-auto h-12 w-12 text-gray-400 mb-4" />
              <p className="text-gray-500">Nenhuma sessão encontrada</p>
              <p className="text-sm text-gray-400">
                Inicie um questionário para ver as sessões aqui
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Paciente</TableHead>
                  <TableHead>Template</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Pontuação</TableHead>
                  <TableHead>Iniciado em</TableHead>
                  <TableHead>Completado em</TableHead>
                  <TableHead className="w-[100px]">Ações</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sessionsData?.items?.map((session: any) => (
                  <TableRow key={session.id}>
                    <TableCell>
                      <div>
                        <p className="font-medium">
                          {session.patient_name || 'Paciente não encontrado'}
                        </p>
                        <p className="text-sm text-gray-500">
                          ID: {session.patient_id}
                        </p>
                      </div>
                    </TableCell>
                    <TableCell>
                      <span className="font-medium">
                        {session.template_name || 'Template não encontrado'}
                      </span>
                    </TableCell>
                    <TableCell>
                      {getStatusBadge(session.is_completed ? 'completed' : 'started')}
                    </TableCell>
                    <TableCell>
                      {session.score !== undefined ? (
                        <span className="font-medium">
                          {Math.round(session.score)}%
                        </span>
                      ) : (
                        '-'
                      )}
                    </TableCell>
                    <TableCell>
                      <span className="text-sm text-gray-600">
                        {session.started_at ? formatDate(session.started_at) : '-'}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span className="text-sm text-gray-600">
                        {session.completed_at ? formatDate(session.completed_at) : '-'}
                      </span>
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={!session.is_completed}
                      >
                        <Eye className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
