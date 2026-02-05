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

export function PatientTimeline({ timeline, isLoading }: PatientTimelineProps) {
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
        return 'Fluxo'
      case 'report':
        return 'Relatório'
      default:
        return 'Evento'
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Timeline do Paciente</CardTitle>
        <CardDescription>
          Histórico de atividades e eventos
        </CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <LoadingSpinner size="md" />
          </div>
        ) : !timeline?.events || timeline.events.length === 0 ? (
          <div className="text-center py-8">
            <Clock className="mx-auto h-12 w-12 text-gray-400 mb-4" />
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

                return (
                  <div key={event.id ?? `timeline-event-${index}`} className="relative">
                    {/* Timeline line */}
                    {!isLast && (
                      <div className="absolute left-4 top-8 w-0.5 h-full bg-gray-200" />
                    )}

                    <div className="flex items-start space-x-3">
                      <div className={`flex items-center justify-center w-8 h-8 rounded-full ${colorClass} relative z-10`}>
                        <Icon className="w-4 h-4" />
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
                              {(() => {
                                try {
                                  const date = new Date(event.created_at)
                                  if (isNaN(date.getTime())) {
                                    return 'Data inválida'
                                  }
                                  return formatDistanceToNow(date, {
                                    addSuffix: true,
                                    locale: ptBR
                                  })
                                } catch {
                                  return 'Data inválida'
                                }
                              })()}
                            </span>
                          </div>
                        </div>

                        <p className="text-sm text-gray-600">
                          {event.description}
                        </p>

                        {event.metadata && Object.keys(event.metadata).length > 0 && (
                          <div className="mt-2 text-xs text-gray-500">
                            {Object.entries(event.metadata).map(([key, value]) => (
                              <div key={key}>
                                <strong>{key}:</strong> {String(value)}
                              </div>
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
