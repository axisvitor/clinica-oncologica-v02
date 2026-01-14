import React, { useState, useEffect } from 'react'
import { formatDistanceToNow } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import { Play, Pause, Calendar, Clock } from 'lucide-react'
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
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { usePauseFlow, useResumeFlow, FlowData } from '@/hooks/useFlows'

interface FlowsTableProps {
  flows?: FlowData[]
  isLoading?: boolean
}

export function FlowsTable({ flows, isLoading }: FlowsTableProps) {
  const pauseFlow = usePauseFlow()
  const resumeFlow = useResumeFlow()
  const [_isMobile, setIsMobile] = useState(false)

  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 768)
    checkMobile()
    window.addEventListener('resize', checkMobile)
    return () => window.removeEventListener('resize', checkMobile)
  }, [])

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'active':
        return (
          <Badge className="bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200">
            Ativo
          </Badge>
        )
      case 'paused':
        return (
          <Badge className="bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200">
            Pausado
          </Badge>
        )
      case 'completed':
        return (
          <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200">
            Concluído
          </Badge>
        )
      case 'cancelled':
        return (
          <Badge variant="secondary">
            Cancelado
          </Badge>
        )
      default:
        return <Badge variant="outline">{status}</Badge>
    }
  }

  const getFlowTypeName = (flowType: string) => {
    const typeMap: Record<string, string> = {
      onboarding: 'Onboarding',
      daily_follow_up: 'Acompanhamento Diario',
      quiz_mensal: 'Quiz Mensal',
      custom: 'Personalizado',
      initial_15_days: 'Inicial 1-15 dias',
      days_16_45: 'Dias 16-45',
      monthly_recurring: 'Mensal Recorrente',
      monthly_quiz: 'Quiz Mensal',
      daily_checkin: 'Check-in Diario',
      daily_engagement: 'Engajamento Diario',
    }
    return typeMap[flowType] || flowType
  }

  const getInitials = (name: string) => {
    return name
      .split(' ')
      .map(n => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2)
  }

  const formatLastMessage = (lastMessage?: string) => {
    if (!lastMessage) return 'Nunca'

    try {
      return formatDistanceToNow(new Date(lastMessage), {
        addSuffix: true,
        locale: ptBR
      })
    } catch {
      return 'Data inválida'
    }
  }

  const handlePauseResume = (flow: FlowData) => {
    if (flow.status === 'active') {
      pauseFlow.mutate(flow.patient_id)
    } else if (flow.status === 'paused') {
      resumeFlow.mutate(flow.patient_id)
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3, 4, 5].map((i) => (
          <Card key={i} className="p-4">
            <div className="flex items-center space-x-4 py-3">
              <Skeleton className="h-10 w-10 rounded-full" />
              <div className="space-y-2 flex-1">
                <Skeleton className="h-4 w-48" />
                <Skeleton className="h-3 w-32" />
              </div>
              <Skeleton className="h-6 w-24" />
              <Skeleton className="h-6 w-16" />
              <Skeleton className="h-8 w-24" />
            </div>
          </Card>
        ))}
      </div>
    )
  }

  if (!flows || flows.length === 0) {
    return (
      <div className="text-center py-12 border rounded-lg bg-muted/10">
        <Calendar className="h-12 w-12 mx-auto text-muted-foreground mb-3" />
        <p className="text-muted-foreground mb-1">Nenhum fluxo encontrado</p>
        <p className="text-sm text-muted-foreground">
          Inicie um novo fluxo para começar o acompanhamento
        </p>
      </div>
    )
  }

  return (
    <>
      {/* Desktop Table - hidden on mobile */}
      <div className="hidden md:block rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Paciente</TableHead>
              <TableHead>Tipo de Fluxo</TableHead>
              <TableHead>Dia Atual</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Última Mensagem</TableHead>
              <TableHead className="text-right">Ações</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {flows.map((flow) => (
              <TableRow key={flow.id}>
                <TableCell>
                  <div className="flex items-center space-x-3">
                    <Avatar className="h-9 w-9">
                      <AvatarFallback className="bg-blue-600 text-white text-xs">
                        {getInitials(flow.patient_name || 'Unknown')}
                      </AvatarFallback>
                    </Avatar>
                    <div>
                      <p className="font-medium text-sm">{flow.patient_name}</p>
                      <p className="text-xs text-muted-foreground">
                        {flow.monthly_cycle ? `Ciclo ${flow.monthly_cycle}` : 'Primeiro ciclo'}
                      </p>
                    </div>
                  </div>
                </TableCell>
                <TableCell>
                  <Badge variant="outline">
                    {getFlowTypeName(flow.flow_type)}
                  </Badge>
                </TableCell>
                <TableCell>
                  <div className="flex items-center gap-1.5">
                    <Clock className="h-3.5 w-3.5 text-muted-foreground" />
                    <span className="font-medium">{flow.current_day}</span>
                  </div>
                </TableCell>
                <TableCell>
                  {getStatusBadge(flow.status)}
                </TableCell>
                <TableCell>
                  <span className="text-sm text-muted-foreground">
                    {formatLastMessage(flow.last_message_sent)}
                  </span>
                </TableCell>
                <TableCell className="text-right">
                  {(flow.status === 'active' || flow.status === 'paused') && (
                    <Button
                      size="sm"
                      variant={flow.status === 'active' ? 'outline' : 'default'}
                      onClick={() => handlePauseResume(flow)}
                      disabled={pauseFlow.isPending || resumeFlow.isPending}
                    >
                      {flow.status === 'active' ? (
                        <>
                          <Pause className="h-3.5 w-3.5 mr-1.5" />
                          Pausar
                        </>
                      ) : (
                        <>
                          <Play className="h-3.5 w-3.5 mr-1.5" />
                          Retomar
                        </>
                      )}
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      {/* Mobile Cards - shown on mobile */}
      <div className="md:hidden space-y-3">
        {flows.map((flow) => (
          <Card key={flow.id} className="p-4 hover:shadow-md transition-shadow">
            {/* Header with Avatar and Status */}
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-3 flex-1 min-w-0">
                <Avatar className="h-12 w-12 flex-shrink-0">
                  <AvatarFallback className="bg-blue-600 text-white text-sm">
                    {getInitials(flow.patient_name || 'Unknown')}
                  </AvatarFallback>
                </Avatar>
                <div className="min-w-0 flex-1">
                  <p className="font-medium truncate">{flow.patient_name}</p>
                  <p className="text-xs text-muted-foreground truncate">
                    {flow.monthly_cycle ? `Ciclo ${flow.monthly_cycle}` : 'Primeiro ciclo'}
                  </p>
                </div>
              </div>
              <div className="flex-shrink-0">
                {getStatusBadge(flow.status)}
              </div>
            </div>

            {/* Flow Details Grid */}
            <div className="grid grid-cols-2 gap-3 text-sm mb-3">
              <div>
                <span className="text-muted-foreground text-xs block mb-1">Tipo de Fluxo:</span>
                <Badge variant="outline" className="text-xs">
                  {getFlowTypeName(flow.flow_type)}
                </Badge>
              </div>
              <div>
                <span className="text-muted-foreground text-xs block mb-1">Dia Atual:</span>
                <div className="flex items-center gap-1.5">
                  <Clock className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="font-medium">{flow.current_day}</span>
                </div>
              </div>
            </div>

            {/* Last Message */}
            <div className="mb-3 pb-3 border-b">
              <span className="text-muted-foreground text-xs block mb-1">Última Mensagem:</span>
              <p className="text-sm">
                {formatLastMessage(flow.last_message_sent)}
              </p>
            </div>

            {/* Action Button */}
            {(flow.status === 'active' || flow.status === 'paused') && (
              <Button
                size="sm"
                variant={flow.status === 'active' ? 'outline' : 'default'}
                onClick={() => handlePauseResume(flow)}
                disabled={pauseFlow.isPending || resumeFlow.isPending}
                className="w-full h-10"
              >
                {flow.status === 'active' ? (
                  <>
                    <Pause className="h-4 w-4 mr-2" />
                    Pausar Fluxo
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4 mr-2" />
                    Retomar Fluxo
                  </>
                )}
              </Button>
            )}
          </Card>
        ))}
      </div>
    </>
  )
}
