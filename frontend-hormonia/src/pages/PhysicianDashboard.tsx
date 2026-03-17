import React, { lazy, Suspense, useCallback, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Brain,
  MessageSquare,
  Search,
  Download,
  RefreshCw,
  X,
  Users,
} from 'lucide-react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert'
import { apiClient } from '@/lib/api-client'
import { useAuth } from '@/app/providers/AuthContext'
import { usePhysicianPatients } from '@/hooks/api/usePhysicianPatients'
import { PhysicianPatientTable } from '@/features/dashboard/components/physician/PhysicianPatientTable'
import { PhysicianChatDialog } from '@/features/dashboard/components/physician/PhysicianChatDialog'
import { PhysicianExportDialog } from '@/features/dashboard/components/physician/PhysicianExportDialog'
import { ChatRole } from '@/types/api'
import { createLogger } from '@/lib/logger'
import type { AIChatMessage as ChatMessage } from '@/types/api'

const logger = createLogger('PhysicianDashboard')

export default function PhysicianDashboard() {
  const queryClient = useQueryClient()
  const { hasRole } = useAuth()

  const canAccessDashboard =
    hasRole('doctor') ||
    hasRole('physician') ||
    hasRole('medico') ||
    hasRole('admin') ||
    hasRole('superadmin')

  // Filters
  const [filters, setFilters] = useState({
    search: '',
    flow_phase: 'all' as string,
    flow_status: 'all' as string,
    page: 1,
    size: 20,
  })

  // Dialogs
  const [chatOpen, setChatOpen] = useState(false)
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])
  const [chatInput, setChatInput] = useState('')
  const [exportDialogOpen, setExportDialogOpen] = useState(false)

  // Fetch patients with enriched flow data
  const {
    data: patientData,
    isLoading,
    error,
    refetch,
  } = usePhysicianPatients({
    search: filters.search,
    flow_phase: filters.flow_phase,
    flow_status: filters.flow_status,
    page: filters.page,
    size: filters.size,
    enabled: canAccessDashboard,
  })

  const patients = patientData?.items ?? []
  const totalPatients = patientData?.total ?? 0

  // AI Chat
  const chatMutation = useMutation({
    mutationFn: async (message: string) => {
      return apiClient.ai.chat(message, { message_type: 'clinical_guidance' })
    },
    onSuccess: (data) => {
      setChatMessages((prev) => [
        ...prev,
        {
          id: Date.now().toString(),
          role: ChatRole.ASSISTANT,
          content: data.message ?? data.response ?? '',
          timestamp: new Date().toISOString(),
        },
      ])
    },
    onError: () => {
      setChatMessages((prev) => [
        ...prev,
        {
          id: Date.now().toString(),
          role: ChatRole.ASSISTANT,
          content: 'Desculpe, ocorreu um erro ao processar sua mensagem. Tente novamente.',
          timestamp: new Date().toISOString(),
        },
      ])
    },
  })

  const handleSendChat = useCallback(() => {
    if (!chatInput.trim()) return
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: ChatRole.USER,
      content: chatInput,
      timestamp: new Date().toISOString(),
    }
    setChatMessages((prev) => [...prev, userMessage])
    chatMutation.mutate(chatInput)
    setChatInput('')
  }, [chatInput, chatMutation])

  // Export
  const exportMutation = useMutation({
    mutationFn: async (_format: 'pdf' | 'excel') => {
      const reportData = {
        patients,
        totalPatients,
        generatedAt: new Date().toISOString(),
      }
      const blob = new Blob([JSON.stringify(reportData, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `physician-patients-${new Date().toISOString().slice(0, 10)}.json`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)
    },
    onSuccess: () => setExportDialogOpen(false),
  })

  const handleExport = useCallback(
    (format: 'pdf' | 'excel') => exportMutation.mutate(format),
    [exportMutation]
  )

  const handleRefresh = useCallback(() => {
    refetch()
    queryClient.invalidateQueries({ queryKey: ['physician'] })
  }, [refetch, queryClient])

  const hasActiveFilters = filters.search !== '' || filters.flow_phase !== 'all' || filters.flow_status !== 'all'

  // Permission denied
  if (!canAccessDashboard) {
    return (
      <div className="flex items-center justify-center h-screen">
        <Card className="w-96">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-red-500">
              <Users className="h-6 w-6" />
              Acesso Negado
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">
              Você não tem permissão para acessar o Dashboard do Médico.
            </p>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold flex items-center gap-2">
            <Brain className="h-7 w-7 md:h-8 md:w-8 text-primary" />
            Meus Pacientes
          </h1>
          <p className="text-muted-foreground mt-1">
            Visão geral dos pacientes e acompanhamento clínico
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={handleRefresh}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Atualizar
          </Button>
          <Button variant="outline" size="sm" onClick={() => setChatOpen(true)}>
            <MessageSquare className="h-4 w-4 mr-2" />
            Chat IA
          </Button>
          <Button variant="outline" size="sm" onClick={() => setExportDialogOpen(true)}>
            <Download className="h-4 w-4 mr-2" />
            Exportar
          </Button>
        </div>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-col sm:flex-row gap-3">
            {/* Search */}
            <div className="flex-1">
              <div className="relative">
                <label htmlFor="patient-search" className="sr-only">
                  Buscar paciente
                </label>
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  id="patient-search"
                  name="patientSearch"
                  placeholder="Buscar por nome..."
                  value={filters.search}
                  onChange={(e) =>
                    setFilters((f) => ({ ...f, search: e.target.value, page: 1 }))
                  }
                  className="pl-10"
                  autoComplete="off"
                />
              </div>
            </div>

            {/* Flow phase filter */}
            <Select
              value={filters.flow_phase}
              onValueChange={(value) =>
                setFilters((f) => ({ ...f, flow_phase: value, page: 1 }))
              }
            >
              <SelectTrigger className="w-full sm:w-[180px]">
                <SelectValue placeholder="Fase do Fluxo" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todas as Fases</SelectItem>
                <SelectItem value="onboarding">Onboarding</SelectItem>
                <SelectItem value="daily_follow_up">Follow-up Diário</SelectItem>
                <SelectItem value="quiz_mensal">Quiz Mensal</SelectItem>
              </SelectContent>
            </Select>

            {/* Flow status filter */}
            <Select
              value={filters.flow_status}
              onValueChange={(value) =>
                setFilters((f) => ({ ...f, flow_status: value, page: 1 }))
              }
            >
              <SelectTrigger className="w-full sm:w-[160px]">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos os Status</SelectItem>
                <SelectItem value="active">Ativo</SelectItem>
                <SelectItem value="paused">Pausado</SelectItem>
                <SelectItem value="completed">Concluído</SelectItem>
              </SelectContent>
            </Select>

            {/* Clear filters */}
            {hasActiveFilters && (
              <Button
                variant="ghost"
                size="sm"
                className="self-center"
                onClick={() =>
                  setFilters({ search: '', flow_phase: 'all', flow_status: 'all', page: 1, size: 20 })
                }
              >
                <X className="h-4 w-4 mr-1" />
                Limpar
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Error state */}
      {error && (
        <Alert variant="destructive">
          <AlertTitle>Erro ao carregar pacientes</AlertTitle>
          <AlertDescription>
            {error instanceof Error ? error.message : 'Erro desconhecido'}
          </AlertDescription>
        </Alert>
      )}

      {/* Loading state */}
      {isLoading && (
        <div className="space-y-3">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-96 w-full" />
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !error && patients.length === 0 && (
        <Card>
          <CardContent className="pt-6">
            <div className="text-center text-muted-foreground py-8">
              <Users className="mx-auto h-10 w-10 mb-3" />
              <p className="text-lg font-medium">Nenhum paciente encontrado</p>
              {hasActiveFilters && (
                <p className="text-sm mt-1">Tente ajustar os filtros de busca</p>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Patient table */}
      {!isLoading && !error && patients.length > 0 && (
        <PhysicianPatientTable
          patients={patients}
          total={totalPatients}
          page={filters.page}
          size={filters.size}
          onPageChange={(page) => setFilters((f) => ({ ...f, page }))}
        />
      )}

      {/* Chat dialog */}
      <PhysicianChatDialog
        open={chatOpen}
        onOpenChange={setChatOpen}
        messages={chatMessages}
        inputValue={chatInput}
        onInputChange={setChatInput}
        onSend={handleSendChat}
        isPending={chatMutation.isPending}
      />

      {/* Export dialog */}
      <PhysicianExportDialog
        open={exportDialogOpen}
        onOpenChange={setExportDialogOpen}
        onExport={handleExport}
        isPending={exportMutation.isPending}
      />
    </div>
  )
}
