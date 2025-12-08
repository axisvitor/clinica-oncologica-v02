import React, { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Send, Paperclip, Smile, Calendar } from 'lucide-react'
import { apiClient } from '../../lib/api-client'
import { MessageType } from '@/types/api'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { useToast } from '@/components/ui/use-toast'
import { LoadingSpinner } from '@/components/ui/loading-spinner'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { getErrorMessage } from '@/lib/utils/type-guards'

interface MessageComposerProps {
  patientId: string
  patientName: string
  onMessageSent?: () => void
}

export function MessageComposer({ patientId, patientName, onMessageSent }: MessageComposerProps) {
  const [message, setMessage] = useState('')
  const [messageType, setMessageType] = useState<MessageType>(MessageType.TEXT)
  const [scheduledFor, setScheduledFor] = useState('')
  const [showTemplates, setShowTemplates] = useState(false)
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const textareaRef = React.useRef<HTMLTextAreaElement>(null)

  const MAX_CHARS = 1000

  const sendMessageMutation = useMutation({
    mutationFn: (data: { patient_id: string; content: string; type?: MessageType; scheduled_for?: string }) =>
      apiClient.messages.send(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['messages'] })
      toast({
        title: 'Mensagem enviada',
        description: 'A mensagem foi enviada com sucesso.',
      })
      setMessage('')
      setScheduledFor('')
      onMessageSent?.()
    },
    onError: (error: unknown) => {
      toast({
        title: 'Erro ao enviar mensagem',
        description: getErrorMessage(error) || 'Ocorreu um erro inesperado.',
        variant: 'destructive'
      })
    }
  })

  const handleSend = () => {
    if (!message.trim()) {
      toast({
        title: 'Mensagem vazia',
        description: 'Digite uma mensagem antes de enviar.',
        variant: 'destructive'
      })
      return
    }

    sendMessageMutation.mutate({
      patient_id: patientId,
      content: message.trim(),
      type: messageType,
      // Default to current time if no schedule is provided (backend requires this field)
      scheduled_for: scheduledFor && scheduledFor.trim() ? scheduledFor : new Date().toISOString()
    })
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey && e.ctrlKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const applyTemplate = (content: string) => {
    setMessage(content)
    setShowTemplates(false)
    textareaRef.current?.focus()
  }

  const messageTemplates = [
    {
      label: 'Lembrete de medicação',
      content: 'Olá! Este é um lembrete para tomar sua medicação conforme prescrito. Lembre-se de seguir as orientações médicas.'
    },
    {
      label: 'Agendamento de consulta',
      content: 'Gostaríamos de agendar sua próxima consulta. Por favor, entre em contato para marcarmos um horário conveniente.'
    },
    {
      label: 'Questionário disponível',
      content: 'Há um novo questionário disponível para você. Por favor, acesse o sistema para respondê-lo.'
    },
    {
      label: 'Resultados de exames',
      content: 'Seus resultados de exames estão prontos. Agende uma consulta para discutirmos os resultados.'
    }
  ]

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Enviar Mensagem</CardTitle>
          <Badge variant="outline">{patientName}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Message Type */}
        <div className="flex items-center space-x-4">
          <label className="text-sm font-medium">Tipo:</label>
          <Select value={messageType} onValueChange={(value) => setMessageType(value as MessageType)}>
            <SelectTrigger className="w-[150px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={MessageType.TEXT}>Texto</SelectItem>
              <SelectItem value={MessageType.TEMPLATE}>Lembrete</SelectItem>
              <SelectItem value={MessageType.INTERACTIVE}>Agendamento</SelectItem>
              <SelectItem value={MessageType.TEXT}>Educativo</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Quick Templates Toggle */}
        <div className="flex items-center justify-between">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setShowTemplates(!showTemplates)}
            className="text-blue-600"
          >
            {showTemplates ? 'Ocultar' : 'Mostrar'} Templates
          </Button>
        </div>

        {/* Quick Templates */}
        {showTemplates && (
          <div className="space-y-2 border-t pt-3">
            <label className="text-sm font-medium text-gray-700">Templates rápidos:</label>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              {messageTemplates.map((template, index) => (
                <Button
                  key={index}
                  type="button"
                  variant="outline"
                  size="sm"
                  className="justify-start text-left h-auto p-3 hover:bg-blue-50 hover:border-blue-300 transition-colors"
                  onClick={() => applyTemplate(template.content)}
                >
                  <div className="w-full">
                    <p className="font-medium text-xs text-gray-900 mb-1">{template.label}</p>
                    <p className="text-xs text-gray-500 line-clamp-2">
                      {template.content}
                    </p>
                  </div>
                </Button>
              ))}
            </div>
          </div>
        )}

        {/* Message Input */}
        <div className="space-y-2">
          <label className="text-sm font-medium">Mensagem:</label>
          <Textarea
            ref={textareaRef}
            placeholder="Digite sua mensagem aqui... (Ctrl+Enter para enviar)"
            value={message}
            onChange={(e) => {
              if (e.target.value.length <= MAX_CHARS) {
                setMessage(e.target.value)
              }
            }}
            onKeyDown={handleKeyPress}
            rows={5}
            className="resize-none focus:ring-2 focus:ring-blue-500"
            maxLength={MAX_CHARS}
          />
          <div className="flex items-center justify-between">
            <span className={`text-xs ${message.length > MAX_CHARS * 0.9 ? 'text-orange-500 font-medium' : 'text-gray-500'
              }`}>
              {message.length}/{MAX_CHARS} caracteres
            </span>
            <span className="text-xs text-gray-400">
              Ctrl+Enter para enviar
            </span>
          </div>
        </div>

        {/* Scheduling */}
        <div className="space-y-2">
          <label className="text-sm font-medium flex items-center">
            <Calendar className="mr-2 h-4 w-4" />
            Agendar envio (opcional)
          </label>
          <Input
            type="datetime-local"
            value={scheduledFor}
            onChange={(e) => setScheduledFor(e.target.value)}
          />
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between pt-2 border-t">
          <div className="flex items-center space-x-2">
            <Button variant="ghost" size="sm" disabled title="Em breve">
              <Paperclip className="h-4 w-4 text-gray-400" />
            </Button>
            <Button variant="ghost" size="sm" disabled title="Em breve">
              <Smile className="h-4 w-4 text-gray-400" />
            </Button>
          </div>

          <div className="flex items-center space-x-2">
            {message.trim() && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  setMessage('')
                  textareaRef.current?.focus()
                }}
                className="text-gray-500 hover:text-gray-700"
              >
                Limpar
              </Button>
            )}
            <Button
              onClick={handleSend}
              disabled={sendMessageMutation.isPending || !message.trim()}
              className="min-w-[120px]"
            >
              {sendMessageMutation.isPending ? (
                <>
                  <LoadingSpinner size="sm" className="mr-2" />
                  Enviando...
                </>
              ) : (
                <>
                  <Send className="mr-2 h-4 w-4" />
                  {scheduledFor ? 'Agendar' : 'Enviar'}
                </>
              )}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
