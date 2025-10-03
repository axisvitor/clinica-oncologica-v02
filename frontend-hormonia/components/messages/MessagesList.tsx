import React from 'react'
import { formatDistanceToNow } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { MessageSquare, Send, Inbox, RefreshCw } from 'lucide-react'
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

  const getMessageStatusBadge = (status: string) => {
    switch (status) {
      case 'sent':
        return <Badge className="bg-blue-100 text-blue-800">Enviada</Badge>
      case 'delivered':
        return <Badge className="bg-green-100 text-green-800">Entregue</Badge>
      case 'read':
        return <Badge className="bg-green-100 text-green-800">Lida</Badge>
      case 'failed':
        return <Badge className="bg-red-100 text-red-800">Falhou</Badge>
      case 'pending':
        return <Badge className="bg-yellow-100 text-yellow-800">Pendente</Badge>
      default:
        return <Badge variant="outline">{status}</Badge>
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
          <ScrollArea className="h-[400px]">
            <div className="space-y-4">
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={`flex ${
                    message.direction === 'outbound' ? 'justify-end' : 'justify-start'
                  }`}
                >
                  <div
                    className={`max-w-xs lg:max-w-md px-4 py-3 rounded-lg ${
                      message.direction === 'outbound'
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-100 text-gray-900'
                    }`}
                  >
                    <p className="text-sm">{message.content}</p>
                    <div className="flex items-center justify-between mt-2">
                      <span className="text-xs opacity-75">
                        {formatTime(message.created_at)}
                      </span>
                      {message.direction === 'outbound' && (
                        <div className="ml-2 flex items-center space-x-2">
                          {getMessageStatusBadge(message.status)}
                          {message.status === 'failed' && (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-6 w-6 p-0 text-white hover:bg-blue-700"
                              onClick={() => retryMutation.mutate(message.id)}
                              disabled={retryMutation.isPending}
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
          </ScrollArea>
        )}
      </CardContent>
    </Card>
  )
}
