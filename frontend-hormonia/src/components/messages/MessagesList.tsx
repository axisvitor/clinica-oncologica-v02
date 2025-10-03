import React, { useEffect, useRef } from 'react'
import { formatDistanceToNow } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { MessageSquare, Send, Inbox, RefreshCw, Check, CheckCheck, Clock } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { LoadingSpinner } from '../ui/loading-spinner'
import { Button } from '../ui/button'
import { apiClient } from '../../lib/api-client'
import { useToast } from '../ui/use-toast'

interface Message {
  id: string
  patient_id: string
  content: string
  direction: 'inbound' | 'outbound'
  message_type: string
  status: string
  created_at: string
}

interface MessagesListProps {
  messages: Message[]
  isLoading: boolean
  patientName?: string
}

export function MessagesList({ messages, isLoading, patientName }: MessagesListProps) {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const scrollRef = useRef<HTMLDivElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (messages.length > 0 && messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages])

  const retryMutation = useMutation({
    mutationFn: (messageId: string) => apiClient.messages.retry(messageId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['messages'] })
      toast({
        title: 'Mensagem reenviada',
        description: 'A mensagem foi colocada na fila para ser reenviada.',
      })
    },
    onError: (error: any) => {
      toast({
        title: 'Erro ao reenviar',
        description: error.data?.message || 'Ocorreu um erro inesperado.',
        variant: 'destructive'
      })
    }
  })

  const formatTime = (timestamp: string) => {
    try {
      return new Date(timestamp).toLocaleTimeString('pt-BR', {
        hour: '2-digit',
        minute: '2-digit'
      })
    } catch {
      return ''
    }
  }

  const formatDateSeparator = (timestamp: string) => {
    try {
      const date = new Date(timestamp)
      const today = new Date()
      const yesterday = new Date(today)
      yesterday.setDate(yesterday.getDate() - 1)

      if (date.toDateString() === today.toDateString()) {
        return 'Hoje'
      } else if (date.toDateString() === yesterday.toDateString()) {
        return 'Ontem'
      } else {
        return date.toLocaleDateString('pt-BR', {
          day: '2-digit',
          month: 'long',
          year: 'numeric'
        })
      }
    } catch {
      return ''
    }
  }

  const groupMessagesByDate = (messages: Message[]) => {
    const groups: { date: string; messages: Message[] }[] = []
    let currentDate = ''

    messages.forEach((message) => {
      const messageDate = new Date(message.created_at).toDateString()
      if (messageDate !== currentDate) {
        currentDate = messageDate
        groups.push({
          date: message.created_at,
          messages: [message]
        })
      } else {
        const lastGroup = groups[groups.length - 1]
        if (lastGroup) {
          lastGroup.messages.push(message)
        }
      }
    })

    return groups
  }

  const getMessageStatusIcon = (status: string) => {
    switch (status) {
      case 'sent':
        return <Check className="h-3 w-3" />
      case 'delivered':
        return <CheckCheck className="h-3 w-3" />
      case 'read':
        return <CheckCheck className="h-3 w-3 text-blue-400" />
      case 'failed':
        return <span className="text-red-400 text-xs">!</span>
      case 'pending':
        return <Clock className="h-3 w-3 animate-pulse" />
      default:
        return null
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center space-x-2">
          <MessageSquare className="h-5 w-5" />
          <span>Mensagens</span>
          {patientName && (
            <span className="text-sm font-normal text-gray-500">
              - {patientName}
            </span>
          )}
        </CardTitle>
        <CardDescription>
          Histórico de conversas com o paciente
        </CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <LoadingSpinner size="md" />
          </div>
        ) : messages.length === 0 ? (
          <div className="text-center py-8">
            <Inbox className="mx-auto h-12 w-12 text-gray-400 mb-4" />
            <p className="text-gray-500">Nenhuma mensagem encontrada</p>
            <p className="text-sm text-gray-400">
              As mensagens aparecerão aqui quando enviadas
            </p>
          </div>
        ) : (
          <ScrollArea className="h-[350px] md:h-[400px]" ref={scrollRef}>
            <div className="space-y-6 p-2">
              {groupMessagesByDate(messages).map((group, groupIndex) => (
                <div key={groupIndex}>
                  <div className="flex items-center justify-center mb-4">
                    <div className="bg-gray-200 text-gray-600 text-xs font-medium px-3 py-1 rounded-full">
                      {formatDateSeparator(group.date)}
                    </div>
                  </div>
                  <div className="space-y-3">
                    {group.messages.map((message) => (
                      <div
                        key={message.id}
                        className={`flex ${
                          message.direction === 'outbound' ? 'justify-end' : 'justify-start'
                        }`}
                      >
                        <div
                          className={`max-w-xs lg:max-w-md px-4 py-2.5 rounded-2xl shadow-sm ${
                            message.direction === 'outbound'
                              ? 'bg-blue-600 text-white rounded-br-sm'
                              : 'bg-gray-100 text-gray-900 rounded-bl-sm'
                          }`}
                        >
                          <p className="text-sm leading-relaxed break-words">{message.content}</p>
                          <div className="flex items-center justify-end mt-1.5 space-x-1">
                            <span className={`text-xs ${
                              message.direction === 'outbound' ? 'text-white/80' : 'text-gray-500'
                            }`}>
                              {formatTime(message.created_at)}
                            </span>
                            {message.direction === 'outbound' && (
                              <div className="flex items-center space-x-1">
                                {getMessageStatusIcon(message.status)}
                                {message.status === 'failed' && (
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    className="h-5 w-5 p-0 text-white hover:bg-blue-700 ml-1"
                                    onClick={() => retryMutation.mutate(message.id)}
                                    disabled={retryMutation.isPending}
                                    title="Reenviar mensagem"
                                  >
                                    <RefreshCw className="h-3 w-3" />
                                  </Button>
                                )}
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
          </ScrollArea>
        )}
      </CardContent>
    </Card>
  )
}
