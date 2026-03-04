import { useState, useCallback } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useToast } from '@/hooks/use-toast'
import { apiClient } from '@/lib/api-client'
import { SendMessageData, MessageFormState } from '../types'

export function useMessageForm(selectedInstance: string) {
  const { toast } = useToast()
  const queryClient = useQueryClient()

  const [formState, setFormState] = useState<MessageFormState>({
    to: '',
    text: '',
    mediaFile: null,
    mediaCaption: '',
  })

  const sendMessageMutation = useMutation({
    mutationFn: (messageData: SendMessageData) =>
      apiClient.request('/api/v2/whatsapp/messages', {
        method: 'POST',
        body: JSON.stringify(messageData),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['whatsapp-recent-messages'] })
      queryClient.invalidateQueries({ queryKey: ['whatsapp-message-stats'] })
      toast({ title: 'Message sent successfully' })
      setFormState({ to: '', text: '', mediaFile: null, mediaCaption: '' })
    },
    onError: (error: unknown) => {
      const errorMessage = error instanceof Error ? error.message : 'Failed to send message'
      toast({
        title: 'Failed to send message',
        description: errorMessage,
        variant: 'destructive',
      })
    },
  })

  const handleFileUpload = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0]
      if (file) {
        const maxSize = 16 * 1024 * 1024 // 16MB
        if (file.size > maxSize) {
          toast({
            title: 'File too large',
            description: 'Maximum file size is 16MB',
            variant: 'destructive',
          })
          return
        }
        setFormState((prev) => ({ ...prev, mediaFile: file }))
      }
    },
    [toast]
  )

  const handleFormChange = useCallback((updates: Partial<MessageFormState>) => {
    setFormState((prev) => ({ ...prev, ...updates }))
  }, [])

  const handleSendMessage = useCallback(() => {
    if (!selectedInstance) {
      toast({
        title: 'No instance selected',
        description: 'Please select a WhatsApp instance first',
        variant: 'destructive',
      })
      return
    }

    if (!formState.to.trim()) {
      toast({
        title: 'Phone number required',
        description: 'Please enter a recipient phone number',
        variant: 'destructive',
      })
      return
    }

    if (!formState.text.trim() && !formState.mediaFile) {
      toast({
        title: 'Message content required',
        description: 'Please enter a message or select a media file',
        variant: 'destructive',
      })
      return
    }

    // Determine message type based on media file
    let messageType: SendMessageData['message_type'] = 'text'
    if (formState.mediaFile) {
      const fileType = formState.mediaFile.type
      if (fileType.startsWith('image/')) {
        messageType = 'image'
      } else if (fileType.startsWith('audio/')) {
        messageType = 'audio'
      } else {
        messageType = 'document'
      }
    }

    const messageData: SendMessageData = {
      instance_name: selectedInstance,
      to: formState.to,
      message_type: messageType,
      text: formState.text.trim() || undefined,
      media_file: formState.mediaFile || undefined,
      media_caption: formState.mediaCaption || undefined,
    }

    sendMessageMutation.mutate(messageData)
  }, [selectedInstance, formState, sendMessageMutation, toast])

  return {
    formState,
    handleFormChange,
    handleFileUpload,
    handleSendMessage,
    isPending: sendMessageMutation.isPending,
  }
}
