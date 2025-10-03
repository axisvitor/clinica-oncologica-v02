import React from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { 
  Play, 
  Pause, 
  SkipForward, 
  Clock, 
  CheckCircle, 
  AlertCircle,
  Calendar,
  MessageSquare,
  Loader2
} from 'lucide-react'
import { useFlowState, useFlowOperations } from '../../hooks/useFlowEngine'
import { FlowType, FlowStatus as FlowStatusEnum } from '../../../types/api'

interface FlowStatusProps {
  patientId: string
}

export function FlowStatus({ patientId }: FlowStatusProps) {
  const { data: flowState, isLoading, error } = useFlowState(patientId)
  const { operations, isLoading: isOperationLoading } = useFlowOperations(patientId)

  if (isLoading) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="text-center">
            <Loader2 className="mx-auto h-8 w-8 animate-spin mb-2" />
            <p className="text-muted-foreground">Carregando status do fluxo...</p>
          </div>
        </CardContent>
      </Card>
    )
  }

  if (error) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="text-center text-red-500">
            <AlertCircle className="mx-auto h-8 w-8 mb-2" />
            <p>Erro ao carregar status do fluxo</p>
          </div>
        </CardContent>
      </Card>
    )
  }

  if (!flowState) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="text-center text-muted-foreground">
            <MessageSquare className="mx-auto h-8 w-8 mb-2" />
            <p>Nenhum fluxo ativo</p>
            <div className="mt-4 space-y-2">
              <Button 
                className="w-full" 
                size="sm"
                onClick={() => operations.start(FlowType.INITIAL_15_DAYS)}
                disabled={isOperationLoading}
              >
                {isOperationLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : null}
                Iniciar Fluxo 15 Dias
              </Button>
              <Button 
                variant="outline" 
                className="w-full" 
                size="sm"
                onClick={() => operations.start(FlowType.MONTHLY_RECURRING)}
                disabled={isOperationLoading}
              >
                Iniciar Fluxo Mensal
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    )
  }

  const getStatusColor = (status: FlowStatusEnum) => {
    switch (status) {
      case FlowStatusEnum.ACTIVE: return 'bg-green-500'
      case FlowStatusEnum.PAUSED: return 'bg-yellow-500'
      case FlowStatusEnum.COMPLETED: return 'bg-blue-500'
      case FlowStatusEnum.CANCELLED: return 'bg-red-500'
      default: return 'bg-gray-500'
    }
  }

  const getStatusIcon = (status: FlowStatusEnum) => {
    switch (status) {
      case FlowStatusEnum.ACTIVE: return <Play className="h-4 w-4" />
      case FlowStatusEnum.PAUSED: return <Pause className="h-4 w-4" />
      case FlowStatusEnum.COMPLETED: return <CheckCircle className="h-4 w-4" />
      case FlowStatusEnum.CANCELLED: return <AlertCircle className="h-4 w-4" />
      default: return <Clock className="h-4 w-4" />
    }
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('pt-BR')
  }

  const formatDateTime = (dateString: string) => {
    return new Date(dateString).toLocaleString('pt-BR')
  }

  const getFlowTypeLabel = (flowType: FlowType) => {
    switch (flowType) {
      case FlowType.INITIAL_15_DAYS: return 'Primeiros 15 Dias'
      case FlowType.DAYS_16_45: return 'Dias 16-45'
      case FlowType.MONTHLY_RECURRING: return 'Mensal Recorrente'
      default: return flowType
    }
  }

  // Calculate progress based on flow type
  const getTotalDays = (flowType: FlowType) => {
    switch (flowType) {
      case FlowType.INITIAL_15_DAYS: return 15
      case FlowType.DAYS_16_45: return 30
      case FlowType.MONTHLY_RECURRING: return 30
      default: return 30
    }
  }

  const totalDays = getTotalDays(flowState.flow_type)
  const completionRate = (flowState.current_day / totalDays) * 100

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-lg">Status do Fluxo</CardTitle>
            <CardDescription>
              {getFlowTypeLabel(flowState.flow_type)}
            </CardDescription>
          </div>
          <Badge 
            variant="secondary" 
            className={`${getStatusColor(flowState.status)} text-white`}
          >
            <span className="flex items-center gap-1">
              {getStatusIcon(flowState.status)}
              {flowState.status.toUpperCase()}
            </span>
          </Badge>
        </div>
      </CardHeader>
      
      <CardContent className="space-y-4">
        {/* Progress */}
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span>Progresso</span>
            <span>{flowState.current_day}/{totalDays} dias</span>
          </div>
          <Progress value={completionRate} className="h-2" />
        </div>

        {/* Timeline Info */}
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-muted-foreground">
              <Calendar className="h-4 w-4" />
              <span>Início</span>
            </div>
            <p className="font-medium">{formatDate(flowState.enrollment_date)}</p>
          </div>
          
          {flowState.last_message_sent && (
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-muted-foreground">
                <MessageSquare className="h-4 w-4" />
                <span>Última mensagem</span>
              </div>
              <p className="font-medium">{formatDateTime(flowState.last_message_sent)}</p>
            </div>
          )}
        </div>

        {/* State Data */}
        {Object.keys(flowState.state_data).length > 0 && (
          <div className="p-3 bg-muted rounded-lg">
            <div className="text-sm text-muted-foreground mb-2">Dados do Estado</div>
            <div className="space-y-1 text-sm">
              {Object.entries(flowState.state_data).map(([key, value]) => (
                <div key={key} className="flex justify-between">
                  <span className="capitalize">{key.replace('_', ' ')}:</span>
                  <span className="font-medium">{String(value)}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-2 pt-2">
          {flowState.status === FlowStatusEnum.ACTIVE && (
            <>
              <Button 
                variant="outline" 
                size="sm" 
                onClick={operations.pause}
                disabled={isOperationLoading}
                className="flex items-center gap-2"
              >
                {isOperationLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Pause className="h-4 w-4" />
                )}
                Pausar
              </Button>
              <Button 
                variant="outline" 
                size="sm" 
                onClick={() => operations.advance()}
                disabled={isOperationLoading}
                className="flex items-center gap-2"
              >
                <SkipForward className="h-4 w-4" />
                Avançar
              </Button>
            </>
          )}
          
          {flowState.status === FlowStatusEnum.PAUSED && (
            <Button 
              variant="default" 
              size="sm" 
              onClick={operations.resume}
              disabled={isOperationLoading}
              className="flex items-center gap-2"
            >
              {isOperationLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Play className="h-4 w-4" />
              )}
              Retomar
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
