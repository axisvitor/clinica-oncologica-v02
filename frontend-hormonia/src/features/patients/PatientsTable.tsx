import React, { useState } from 'react'
import { formatDistanceToNow } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { MoveHorizontal as MoreHorizontal, Eye, CreditCard as Edit, Trash2, Play, Pause, Send } from 'lucide-react'
import { apiClient } from '@/lib/api-client'
import { MonthlyQuizStatus } from './MonthlyQuizStatus'
import { SendQuizLinkModal } from '@/features/quiz/SendQuizLinkModal'
import { useMonthlyQuizStatus, useResendQuizLink } from '@/hooks/useMonthlyQuizStatus'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
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

import type { Patient } from '@/types/api'

interface PatientsTableProps {
  patients: Patient[]
  currentPage: number
  totalPages: number
  onPageChange: (page: number) => void
  onEditPatient?: (patient: Patient) => void
}

interface PatientRowProps {
  patient: Patient
  onNavigate: (id: string) => void
  onEdit?: (patient: Patient) => void
  onDelete: (e: React.MouseEvent, patientId: string, patientName: string) => void
  onActivate: (id: string) => void
  onDeactivate: (id: string) => void
  onSendQuiz: (patient: { id: string; name: string }) => void
  confirmDeleteId: string | null
  isResending: boolean
}

const PatientRow = React.memo(({
  patient,
  onNavigate,
  onEdit,
  onDelete,
  onActivate,
  onDeactivate,
  onSendQuiz,
  confirmDeleteId,
  isResending
}: PatientRowProps) => {
  const { data: quizStatus, isLoading } = useMonthlyQuizStatus(patient.id)
  const resendQuizLinkMutation = useResendQuizLink()

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
    <TableRow
      key={patient.id}
      className="cursor-pointer hover:bg-muted/50"
      onClick={() => onNavigate(patient.id)}
    >
      <TableCell>
        <div className="flex items-center space-x-3">
          <Avatar className="h-8 w-8">
            <AvatarImage src="" alt={patient.name} />
            <AvatarFallback className="bg-blue-600 text-white text-xs">
              {getInitials(patient.name)}
            </AvatarFallback>
          </Avatar>
          <div>
            <p className="font-medium text-gray-900">{patient.name}</p>
            {patient.email && (
              <p className="text-sm text-gray-500">{patient.email}</p>
            )}
          </div>
        </div>
      </TableCell>
      <TableCell>
        <p className="text-sm">{patient.phone}</p>
      </TableCell>
      <TableCell>
        <Badge variant="outline">{patient.treatment_type}</Badge>
      </TableCell>
      <TableCell>
        {getStatusBadge(patient.status)}
      </TableCell>
      <TableCell onClick={(e) => e.stopPropagation()}>
        {renderQuizStatus()}
      </TableCell>
      <TableCell>
        <span className="font-medium">{patient.current_day ?? 0}</span>
      </TableCell>
      <TableCell>
        <span className="text-sm text-gray-600">
          {formatLastContact(patient.last_contact)}
        </span>
      </TableCell>
      <TableCell>
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
      </TableCell>
    </TableRow>
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

  return (
    <div className="space-y-4">
      <div className="overflow-x-auto -mx-4 md:mx-0">
        <div className="inline-block min-w-full align-middle">
          <div className="overflow-hidden border md:rounded-lg">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Paciente</TableHead>
                  <TableHead>Contato</TableHead>
                  <TableHead>Tratamento</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Quiz Mensal</TableHead>
                  <TableHead>Dia Atual</TableHead>
                  <TableHead>Último Contato</TableHead>
                  <TableHead className="w-[70px]">Ações</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {patients.map((patient) => (
                  <PatientRow
                    key={patient.id}
                    patient={patient}
                    onNavigate={(id) => navigate(`/patients/${id}`)}
                    onEdit={onEditPatient}
                    onDelete={handleDelete}
                    onActivate={(id) => activateMutation.mutate(id)}
                    onDeactivate={(id) => deactivateMutation.mutate(id)}
                    onSendQuiz={(patient) => {
                      setSelectedPatient(patient)
                      setShowSendQuizModal(true)
                    }}
                    confirmDeleteId={confirmDeleteId}
                    isResending={resendQuizLinkMutation.isPending}
                  />
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
      </div>

      {totalPages > 1 && (
        <Pagination
          currentPage={currentPage}
          totalPages={totalPages}
          onPageChange={onPageChange}
        />
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
