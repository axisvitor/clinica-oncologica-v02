import React, { useState, useRef, useEffect } from 'react'
import { Send, Bot, User, Loader2, AlertTriangle } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { useToast } from '@/components/ui/use-toast'
import { AIChatMessage as ChatMessage, ChatRole, ChatSession } from '@/types/api'
import { apiClient } from '../../lib/api-client'
import { FEATURES } from '../../config'
import { createLogger } from '@/lib/logger'
import { toReactNode, toReactString, isNumber } from '@/lib/utils/type-guards'

const logger = createLogger('AIChatInterface')

interface AIChatInterfaceProps {
  patientId?: string
  sessionId?: string
  onSessionChange?: (session: ChatSession) => void
  className?: string
}

export function AIChatInterface({ 
  patientId, 
  sessionId, 
  onSessionChange,
  className 
}: AIChatInterfaceProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [session, setSession] = useState<ChatSession | null>(null)
  const { toast } = useToast()
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Scroll to bottom when new messages arrive
  useEffect(() => {
    if (FEATURES.AI_CHAT) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages])

  // Focus input on mount
  useEffect(() => {
    if (FEATURES.AI_CHAT) {
      inputRef.current?.focus()
    }
  }, [])

  // Initialize session
  useEffect(() => {
    if (!FEATURES.AI_CHAT) return
    if (sessionId) {
      loadSession(sessionId)
    } else {
      createNewSession()
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps -- loadSession and createNewSession are stable functions
  }, [sessionId, patientId])

  // Check if AI features are enabled
  if (!FEATURES.AI_CHAT) {
    return (
      <Card className={className}>
        <CardContent className="pt-6">
          <div className="text-center text-muted-foreground">
            <Bot className="mx-auto h-8 w-8 mb-2" />
            <p>Chat com IA não disponível</p>
            <p className="text-sm">Configure VITE_OPENAI_API_KEY para habilitar</p>
          </div>
        </CardContent>
      </Card>
    )
  }

  const loadSession = async (id: string) => {
    try {
      // In a real implementation, load from API
      // const sessionData = await apiClient.ai.getSession(id)
      // setSession(sessionData)
      // setMessages(sessionData.messages)
      
      // Mock session for demo
      const mockSession: ChatSession = {
        id,
        patient_id: patientId || "",
        user_id: 'current-user',
        title: 'Chat com IA',
        messages: [],
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        status: 'active'
      }
      setSession(mockSession)
      setMessages([])
    } catch (error) {
      logger.error('Failed to load session:', error)
      toast({
        title: 'Erro',
        description: 'Não foi possível carregar a sessão de chat',
        variant: 'destructive'
      })
    }
  }

  const createNewSession = async () => {
    try {
      const newSession: ChatSession = {
        id: `session-${Date.now()}`,
        patient_id: patientId || "",
        user_id: 'current-user',
        title: patientId ? `Chat - Paciente ${patientId}` : 'Chat com IA',
        messages: [],
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        status: 'active'
      }
      
      setSession(newSession)
      setMessages([])
      onSessionChange?.(newSession)
      
      // Add welcome message
      const welcomeMessage: ChatMessage = {
        id: `msg-${Date.now()}`,
        role: ChatRole.ASSISTANT,
        content: patientId
          ? `Olá! Sou a IA assistente da Hormonia. Como posso ajudar com o paciente ${patientId}?`
          : 'Olá! Sou a IA assistente da Hormonia. Como posso ajudá-lo hoje?',
        timestamp: new Date().toISOString(),
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        ...(patientId && { patient_id: patientId })
      }

      setMessages([welcomeMessage])
    } catch (error) {
      logger.error('Failed to create session:', error)
    }
  }

  const sendMessage = async () => {
    if (!inputValue.trim() || isLoading) return

    const userMessage: ChatMessage = {
      id: `msg-${Date.now()}`,
      role: ChatRole.USER,
      content: inputValue.trim(),
      timestamp: new Date().toISOString(),
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      ...(patientId && { patient_id: patientId })
    }

    setMessages(prev => [...prev, userMessage])
    setInputValue('')
    setIsLoading(true)

    try {
      // Build context for AI
      const context = {
        patient_id: patientId || "",
        session_id: session?.id,
        conversation_history: messages.slice(-10) // Last 10 messages for context
      }

      // Mock response for demo when API is not available
      interface AIResponse {
        message: string
        confidence?: number
        intent?: string
        suggestions?: string[]
        requires_human_review?: boolean
      }

      let response: AIResponse
      try {
        // Define API response structure
        interface AIChatApiResponse {
          message?: string;
          response?: string;
          confidence?: number;
          intent?: string;
          suggestions?: string[];
          requires_human_review?: boolean;
        }
        const apiResponse = await apiClient.ai.chat(userMessage.content, context) as AIChatApiResponse
        response = {
          message: apiResponse.message || apiResponse.response || 'Resposta da IA',
          confidence: apiResponse.confidence,
          intent: apiResponse.intent,
          suggestions: apiResponse.suggestions,
          requires_human_review: apiResponse.requires_human_review
        }
      } catch {
        // Fallback to mock response
        response = {
          message: `Entendi sua mensagem: "${userMessage.content}". Esta é uma resposta simulada da IA. Configure a API do OpenAI para respostas reais.`,
          confidence: 0.85,
          intent: 'general_inquiry',
          suggestions: ['Como posso ajudar mais?', 'Precisa de informações específicas?'],
          requires_human_review: false
        }
      }
      
      const assistantMessage: ChatMessage = {
        id: `msg-${Date.now() + 1}`,
        role: ChatRole.ASSISTANT,
        content: response.message || 'Desculpe, não consegui processar sua mensagem.',
        timestamp: new Date().toISOString(),
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        ...(patientId && { patient_id: patientId }),
        metadata: {
          confidence: response.confidence,
          ...(response.intent && { intent: response.intent }),
          ...(response.requires_human_review && { requires_review: response.requires_human_review })
        }
      }

      setMessages(prev => [...prev, assistantMessage])

      // Show suggestions if available
      if (response.suggestions && response.suggestions.length > 0) {
        toast({
          title: 'Sugestões',
          description: response.suggestions.join(', ')
        })
      }

      // Alert if human review is needed
      if (response.requires_human_review) {
        toast({
          title: 'Revisão Necessária',
          description: 'Esta resposta pode precisar de revisão humana',
          variant: 'destructive'
        })
      }

    } catch (error) {
      logger.error('Failed to send message:', error)

      const errorMessage: ChatMessage = {
        id: `msg-${Date.now() + 1}`,
        role: ChatRole.ASSISTANT,
        content: 'Desculpe, ocorreu um erro ao processar sua mensagem. Tente novamente.',
        timestamp: new Date().toISOString(),
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        ...(patientId && { patient_id: patientId })
      }
      
      setMessages(prev => [...prev, errorMessage])
      
      toast({
        title: 'Erro',
        description: 'Não foi possível enviar a mensagem',
        variant: 'destructive'
      })
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const formatTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString('pt-BR', {
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const getMessageIcon = (role: ChatMessage['role']) => {
    switch (role) {
      case ChatRole.ASSISTANT:
        return <Bot className="h-4 w-4" />
      case ChatRole.USER:
        return <User className="h-4 w-4" />
      default:
        return null
    }
  }

  const getConfidenceBadge = (confidence?: number) => {
    if (!confidence) return null
    
    const variant = confidence > 0.8 ? 'default' : confidence > 0.6 ? 'secondary' : 'destructive'
    return (
      <Badge variant={variant} className="text-xs">
        {Math.round(confidence * 100)}%
      </Badge>
    )
  }

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Bot className="h-5 w-5" />
          Chat com IA
          {patientId && (
            <Badge variant="outline">Paciente: {patientId}</Badge>
          )}
        </CardTitle>
      </CardHeader>
      
      <CardContent className="p-0">
        <ScrollArea className="h-96 p-4">
          <div className="space-y-4">
            {messages.map((message) => (
              <div
                key={message.id}
                className={`flex gap-3 ${
                  message.role === ChatRole.USER ? 'justify-end' : 'justify-start'
                }`}
              >
                {message.role !== ChatRole.USER && (
                  <div className="flex-shrink-0">
                    <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                      {getMessageIcon(message.role)}
                    </div>
                  </div>
                )}
                
                <div className={`max-w-[80%] ${message.role === ChatRole.USER ? 'order-first' : ''}`}>
                  <div
                    className={`rounded-lg p-3 ${
                      message.role === ChatRole.USER
                        ? 'bg-primary text-primary-foreground ml-auto'
                        : 'bg-muted'
                    }`}
                  >
                    <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                  </div>
                  
                  <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
                    <span>{formatTime(message.timestamp)}</span>
                    {message.metadata?.['confidence'] != null &&
                     isNumber(message.metadata['confidence']) &&
                     toReactNode(getConfidenceBadge(message.metadata['confidence']))}

                    {message.metadata?.['requires_review'] != null && (
                      <AlertTriangle className="h-3 w-3 text-yellow-500" />
                    )}
                    {message.metadata?.['intent'] != null && (
                      <Badge variant="outline" className="text-xs">
                        {toReactString(message.metadata['intent'], 'unknown')}
                      </Badge>
                    )}
                  </div>
                </div>
                
                {message.role === ChatRole.USER && (
                  <div className="flex-shrink-0">
                    <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                      {getMessageIcon(message.role)}
                    </div>
                  </div>
                )}
              </div>
            ))}
            
            {isLoading && (
              <div className="flex gap-3 justify-start">
                <div className="flex-shrink-0">
                  <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                    <Bot className="h-4 w-4" />
                  </div>
                </div>
                <div className="bg-muted rounded-lg p-3">
                  <div className="flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span className="text-sm text-muted-foreground">Pensando...</span>
                  </div>
                </div>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </div>
        </ScrollArea>
        
        <Separator />
        
        <div className="p-4">
          <div className="flex gap-2">
            <Input
              ref={inputRef}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Digite sua mensagem..."
              disabled={isLoading}
              className="flex-1"
            />
            <Button
              onClick={sendMessage}
              disabled={!inputValue.trim() || isLoading}
              size="icon"
            >
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
