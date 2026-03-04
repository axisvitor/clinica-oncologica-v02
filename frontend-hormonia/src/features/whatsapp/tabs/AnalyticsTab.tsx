import React from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Progress } from '@/components/ui/progress'
import { AlertCircle } from 'lucide-react'
import { useWhatsAppMessages } from '../hooks/useWhatsAppMessages'

interface AnalyticsTabProps {
  selectedInstance: string
}

export function AnalyticsTab({ selectedInstance }: AnalyticsTabProps) {
  const { messageStats } = useWhatsAppMessages(selectedInstance)

  if (!selectedInstance) {
    return (
      <Alert>
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>Please select a WhatsApp instance to view analytics.</AlertDescription>
      </Alert>
    )
  }

  if (!messageStats) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="text-center text-muted-foreground">Loading analytics...</div>
        </CardContent>
      </Card>
    )
  }

  const deliveryRate =
    messageStats.total > 0 ? Math.round((messageStats.delivered / messageStats.total) * 100) : 0

  return (
    <Card>
      <CardHeader>
        <CardTitle>Message Statistics</CardTitle>
        <CardDescription>Analytics for {selectedInstance}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
          <div className="text-center">
            <div className="text-3xl font-bold">{messageStats.total}</div>
            <div className="text-sm text-muted-foreground">Total Messages</div>
          </div>
          <div className="text-center">
            <div className="text-3xl font-bold text-green-600">{messageStats.delivered}</div>
            <div className="text-sm text-muted-foreground">Delivered</div>
          </div>
          <div className="text-center">
            <div className="text-3xl font-bold text-blue-600">{messageStats.read}</div>
            <div className="text-sm text-muted-foreground">Read</div>
          </div>
          <div className="text-center">
            <div className="text-3xl font-bold text-red-600">{messageStats.failed}</div>
            <div className="text-sm text-muted-foreground">Failed</div>
          </div>
          <div className="text-center">
            <div className="text-3xl font-bold text-yellow-600">{messageStats.pending}</div>
            <div className="text-sm text-muted-foreground">Pending</div>
          </div>
        </div>

        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span>Delivery Rate</span>
            <span>{deliveryRate}%</span>
          </div>
          <Progress value={deliveryRate} className="h-2" />
        </div>
      </CardContent>
    </Card>
  )
}
