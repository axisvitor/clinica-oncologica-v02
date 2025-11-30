import React, { useState, memo } from 'react'
import { formatDistanceToNow } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { MoveHorizontal as MoreHorizontal, Eye, CreditCard as Edit, Trash2, Play, Pause, Send } from 'lucide-react'
import { apiClient } from '@/lib/api-client'
import { MonthlyQuizStatus } from './MonthlyQuizStatus'
import { SendQuizLinkModal } from '@/features/quiz/SendQuizLinkModal'
import { useMonthlyQuizStatus, useResendQuizLink } from '@/hooks/useMonthlyQuizStatus'
import { List } from 'react-window'
import AutoSizer from 'react-virtualized-auto-sizer'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Card } from '@/components/ui/card'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Pagination } from '@/components/ui/pagination'
import { useToast } from '@/components/ui/use-toast'
import { getErrorMessage } from '@/lib/utils/type-guards'
import { cn } from '@/lib/utils'

import type { Patient } from '@/types/api'

interface PatientsTableProps {
  patients: Patient[]
  currentPage: number
  totalPages: number
  onPageChange: (page: number) => void
  onEditPatient?: (patient: Patient) => void
}

interface RowData {
  patients: Patient[]
  onNavigate: (id: string) => void
  onEdit?: (patient: Patient) => void
  onDelete: (e: React.MouseEvent, patientId: string, patientName: string) => void
  onActivate: (id: string) => void
  onDeactivate: (id: string) => void
  onSendQuiz: (patient: { id: string; name: string }) => void
  confirmDeleteId: string | null
  isResending: boolean
}

interface PatientRowProps extends RowData {
  style: React.CSSProperties
  index: number
}

const GRID_COLS = "grid-cols-[2.5fr_1.5fr_1fr_1fr_1fr_0.8fr_1.2fr_70px]"

const PatientRow = memo(({ style, index, patients, onNavigate, onEdit, onDelete, onActivate, onDeactivate, onSendQuiz, confirmDeleteId, isResending }: PatientRowProps) => {
  const patient = patients[index]
  const { data: quizStatus, isLoading } = useMonthlyQuizStatus(patient?.id ?? '')
  const resendQuizLinkMutation = useResendQuizLink()

  if (!patient) return null

  const getInitials = (name: string) => {
    return name
      .split(' ')
      .map(n => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2)
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'active':
        return <Badge className="bg-green-100 text-green-800">Ativo</Badge>
      case 'paused':
        return <Badge className="bg-yellow-100 text-yellow-800">Pausado</Badge>
      case 'completed':
        return <Badge className="bg-blue-100 text-blue-800">Concluído</Badge>
      case 'inactive':
        return <Badge variant="secondary">Inativo</Badge>
      case 'cancelled':
        return <Badge className="bg-red-100 text-red-800">Cancelado</Badge>
      default:
        return <Badge variant="outline">{status}</Badge>
    }
  }

  const formatLastContact = (lastContact?: string) => {
    if (!lastContact) return 'Nunca'

    try {
      return formatDistanceToNow(new Date(lastContact), {
        addSuffix: true,
        locale: ptBR
      })
    } catch {
      return 'Data inválida'
    }
  }

  const renderQuizStatus = () => {
    if (isLoading) {
      return <Badge variant="outline" className="animate-pulse">Carregando...</Badge>
    }

    if (!quizStatus || quizStatus.status === 'not_sent') {
      return (
        <Button
          variant="ghost"
          size="sm"
          onClick={(e) => {
            e.stopPropagation()
            onSendQuiz({ id: patient.id, name: patient.name })
          }}
        >
          <Send className="h-4 w-4 mr-1" />
          Enviar
        </Button>
      )
    }

    return (
      <MonthlyQuizStatus
        status={quizStatus.status}
        {...(quizStatus.last_sent && { lastSent: quizStatus.last_sent })}
        {...(quizStatus.access_date && { accessDate: quizStatus.access_date })}
        {...(quizStatus.completion_date && { completionDate: quizStatus.completion_date })}
        {...(quizStatus.expires_at && { expiresAt: quizStatus.expires_at })}
        {...(quizStatus.session_id && { onResend: () => resendQuizLinkMutation.mutate(quizStatus.session_id!) })}
        isResending={isResending}
      />
    )
  }

  return (
    <div
      style={style}
      className={cn(
        "grid items-center gap-4 px-4 py-2 border-b hover:bg-muted/50 transition-colors cursor-pointer",
        GRID_COLS
      )}
      onClick={() => onNavigate(patient.id)}
    >
      {/* Patient */}
      <div className="flex items-center space-x-3 min-w-0">
        <Avatar className="h-8 w-8 flex-shrink-0">
          <AvatarImage src="" alt={patient.name} />
          <AvatarFallback className="bg-blue-600 text-white text-xs">
            {getInitials(patient.name)}
          </AvatarFallback>
        </Avatar>
        <div className="min-w-0">
          <p className="font-medium text-gray-900 truncate">{patient.name}</p>
          {patient.email && (
            <p className="text-sm text-gray-500 truncate">{patient.email}</p>
          )}
        </div>
      </div>

      {/* Contact */}
      <div className="text-sm truncate">{patient.phone}</div>

      {/* Treatment */}
      <div><Badge variant="outline" className="truncate">{patient.treatment_type}</Badge></div>

      {/* Status */}
      <div>{getStatusBadge(patient.status)}</div>

      {/* Quiz */}
      <div onClick={(e) => e.stopPropagation()} className="min-w-0">
        {renderQuizStatus()}
      </div>

      {/* Current Day */}
      <div className="font-medium">{patient.current_day ?? 0}</div>

      {/* Last Contact */}
      <div className="text-sm text-gray-600 truncate">
        {formatLastContact(patient.last_contact)}
      </div>

      {/* Actions */}
      <div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              className="h-8 w-8 p-0"
              onClick={(e) => e.stopPropagation()}
            >
              <MoreHorizontal className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>Ações</DropdownMenuLabel>
            <DropdownMenuItem
              onClick={(e) => {
                e.stopPropagation()
                onNavigate(patient.id)
              }}
            >
              <Eye className="mr-2 h-4 w-4" />
              Visualizar
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={(e) => {
                e.stopPropagation()
                onEdit?.(patient)
              }}
            >
              <Edit className="mr-2 h-4 w-4" />
              Editar
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            {patient.status === 'active' ? (
              <DropdownMenuItem
                onClick={(e) => {
                  e.stopPropagation()
                  onDeactivate(patient.id)
                }}
              >
                <Pause className="mr-2 h-4 w-4" />
                Pausar
              </DropdownMenuItem>
            ) : (
              <DropdownMenuItem
                onClick={(e) => {
                  e.stopPropagation()
                  onActivate(patient.id)
                }}
              >
                <Play className="mr-2 h-4 w-4" />
                Ativar
              </DropdownMenuItem>
            )}
            <DropdownMenuSeparator />
            <DropdownMenuItem
              className="text-red-600"
              onClick={(e) => onDelete(e, patient.id, patient.name)}
            >
              <Trash2 className="mr-2 h-4 w-4" />
              Excluir
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  )
})

const MobilePatientCard = memo(({ style, index, patients, onNavigate, onEdit, onDelete, onActivate, onDeactivate, onSendQuiz, confirmDeleteId, isResending }: PatientRowProps) => {
  const patient = patients[index]
  const { data: quizStatus, isLoading } = useMonthlyQuizStatus(patient?.id ?? '')
  const resendQuizLinkMutation = useResendQuizLink()

  if (!patient) return null

  const getInitials = (name: string) => {
    return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'active':
        return <Badge className="bg-green-100 text-green-800">Ativo</Badge>
      case 'paused':
        return <Badge className="bg-yellow-100 text-yellow-800">Pausado</Badge>
      case 'completed':
        return <Badge className="bg-blue-100 text-blue-800">Concluído</Badge>
      case 'inactive':
        return <Badge variant="secondary">Inativo</Badge>
      case 'cancelled':
        return <Badge className="bg-red-100 text-red-800">Cancelado</Badge>
      default:
        return <Badge variant="outline">{status}</Badge>
    }
  }

  const formatLastContact = (lastContact?: string) => {
    if (!lastContact) return 'Nunca'
    try {
      return formatDistanceToNow(new Date(lastContact), { addSuffix: true, locale: ptBR })
    } catch {
      return 'Data inválida'
    }
  }

  const renderQuizStatus = () => {
    if (isLoading) return <Badge variant="outline" className="animate-pulse text-xs">Carregando...</Badge>

    if (!quizStatus || quizStatus.status === 'not_sent') {
      return (
        <Button
          variant="ghost"
          size="sm"
          className="h-7 text-xs"
          onClick={(e) => {
            e.stopPropagation()
            onSendQuiz({ id: patient.id, name: patient.name })
          }}
        >
          <Send className="h-3 w-3 mr-1" />
          Enviar
        </Button>
      )
    }

    return (
      <MonthlyQuizStatus
        status={quizStatus.status}
        {...(quizStatus.last_sent && { lastSent: quizStatus.last_sent })}
        {...(quizStatus.access_date && { accessDate: quizStatus.access_date })}
        {...(quizStatus.completion_date && { completionDate: quizStatus.completion_date })}
        {...(quizStatus.expires_at && { expiresAt: quizStatus.expires_at })}
        {...(quizStatus.session_id && { onResend: () => resendQuizLinkMutation.mutate(quizStatus.session_id!) })}
        isResending={isResending}
      />
    )
  }

  return (
    <div style={style} className="px-4 pb-3">
      <Card
        className="p-4 hover:shadow-md transition-shadow cursor-pointer h-full"
        onClick={() => onNavigate(patient.id)}
      >
        {/* Header with Avatar and Status */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3 flex-1 min-w-0">
            <Avatar className="h-10 w-10 flex-shrink-0">
              <AvatarImage src="" alt={patient.name} />
              <AvatarFallback className="bg-blue-600 text-white text-sm">
                {getInitials(patient.name)}
              </AvatarFallback>
            </Avatar>
            <div className="min-w-0 flex-1">
              <p className="font-medium truncate">{patient.name}</p>
              <p className="text-sm text-muted-foreground truncate">{patient.phone}</p>
              {patient.email && (
                <p className="text-xs text-muted-foreground truncate">{patient.email}</p>
              )}
            </div>
          </div>
          <div className="flex-shrink-0">
            {getStatusBadge(patient.status)}
          </div>
        </div>

        {/* Patient Details Grid */}
        <div className="grid grid-cols-2 gap-2 text-sm mb-3">
          <div>
            <span className="text-muted-foreground text-xs">Tratamento:</span>
            <p className="font-medium truncate">
              <Badge variant="outline" className="text-xs">{patient.treatment_type}</Badge>
            </p>
          </div>
          <div>
            <span className="text-muted-foreground text-xs">Dia Atual:</span>
            <p className="font-medium">{patient.current_day ?? 0}</p>
          </div>
        </div>

        {/* Quiz Status */}
        <div className="mb-3" onClick={(e) => e.stopPropagation()}>
          <span className="text-muted-foreground text-xs block mb-1">Quiz Mensal:</span>
          {renderQuizStatus()}
        </div>

        {/* Footer with Last Contact and Actions */}
        <div className="flex justify-between items-center pt-3 border-t text-xs text-muted-foreground">
          <span className="truncate flex-1">
            Último contato: {formatLastContact(patient.last_contact)}
          </span>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                className="h-8 w-8 p-0 flex-shrink-0 ml-2"
                onClick={(e) => e.stopPropagation()}
              >
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>Ações</DropdownMenuLabel>
              <DropdownMenuItem
                onClick={(e) => {
                  e.stopPropagation()
                  onNavigate(patient.id)
                }}
              >
                <Eye className="mr-2 h-4 w-4" />
                Visualizar
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={(e) => {
                  e.stopPropagation()
                  onEdit?.(patient)
                }}
              >
                <Edit className="mr-2 h-4 w-4" />
                Editar
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              {patient.status === 'active' ? (
                <DropdownMenuItem
                  onClick={(e) => {
                    e.stopPropagation()
                    onDeactivate(patient.id)
                  }}
                >
                  <Pause className="mr-2 h-4 w-4" />
                  Pausar
                </DropdownMenuItem>
              ) : (
                <DropdownMenuItem
                  onClick={(e) => {
                    e.stopPropagation()
                    onActivate(patient.id)
                  }}
                >
                  <Play className="mr-2 h-4 w-4" />
                  Ativar
                </DropdownMenuItem>
              )}
              <DropdownMenuSeparator />
              <DropdownMenuItem
                className="text-red-600"
                onClick={(e) => onDelete(e, patient.id, patient.name)}
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Excluir
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </Card>
    </div>
  )
})

export function PatientsTable({
  patients,
  currentPage,
  totalPages,
  onPageChange,
  onEditPatient
}: PatientsTableProps) {
  const navigate = useNavigate()
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [selectedPatient, setSelectedPatient] = useState<{ id: string; name: string } | null>(null)
  const [showSendQuizModal, setShowSendQuizModal] = useState(false)
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)
  const resendQuizLinkMutation = useResendQuizLink()

  const mutationOptions = {
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patients'] })
    },
    onError: (error: unknown) => {
      toast({
        title: 'Erro',
        description: getErrorMessage(error) || 'Ocorreu um erro inesperado.',
        variant: 'destructive'
      })
    }
  }

  const deleteMutation = useMutation({
    mutationFn: (id: string) => apiClient.patients.deletePatient(id),
    ...mutationOptions,
    onSuccess: () => {
      mutationOptions.onSuccess()
      toast({ title: 'Paciente excluído com sucesso' })
    }
  })

  const activateMutation = useMutation({
    mutationFn: (id: string) => apiClient.patients.activate(id),
    ...mutationOptions,
    onSuccess: () => {
      mutationOptions.onSuccess()
      toast({ title: 'Paciente ativado com sucesso' })
    }
  })

  const deactivateMutation = useMutation({
    mutationFn: (id: string) => apiClient.patients.deactivate(id),
    ...mutationOptions,
    onSuccess: () => {
      mutationOptions.onSuccess()
      toast({ title: 'Paciente desativado (pausado) com sucesso' })
    }
  })

  const handleDelete = (e: React.MouseEvent, patientId: string, patientName: string) => {
    e.stopPropagation()
    if (confirmDeleteId === patientId) {
      setConfirmDeleteId(null)
      deleteMutation.mutate(patientId)
      return
    }
    setConfirmDeleteId(patientId)
    toast({
      title: 'Confirme a exclusão',
      description: `Clique novamente para excluir ${patientName}.`,
      variant: 'destructive'
    })
    setTimeout(() => {
      setConfirmDeleteId((prev) => (prev === patientId ? null : prev))
    }, 3000)
  }

  if (patients.length === 0) {
    return (
      <div className="text-center py-8">
        <p className="text-gray-500">Nenhum paciente encontrado</p>
        <p className="text-sm text-gray-400 mt-1">
          Tente ajustar os filtros ou criar um novo paciente
        </p>
      </div>
    )
  }

  const itemData: RowData = {
    patients,
    onNavigate: (id) => navigate(`/patients/${id}`),
    onEdit: onEditPatient,
    onDelete: handleDelete,
    onActivate: (id) => activateMutation.mutate(id),
    onDeactivate: (id) => deactivateMutation.mutate(id),
    onSendQuiz: (patient) => {
      setSelectedPatient(patient)
      setShowSendQuizModal(true)
    },
    confirmDeleteId,
    isResending: resendQuizLinkMutation.isPending
  }

  return (
    <div className="space-y-4 h-[calc(100vh-220px)] min-h-[500px] flex flex-col">
      {/* Desktop Table - hidden on mobile */}
      <div className="hidden md:flex flex-1 flex-col overflow-hidden border md:rounded-lg">
        <div className={cn("grid bg-muted/50 font-medium text-sm border-b", GRID_COLS)}>
          <div className="px-4 py-3">Paciente</div>
          <div className="px-4 py-3">Contato</div>
          <div className="px-4 py-3">Tratamento</div>
          <div className="px-4 py-3">Status</div>
          <div className="px-4 py-3">Quiz Mensal</div>
          <div className="px-4 py-3">Dia Atual</div>
          <div className="px-4 py-3">Último Contato</div>
          <div className="px-4 py-3 w-[70px]">Ações</div>
        </div>
        
        <div className="flex-1">
          <AutoSizer>
            {({ height, width }) => (
              <List
                style={{ height, width }}
                rowCount={patients.length}
                rowHeight={80} // Approximate height
                rowProps={itemData}
                rowComponent={PatientRow as any}
              />
            )}
          </AutoSizer>
        </div>
      </div>

      {/* Mobile Cards - hidden on desktop */}
      <div className="md:hidden flex-1">
        <AutoSizer>
          {({ height, width }) => (
            <List
              style={{ height, width }}
              rowCount={patients.length}
              rowHeight={300} // Approximate card height
              rowProps={itemData}
              rowComponent={MobilePatientCard as any}
            />
          )}
        </AutoSizer>
      </div>

      {totalPages > 1 && (
        <div className="pt-2">
          <Pagination
            currentPage={currentPage}
            totalPages={totalPages}
            onPageChange={onPageChange}
          />
        </div>
      )}

      {/* Send Quiz Modal */}
      {selectedPatient && (
        <SendQuizLinkModal
          open={showSendQuizModal}
          onOpenChange={setShowSendQuizModal}
          patientId={selectedPatient.id}
          patientName={selectedPatient.name}
          onSuccess={() => {
            setSelectedPatient(null)
            queryClient.invalidateQueries({ queryKey: ['monthly-quiz-status'] })
          }}
        />
      )}
    </div>
  )
}
