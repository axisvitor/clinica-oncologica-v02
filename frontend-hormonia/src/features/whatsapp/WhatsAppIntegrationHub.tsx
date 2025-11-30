import React, { useState, useEffect, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Progress } from '@/components/ui/progress'
import {
  MessageSquare,
  Phone,
  Send,
  Image,
  FileText,
  AlertCircle,
  CheckCircle,
  Clock,
  X,
  RefreshCw,
  Users,
  BarChart3
} from 'lucide-react'
import { useToast } from '@/hooks/use-toast'
import { apiClient } from '@/lib/api-client'

// Types
interface WhatsAppInstance {
  name: string
  status: 'connected' | 'disconnected' | 'connecting' | 'error'
  qr_code?: string
  phone_number?: string
  profile_name?: string
  created_at: string
  last_seen?: string
}

interface WhatsAppMessage {
  id: string
  instance_name: string
  chat_id: string
  recipient_id: string
  message_type: 'text' | 'image' | 'document' | 'audio'
  content: string
  media_url?: string
  status: 'pending' | 'sent' | 'delivered' | 'read' | 'failed'
  sent_at?: string
  created_at: string
  error_message?: string
}

interface QueueStats {
  pending: number
  scheduled: number
  retry_scheduled: number
  dead_letter: number
}

interface MessageStats {
  total: number
  sent: number
  delivered: number
  read: number
  failed: number
  pending: number
}

interface SendMessageData {
  instance_name: string
  to: string
  message_type: 'text' | 'image' | 'audio' | 'document'
  text?: string
  media_file?: File
  media_caption?: string
}

export function WhatsAppIntegrationHub() {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [selectedInstance, setSelectedInstance] = useState<string>('')
  const [messageForm, setMessageForm] = useState({
    to: '',
    text: '',
    mediaFile: null as File | null,
    mediaCaption: ''
  })

  // Queries
  const { data: instances = [], isLoading: loadingInstances } = useQuery<WhatsAppInstance[]>({
    queryKey: ['whatsapp-instances'],
    queryFn: () => apiClient.request('/whatsapp/instances'),
    refetchInterval: 30000 // Refresh every 30 seconds
  })

  const { data: queueStats } = useQuery<QueueStats>({
    queryKey: ['whatsapp-queue-stats'],
    queryFn: () => apiClient.request('/whatsapp/queue/stats'),
    refetchInterval: 10000 // Refresh every 10 seconds
  })

  const { data: messageStats } = useQuery<MessageStats>({
    queryKey: ['whatsapp-message-stats', selectedInstance],
    queryFn: () => apiClient.request(`/whatsapp/messages/stats?instance=${selectedInstance}`),
    enabled: !!selectedInstance,
    refetchInterval: 30000
  })

  const { data: recentMessages = [] } = useQuery<WhatsAppMessage[]>({
    queryKey: ['whatsapp-recent-messages', selectedInstance],
    queryFn: () => apiClient.request(`/whatsapp/messages?instance=${selectedInstance}&limit=20`),
    enabled: !!selectedInstance,
    refetchInterval: 5000 // Refresh every 5 seconds
  })

  // Mutations
  const createInstanceMutation = useMutation({
    mutationFn: (instanceName: string) =>
      apiClient.request('/whatsapp/instances', {
        method: 'POST',
        body: JSON.stringify({ name: instanceName })
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['whatsapp-instances'] })
      toast({ title: 'Instance created successfully' })
    },
    onError: (error: unknown) => {
      const errorMessage = error instanceof Error ? error.message : 'Failed to create instance';
      toast({
        title: 'Failed to create instance',
        description: errorMessage,
        variant: 'destructive'
      })
    }
  })

  const sendMessageMutation = useMutation({
    mutationFn: (messageData: SendMessageData) =>
      apiClient.request('/whatsapp/messages/send', {
        method: 'POST',
        body: JSON.stringify(messageData)
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['whatsapp-recent-messages'] })
      queryClient.invalidateQueries({ queryKey: ['whatsapp-message-stats'] })
      toast({ title: 'Message sent successfully' })
      setMessageForm({ to: '', text: '', mediaFile: null, mediaCaption: '' })
    },
    onError: (error: unknown) => {
      const errorMessage = error instanceof Error ? error.message : 'Failed to send message';
      toast({
        title: 'Failed to send message',
        description: errorMessage,
        variant: 'destructive'
      })
    }
  })

  const restartInstanceMutation = useMutation({
    mutationFn: (instanceName: string) =>
      apiClient.request(`/whatsapp/instances/${instanceName}/restart`, {
        method: 'POST'
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['whatsapp-instances'] })
      toast({ title: 'Instance restart initiated' })
    }
  })

  const deleteInstanceMutation = useMutation({
    mutationFn: (instanceName: string) =>
      apiClient.request(`/whatsapp/instances/${instanceName}`, {
        method: 'DELETE'
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['whatsapp-instances'] })
      toast({ title: 'Instance deleted successfully' })
      if (selectedInstance === deleteInstanceMutation.variables) {
        setSelectedInstance('')
      }
    }
  })

  // Handle file upload
  const handleFileUpload = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file) {
      const maxSize = 16 * 1024 * 1024 // 16MB
      if (file.size > maxSize) {
        toast({
          title: 'File too large',
          description: 'Maximum file size is 16MB',
          variant: 'destructive'
        })
        return
      }
      setMessageForm(prev => ({ ...prev, mediaFile: file }))
    }
  }, [toast])

  // Send message
  const handleSendMessage = async () => {
    if (!selectedInstance) {
      toast({
        title: 'No instance selected',
        description: 'Please select a WhatsApp instance first',
        variant: 'destructive'
      })
      return
    }

    if (!messageForm.to.trim()) {
      toast({
        title: 'Phone number required',
        description: 'Please enter a recipient phone number',
        variant: 'destructive'
      })
      return
    }

    if (!messageForm.text.trim() && !messageForm.mediaFile) {
      toast({
        title: 'Message content required',
        description: 'Please enter a message or select a media file',
        variant: 'destructive'
      })
      return
    }

    // Determine message type based on media file
    let messageType: SendMessageData['message_type'] = 'text'
    if (messageForm.mediaFile) {
      const fileType = messageForm.mediaFile.type
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
      to: messageForm.to,
      message_type: messageType,
      text: messageForm.text.trim() || undefined,
      media_file: messageForm.mediaFile || undefined,
      media_caption: messageForm.mediaCaption || undefined
    }

    sendMessageMutation.mutate(messageData)
  }

  // Status badge component
  const StatusBadge = ({ status }: { status: string }) => {
    const statusConfig = {
      connected: { color: 'bg-green-100 text-green-800', icon: CheckCircle },
      connecting: { color: 'bg-yellow-100 text-yellow-800', icon: Clock },
      disconnected: { color: 'bg-gray-100 text-gray-800', icon: X },
      error: { color: 'bg-red-100 text-red-800', icon: AlertCircle },
      pending: { color: 'bg-blue-100 text-blue-800', icon: Clock },
      sent: { color: 'bg-green-100 text-green-800', icon: CheckCircle },
      delivered: { color: 'bg-green-100 text-green-800', icon: CheckCircle },
      read: { color: 'bg-green-100 text-green-800', icon: CheckCircle },
      failed: { color: 'bg-red-100 text-red-800', icon: AlertCircle }
    }

    const config = statusConfig[status as keyof typeof statusConfig]
    if (!config) return <Badge variant="outline">{status}</Badge>

    const Icon = config.icon

    return (
      <Badge className={config.color}>
        <Icon className="w-3 h-3 mr-1" />
        {status}
      </Badge>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">WhatsApp Integration</h1>
          <p className="text-muted-foreground">
            Manage WhatsApp instances and send messages to patients
          </p>
        </div>
        <Button
          onClick={() => {
            queryClient.invalidateQueries({ queryKey: ['whatsapp-instances'] })
            queryClient.invalidateQueries({ queryKey: ['whatsapp-queue-stats'] })
          }}
          variant="outline"
          size="sm"
        >
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh
        </Button>
      </div>

      {queueStats && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center">
              <BarChart3 className="w-5 h-5 mr-2" />
              Message Queue Status
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="text-center">
                <div className="text-2xl font-bold text-blue-600">{queueStats?.pending ?? 0}</div>
                <div className="text-sm text-muted-foreground">Pending</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-yellow-600">{queueStats?.scheduled ?? 0}</div>
                <div className="text-sm text-muted-foreground">Scheduled</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-orange-600">{queueStats?.retry_scheduled ?? 0}</div>
                <div className="text-sm text-muted-foreground">Retrying</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-red-600">{queueStats?.dead_letter ?? 0}</div>
                <div className="text-sm text-muted-foreground">Failed</div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      <Tabs defaultValue="instances" className="space-y-4">
        <TabsList>
          <TabsTrigger value="instances">Instances</TabsTrigger>
          <TabsTrigger value="messages">Messages</TabsTrigger>
          <TabsTrigger value="analytics">Analytics</TabsTrigger>
        </TabsList>

        <TabsContent value="instances" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Create New Instance</CardTitle>
              <CardDescription>
                Create a new WhatsApp instance for messaging
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={(e) => {
                e.preventDefault()
                const formData = new FormData(e.target as HTMLFormElement)
                const instanceName = formData.get('instanceName') as string
                if (instanceName.trim()) {
                  createInstanceMutation.mutate(instanceName.trim())
                }
              }}>
                <div className="flex gap-4">
                  <Input
                    name="instanceName"
                    placeholder="Instance name (e.g., clinica-main)"
                    className="flex-1"
                  />
                  <Button
                    type="submit"
                    disabled={createInstanceMutation.isPending}
                  >
                    {createInstanceMutation.isPending ? 'Creating...' : 'Create Instance'}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>

          <div className="grid gap-4">
            {loadingInstances ? (
              <Card>
                <CardContent className="pt-6">
                  <div className="flex items-center justify-center">
                    <RefreshCw className="w-6 h-6 animate-spin mr-2" />
                    Loading instances...
                  </div>
                </CardContent>
              </Card>
            ) : instances.length === 0 ? (
              <Card>
                <CardContent className="pt-6">
                  <div className="text-center text-muted-foreground">
                    No WhatsApp instances found. Create your first instance above.
                  </div>
                </CardContent>
              </Card>
            ) : (
              instances.map((instance) => (
                <Card key={instance.name} className={selectedInstance === instance.name ? 'border-blue-500' : ''}>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <div>
                        <CardTitle className="flex items-center">
                          <Phone className="w-5 h-5 mr-2" />
                          {instance.name}
                        </CardTitle>
                        <CardDescription>
                          {instance.profile_name || 'No profile name'} | {instance.phone_number || 'No phone number'}
                        </CardDescription>
                      </div>
                      <div className="flex items-center gap-2">
                        <StatusBadge status={instance.status} />
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setSelectedInstance(instance.name)}
                        >
                          {selectedInstance === instance.name ? 'Selected' : 'Select'}
                        </Button>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => restartInstanceMutation.mutate(instance.name)}
                        disabled={restartInstanceMutation.isPending}
                      >
                        <RefreshCw className="w-4 h-4 mr-2" />
                        Restart
                      </Button>
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() => deleteInstanceMutation.mutate(instance.name)}
                        disabled={deleteInstanceMutation.isPending}
                      >
                        <X className="w-4 h-4 mr-2" />
                        Delete
                      </Button>
                    </div>

                    {instance.qr_code && (
                      <div className="mt-4">
                        <Label>Scan QR Code to Connect</Label>
                        <div className="mt-2 p-4 bg-white rounded border">
                          <img
                            src={`data:image/png;base64,${instance.qr_code}`}
                            alt="QR Code"
                            className="w-48 h-48 mx-auto"
                          />
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))
            )}
          </div>
        </TabsContent>

        <TabsContent value="messages" className="space-y-4">
          {!selectedInstance ? (
            <Alert>
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                Please select a WhatsApp instance from the Instances tab to send messages.
              </AlertDescription>
            </Alert>
          ) : (
            <>
              <Card>
                <CardHeader>
                  <CardTitle>Send Message</CardTitle>
                  <CardDescription>
                    Send message via {selectedInstance}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <Label htmlFor="recipient">Recipient Phone Number</Label>
                    <Input
                      id="recipient"
                      placeholder="+5511999999999 or 5511999999999"
                      value={messageForm.to}
                      onChange={(e) => setMessageForm(prev => ({ ...prev, to: e.target.value }))}
                    />
                  </div>

                  <div>
                    <Label htmlFor="message">Message</Label>
                    <Textarea
                      id="message"
                      placeholder="Type your message here..."
                      value={messageForm.text}
                      onChange={(e) => setMessageForm(prev => ({ ...prev, text: e.target.value }))}
                      rows={3}
                    />
                  </div>

                  <div>
                    <Label htmlFor="media">Media File (Optional)</Label>
                    <Input
                      id="media"
                      type="file"
                      accept="image/*,audio/*,.pdf,.doc,.docx"
                      onChange={handleFileUpload}
                    />
                    {messageForm.mediaFile && (
                      <div className="mt-2 p-2 bg-gray-50 rounded text-sm">
                        Selected: {messageForm.mediaFile.name} ({(messageForm.mediaFile.size / 1024 / 1024).toFixed(2)}MB)
                      </div>
                    )}
                  </div>

                  {messageForm.mediaFile && (
                    <div>
                      <Label htmlFor="caption">Media Caption (Optional)</Label>
                      <Input
                        id="caption"
                        placeholder="Caption for the media file..."
                        value={messageForm.mediaCaption}
                        onChange={(e) => setMessageForm(prev => ({ ...prev, mediaCaption: e.target.value }))}
                      />
                    </div>
                  )}

                  <Button
                    onClick={handleSendMessage}
                    disabled={sendMessageMutation.isPending}
                    className="w-full"
                  >
                    {sendMessageMutation.isPending ? (
                      <>
                        <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                        Sending...
                      </>
                    ) : (
                      <>
                        <Send className="w-4 h-4 mr-2" />
                        Send Message
                      </>
                    )}
                  </Button>
                </CardContent>
              </Card>

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
            </>
          )}
        </TabsContent>

        <TabsContent value="analytics" className="space-y-4">
          {!selectedInstance ? (
            <Alert>
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                Please select a WhatsApp instance to view analytics.
              </AlertDescription>
            </Alert>
          ) : messageStats ? (
            <Card>
              <CardHeader>
                <CardTitle>Message Statistics</CardTitle>
                <CardDescription>
                  Analytics for {selectedInstance}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
                  <div className="text-center">
                    <div className="text-3xl font-bold">{messageStats?.total ?? 0}</div>
                    <div className="text-sm text-muted-foreground">Total Messages</div>
                  </div>
                  <div className="text-center">
                    <div className="text-3xl font-bold text-green-600">{messageStats?.delivered ?? 0}</div>
                    <div className="text-sm text-muted-foreground">Delivered</div>
                  </div>
                  <div className="text-center">
                    <div className="text-3xl font-bold text-blue-600">{messageStats?.read ?? 0}</div>
                    <div className="text-sm text-muted-foreground">Read</div>
                  </div>
                  <div className="text-center">
                    <div className="text-3xl font-bold text-red-600">{messageStats?.failed ?? 0}</div>
                    <div className="text-sm text-muted-foreground">Failed</div>
                  </div>
                  <div className="text-center">
                    <div className="text-3xl font-bold text-yellow-600">{messageStats?.pending ?? 0}</div>
                    <div className="text-sm text-muted-foreground">Pending</div>
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span>Delivery Rate</span>
                    <span>{messageStats && messageStats.total > 0 ? Math.round((messageStats.delivered / messageStats.total) * 100) : 0}%</span>
                  </div>
                  <Progress
                    value={messageStats && messageStats.total > 0 ? (messageStats.delivered / messageStats.total) * 100 : 0}
                    className="h-2"
                  />
                </div>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="pt-6">
                <div className="text-center text-muted-foreground">
                  Loading analytics...
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}
