import React, { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { RefreshCw, BarChart3 } from 'lucide-react'
import { InstancesTab } from './tabs/InstancesTab'
import { MessagesTab } from './tabs/MessagesTab'
import { AnalyticsTab } from './tabs/AnalyticsTab'
import { useWhatsAppMessages } from './hooks/useWhatsAppMessages'

export function WhatsAppIntegrationHub() {
  const queryClient = useQueryClient()
  const [selectedInstance, setSelectedInstance] = useState<string>('')
  const { queueStats } = useWhatsAppMessages(selectedInstance)

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ['whatsapp-instances'] })
    queryClient.invalidateQueries({ queryKey: ['whatsapp-queue-stats'] })
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
          onClick={handleRefresh}
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
                <div className="text-2xl font-bold text-blue-600">{queueStats.pending}</div>
                <div className="text-sm text-muted-foreground">Pending</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-yellow-600">{queueStats.scheduled}</div>
                <div className="text-sm text-muted-foreground">Scheduled</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-orange-600">{queueStats.retry_scheduled}</div>
                <div className="text-sm text-muted-foreground">Retrying</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-red-600">{queueStats.dead_letter}</div>
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

        <TabsContent value="instances">
          <InstancesTab
            selectedInstance={selectedInstance}
            onSelectInstance={setSelectedInstance}
          />
        </TabsContent>

        <TabsContent value="messages">
          <MessagesTab selectedInstance={selectedInstance} />
        </TabsContent>

        <TabsContent value="analytics">
          <AnalyticsTab selectedInstance={selectedInstance} />
        </TabsContent>
      </Tabs>
    </div>
  )
}
