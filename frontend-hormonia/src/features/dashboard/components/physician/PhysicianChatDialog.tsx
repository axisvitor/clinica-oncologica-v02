import React from 'react'
import { Brain, MessageSquare } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { LoadingSpinner } from '@/components/ui/loading-spinner'
import { ChatRole } from '@/types/api'
import type { AIChatMessage as ChatMessage } from '@/types/api'

interface PhysicianChatDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  messages: ChatMessage[]
  inputValue: string
  onInputChange: (value: string) => void
  onSend: () => void
  isPending: boolean
}

export function PhysicianChatDialog({
  open,
  onOpenChange,
  messages,
  inputValue,
  onInputChange,
  onSend,
  isPending,
}: PhysicianChatDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[80vh]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Brain className="h-5 w-5" />
            Chat com IA - Orientação Clínica
          </DialogTitle>
          <DialogDescription>Obtenha orientações clínicas baseadas em IA</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col h-[60vh]">
          {/* Chat Messages */}
          <div className="flex-1 overflow-y-auto space-y-3 p-4 border rounded-md mb-4">
            {messages.length === 0 ? (
              <div className="text-center text-muted-foreground py-8">
                <MessageSquare className="mx-auto h-8 w-8 mb-2" />
                <p>Inicie uma conversa com a IA</p>
                <p className="text-xs mt-1">
                  Faça perguntas sobre pacientes, tratamentos ou análises
                </p>
              </div>
            ) : (
              messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex ${msg.role === ChatRole.USER ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[80%] rounded-lg p-3 ${
                      msg.role === ChatRole.USER ? 'bg-primary text-primary-foreground' : 'bg-muted'
                    }`}
                  >
                    <p className="text-sm">{msg.content}</p>
                    <p className="text-xs opacity-70 mt-1">
                      {new Date(msg.timestamp).toLocaleTimeString('pt-BR')}
                    </p>
                  </div>
                </div>
              ))
            )}
            {isPending && (
              <div className="flex justify-start">
                <div className="bg-muted rounded-lg p-3">
                  <LoadingSpinner size="sm" />
                </div>
              </div>
            )}
          </div>

          {/* Chat Input */}
          <div className="flex gap-2">
            <Input
              placeholder="Digite sua pergunta..."
              value={inputValue}
              onChange={(e) => onInputChange(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && onSend()}
              disabled={isPending}
            />
            <Button onClick={onSend} disabled={!inputValue.trim() || isPending}>
              <MessageSquare className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
