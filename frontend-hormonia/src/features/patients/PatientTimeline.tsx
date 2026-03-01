import React from 'react'
import { formatDistanceToNow } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import {
  MessageSquare,
  AlertTriangle,
  Activity,
  FileText,
  Clock
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { LoadingSpinner } from '@/components/ui/loading-spinner'
import type { TimelineEvent } from '@/types/api-responses'

interface PatientTimelineProps {
  timeline?: { events: TimelineEvent[] } | undefined
  isLoading: boolean
}

const FLOW_STATE_LABELS: Record<string, string> = {
  active: 'Ativo',
  paused: 'Pausado',
  completed: 'Concluído',
  cancelled: 'Cancelado',
  onboarding: 'Onboarding',
  inactive: 'Inativo'
}

const STATUS_LABELS: Record<string, string> = {
  success: 'Sucesso',
  failed: 'Falha',
  error: 'Falha',
  completed: 'Concluída',
  pending: 'Pendente',
  running: 'Em andamento'
}

const ACTION_LABELS: Record<string, string> = {
  create_patient: 'Cadastro do paciente',
  start_flow: 'Início do fluxo',
  update_flow: 'Atualização do fluxo'
}

const formatBoolean = (value: boolean) => (value ? 'Sim' : 'Não')

const normalizeText = (value: string) => value.replace(/[_-]+/g, ' ').trim()

const toSentenceCase = (value: string) => {
  if (!value) {
    return value
  }
  return value.charAt(0).toUpperCase() + value.slice(1)
}

const formatEnumValue = (value?: unknown, mapping?: Record<string, string>) => {
  if (value === null || value === undefined) {
    return ''
  }
  const stringValue = String(value)
  if (!stringValue) {
    return ''
  }
  const normalized = normalizeText(stringValue).toLowerCase()
  const mapped = mapping?.[normalized]
  return mapped ?? toSentenceCase(normalizeText(stringValue))
}

const formatDurationSeconds = (value?: unknown) => {
  if (value === null || value === undefined) {
    return ''
  }
  const parsed = typeof value === 'number' ? value : Number(value)
  if (Number.isNaN(parsed)) {
    return String(value)
  }
  if (parsed >= 3600) {
    const hours = Math.floor(parsed / 3600)
    const minutes = Math.round((parsed % 3600) / 60)
    return minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`
  }
  if (parsed >= 60) {
    const minutes = Math.floor(parsed / 60)
    const seconds = Math.round(parsed % 60)
    return seconds > 0 ? `${minutes}m ${seconds}s` : `${minutes}m`
  }
  const rounded = parsed < 10 ? parsed.toFixed(1) : Math.round(parsed).toString()
  return `${rounded.replace('.', ',')} s`
}

const formatIdentifier = (value?: unknown) => {
  if (value === null || value === undefined) {
    return ''
  }
  const stringValue = String(value)
  if (stringValue.length <= 12) {
    return stringValue
  }
  return `${stringValue.slice(0, 8)}…${stringValue.slice(-4)}`
}

const formatEventDescription = (event: TimelineEvent) => {
  const metadata = event.metadata ?? {}
  if (metadata['flow_state']) {
    return `Estado atual do fluxo: ${formatEnumValue(metadata['flow_state'], FLOW_STATE_LABELS)}`
  }
  if (metadata['action'] || metadata['step']) {
    const step = metadata['step']
    const action = metadata['action']
    const status = metadata['status']
    const stepLabel = step !== undefined ? `Etapa ${step}` : 'Etapa'
    const actionLabel = action ? formatEnumValue(action, ACTION_LABELS) : ''
    const statusLabel = status ? formatEnumValue(status, STATUS_LABELS) : ''
    const parts = [stepLabel, actionLabel].filter(Boolean)
    const detail = parts.join(': ')
    return statusLabel ? `${detail} (${statusLabel})` : detail
  }
  return event.description ?? ''
}

const formatMetadataEntries = (event: TimelineEvent) => {
  const metadata = event.metadata ?? {}
  const suppressedKeys = new Set<string>(['timestamp', 'created_at', 'date'])
  if (metadata['flow_state']) {
    suppressedKeys.add('flow_state')
  }
  if (metadata['action'] || metadata['step']) {
    suppressedKeys.add('action')
    suppressedKeys.add('step')
    suppressedKeys.add('status')
  }
  const entries = Object.entries(metadata).filter(([key]) => !suppressedKeys.has(key))
  const results: Array<{ label: string; value: string; title?: string }> = []

  for (const [key, value] of entries) {
    if (value === null || value === undefined || value === '') {
      continue
    }

    switch (key) {
      case 'error_type': {
        results.push({
          label: 'Erro',
          value: formatEnumValue(value)
        })
        break
      }
      case 'error_message': {
        results.push({
          label: 'Mensagem',
          value: String(value)
        })
        break
      }
      case 'retry_count': {
        results.push({
          label: 'Tentativas',
          value: String(value)
        })
        break
      }
      case 'flow_state': {
        results.push({
          label: 'Fluxo',
          value: formatEnumValue(value, FLOW_STATE_LABELS)
        })
        break
      }
      case 'status': {
        results.push({
          label: 'Status',
          value: formatEnumValue(value, STATUS_LABELS)
        })
        break
      }
      case 'duration_seconds': {
        results.push({
          label: 'Duração',
          value: formatDurationSeconds(value)
        })
        break
      }
      case 'saga_id': {
        const fullId = String(value)
        results.push({
          label: 'Saga',
          value: formatIdentifier(fullId),
          title: fullId
        })
        break
      }
      case 'doctor_id': {
        results.push({
          label: 'Médico',
          value: formatIdentifier(value)
        })
        break
      }
      case 'archived_by': {
        results.push({
          label: 'Arquivado por',
          value: formatIdentifier(value)
        })
        break
      }
      case 'treatment_type': {
        results.push({
          label: 'Tratamento',
          value: String(value)
        })
        break
      }
      case 'action': {
        results.push({
          label: 'Ação',
          value: formatEnumValue(value, ACTION_LABELS)
        })
        break
      }
      case 'step': {
        results.push({
          label: 'Etapa',
          value: String(value)
        })
        break
      }
      default: {
        if (typeof value === 'boolean') {
          results.push({
            label: toSentenceCase(normalizeText(key)),
            value: formatBoolean(value)
          })
          break
        }
        if (key.endsWith('_id')) {
          results.push({
            label: toSentenceCase(normalizeText(key.replace(/_id$/, ''))),
            value: formatIdentifier(value),
            title: String(value)
          })
          break
        }
        results.push({
          label: toSentenceCase(normalizeText(key)),
          value: String(value)
        })
        break
      }
    }
  }

  return results
}

export function PatientTimeline({ timeline, isLoading }: PatientTimelineProps) {
  const formatEventDate = (value?: string) => {
    if (!value) {
      return 'Data indisponível'
    }
    const normalized = value.replace(/(\.\d{3})\d+/, '$1')
    const date = new Date(normalized)
    if (Number.isNaN(date.getTime())) {
      return 'Data indisponível'
    }
    return formatDistanceToNow(date, {
      addSuffix: true,
      locale: ptBR
    })
  }

  const getEventIcon = (type: string) => {
    switch (type) {
      case 'message':
        return MessageSquare
      case 'quiz':
        return FileText
      case 'alert':
        return AlertTriangle
      case 'flow_change':
        return Activity
      case 'report':
        return FileText
      default:
        return Clock
    }
  }

  const getEventColor = (type: string) => {
    switch (type) {
      case 'message':
        return 'text-blue-600 bg-blue-100'
      case 'quiz':
        return 'text-purple-600 bg-purple-100'
      case 'alert':
        return 'text-red-600 bg-red-100'
      case 'flow_change':
        return 'text-green-600 bg-green-100'
      case 'report':
        return 'text-orange-600 bg-orange-100'
      default:
        return 'text-gray-600 bg-gray-100'
    }
  }

  const getEventLabel = (type: string) => {
    switch (type) {
      case 'message':
        return 'Mensagem'
      case 'quiz':
        return 'Questionário'
      case 'alert':
        return 'Alerta'
      case 'flow_change':
        return 'Fluxo do tratamento'
      case 'report':
        return 'Relatório'
      default:
        return 'Evento'
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Linha do Tempo do Paciente</CardTitle>
        <CardDescription>
          Registro das principais atividades e eventos
        </CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <LoadingSpinner size="md" />
          </div>
        ) : !timeline?.events || timeline.events.length === 0 ? (
          <div className="text-center py-8">
            <Clock className="mx-auto h-12 w-12 text-gray-400 mb-4" aria-hidden="true" />
            <p className="text-gray-500">Nenhum evento registrado</p>
            <p className="text-sm text-gray-400">
              Os eventos aparecerão aqui conforme o paciente interage com o sistema
            </p>
          </div>
        ) : (
          <ScrollArea className="h-[500px]">
            <div className="space-y-4">
              {timeline.events.map((event, index) => {
                const Icon = getEventIcon(event.event_type)
                const colorClass = getEventColor(event.event_type)
                const isLast = index === timeline.events.length - 1
                const description = formatEventDescription(event)
                const metadataEntries = formatMetadataEntries(event)

                return (
                  <div key={event.id ?? `timeline-event-${index}`} className="relative">
                    {/* Timeline line */}
                    {!isLast && (
                      <div className="absolute left-4 top-8 w-0.5 h-full bg-gray-200" />
                    )}

                    <div className="flex items-start space-x-3">
                      <div className={`flex items-center justify-center w-8 h-8 rounded-full ${colorClass} relative z-10`}>
                        <Icon className="w-4 h-4" aria-hidden="true" />
                      </div>

                      <div className="flex-1 min-w-0 pb-4">
                        <div className="flex items-center justify-between mb-1">
                          <h4 className="text-sm font-medium text-gray-900">
                            {event.title}
                          </h4>
                          <div className="flex items-center space-x-2">
                            <Badge variant="outline" className="text-xs">
                              {getEventLabel(event.event_type)}
                            </Badge>
                            <span className="text-xs text-gray-500">
                              {formatEventDate(event.created_at)}
                            </span>
                          </div>
                        </div>

                        {description && (
                          <p className="text-sm text-gray-600 break-words">
                            {description}
                          </p>
                        )}

                        {metadataEntries.length > 0 && (
                          <div className="mt-2 flex flex-wrap gap-2 text-xs text-gray-500">
                            {metadataEntries.map(({ label, value, title }) => (
                              <span
                                key={`${event.id}-${label}-${value}`}
                                className="inline-flex items-center gap-1 rounded-full bg-gray-50 px-2 py-0.5 text-gray-600"
                                title={title}
                              >
                                <span className="font-medium text-gray-700">{label}:</span>
                                <span className="break-words">{value}</span>
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </ScrollArea>
        )}
      </CardContent>
    </Card>
  )
}
