import React from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { AlertCircle, MessageSquare, Image, FileText } from 'lucide-react'
import { MessageForm } from '../components/MessageForm'
import { StatusBadge } from '../components/StatusBadge'
import { useMessageForm } from '../hooks/useMessageForm'
import { useWhatsAppMessages } from '../hooks/useWhatsAppMessages'

interface MessagesTabProps {
  selectedInstance: string
}

export function MessagesTab({ selectedInstance }: MessagesTabProps) {
  const { recentMessages } = useWhatsAppMessages(selectedInstance)
  const {
    formState,
    handleFormChange,
    handleFileUpload,
    handleSendMessage,
    isPending
  } = useMessageForm(selectedInstance)

  if (!selectedInstance) {
    return (
      <Alert>
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>
          Please select a WhatsApp instance from the Instances tab to send messages.
        </AlertDescription>
      </Alert>
    )
  }

  return (
    <div className="space-y-4">
      <MessageForm
        selectedInstance={selectedInstance}
        formState={formState}
        onFormChange={handleFormChange}
        onFileUpload={handleFileUpload}
        onSubmit={handleSendMessage}
        isPending={isPending}
      />

      <Card>
        <CardHeader>
          <CardTitle>Recent Messages</CardTitle>
          <CardDescription>
            Latest messages from {selectedInstance}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {recentMessages.length === 0 ? (
              <div className="text-center text-muted-foreground py-4">
                No messages found
              </div>
            ) : (
              recentMessages.map((message) => (
                <div key={message.id} className="border rounded p-3">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <MessageSquare className="w-4 h-4" />
                      <span className="font-medium">{message.recipient_id}</span>
                      <StatusBadge status={message.status} />
                    </div>
                    <span className="text-sm text-muted-foreground">
                      {new Date(message.created_at).toLocaleString()}
                    </span>
                  </div>
                  <div className="text-sm">
                    {message.content && <p>{message.content}</p>}
                    {message.media_url && (
                      <div className="mt-2 flex items-center text-muted-foreground">
                        {message.message_type === 'image' && <Image className="w-4 h-4 mr-1" />}
                        {message.message_type === 'document' && <FileText className="w-4 h-4 mr-1" />}
                        Media attachment
                      </div>
                    )}
                    {message.error_message && (
                      <p className="text-red-600 mt-1">{message.error_message}</p>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
