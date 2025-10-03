import React, { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Send, Loader2 } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { useToast } from '@/components/ui/use-toast'
import { apiClient } from '@/lib/api-client'

interface SendQuizLinkModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  patientId: string
  patientName: string
  onSuccess?: () => void
}

export function SendQuizLinkModal({
  open,
  onOpenChange,
  patientId,
  patientName,
  onSuccess
}: SendQuizLinkModalProps) {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [templateId, setTemplateId] = useState('')
  const [deliveryMethod, setDeliveryMethod] = useState<'whatsapp' | 'email' | 'sms'>('whatsapp')
  const [validityHours, setValidityHours] = useState('72')
  const [customMessage, setCustomMessage] = useState('')

  // Fetch quiz templates
  const { data: templatesData, isLoading: isLoadingTemplates } = useQuery({
    queryKey: ['quiz-templates'],
    queryFn: () => apiClient.quiz.templates(),
    enabled: open
  })

  const templates = templatesData?.items || []

  const sendLinkMutation = useMutation({
    mutationFn: (data: {
      patient_id: string
      quiz_template_id: string
      delivery_method: string
      expiry_hours: number
      custom_message?: string
    }) => apiClient.monthlyQuiz.createLink(data),
    onSuccess: () => {
      toast({
        title: 'Link enviado com sucesso',
        description: `Link do quiz mensal enviado para ${patientName}`
      })
      queryClient.invalidateQueries({ queryKey: ['monthly-quiz-status', patientId] })
      queryClient.invalidateQueries({ queryKey: ['patients'] })
      onSuccess?.()
      handleClose()
    },
    onError: (error: any) => {
      toast({
        title: 'Erro ao enviar link',
        description: error.data?.message || 'Ocorreu um erro ao enviar o link do quiz',
        variant: 'destructive'
      })
    }
  })

  const handleClose = () => {
    setTemplateId('')
    setDeliveryMethod('whatsapp')
    setValidityHours('72')
    setCustomMessage('')
    onOpenChange(false)
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    if (!templateId) {
      toast({
        title: 'Template obrigatório',
        description: 'Por favor, selecione um template de quiz',
        variant: 'destructive'
      })
      return
    }

    sendLinkMutation.mutate({
      patient_id: patientId,
      quiz_template_id: templateId,
      delivery_method: deliveryMethod,
      expiry_hours: parseInt(validityHours, 10),
      ...(customMessage ? { custom_message: customMessage } : {})
    })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>Enviar Link do Quiz Mensal</DialogTitle>
          <DialogDescription>
            Enviar link do quiz mensal para {patientName}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="template">Template do Quiz *</Label>
            <Select value={templateId} onValueChange={setTemplateId} disabled={isLoadingTemplates}>
              <SelectTrigger id="template">
                <SelectValue placeholder="Selecione um template" />
              </SelectTrigger>
              <SelectContent>
                {isLoadingTemplates ? (
                  <SelectItem value="loading" disabled>
                    Carregando...
                  </SelectItem>
                ) : templates.length === 0 ? (
                  <SelectItem value="empty" disabled>
                    Nenhum template disponível
                  </SelectItem>
                ) : (
                  templates.map((template: any) => (
                    <SelectItem key={template.id} value={template.id}>
                      {template.name} (v{template.version})
                    </SelectItem>
                  ))
                )}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="delivery">Método de Entrega *</Label>
            <Select value={deliveryMethod} onValueChange={(value: any) => setDeliveryMethod(value)}>
              <SelectTrigger id="delivery">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="whatsapp">WhatsApp</SelectItem>
                <SelectItem value="email">Email</SelectItem>
                <SelectItem value="sms">SMS</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="validity">Validade (horas) *</Label>
            <Input
              id="validity"
              type="number"
              min="1"
              max="168"
              value={validityHours}
              onChange={(e) => setValidityHours(e.target.value)}
              placeholder="72"
            />
            <p className="text-xs text-gray-500">
              O link expira após {validityHours} horas (padrão: 72 horas)
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="message">Mensagem Personalizada (opcional)</Label>
            <Textarea
              id="message"
              value={customMessage}
              onChange={(e) => setCustomMessage(e.target.value)}
              placeholder="Adicione uma mensagem personalizada..."
              rows={3}
            />
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={handleClose}
              disabled={sendLinkMutation.isPending}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={sendLinkMutation.isPending || !templateId}>
              {sendLinkMutation.isPending ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Enviando...
                </>
              ) : (
                <>
                  <Send className="mr-2 h-4 w-4" />
                  Enviar
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}