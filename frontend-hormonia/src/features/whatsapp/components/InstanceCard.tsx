import React from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Phone, RefreshCw, X } from 'lucide-react'
import { WhatsAppInstance } from '../types'
import { StatusBadge } from './StatusBadge'
import { QRCodeDisplay } from './QRCodeDisplay'

interface InstanceCardProps {
  instance: WhatsAppInstance
  isSelected: boolean
  onSelect: () => void
  onRestart: () => void
  onDelete: () => void
  isRestartPending: boolean
  isDeletePending: boolean
}

export function InstanceCard({
  instance,
  isSelected,
  onSelect,
  onRestart,
  onDelete,
  isRestartPending,
  isDeletePending,
}: InstanceCardProps) {
  return (
    <Card className={isSelected ? 'border-blue-500' : ''}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center">
              <Phone className="w-5 h-5 mr-2" />
              {instance.name}
            </CardTitle>
            <CardDescription>
              {instance.profile_name || 'No profile name'} |{' '}
              {instance.phone_number || 'No phone number'}
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <StatusBadge status={instance.status} />
            <Button variant="outline" size="sm" onClick={onSelect}>
              {isSelected ? 'Selected' : 'Select'}
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={onRestart} disabled={isRestartPending}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Restart
          </Button>
          <Button variant="destructive" size="sm" onClick={onDelete} disabled={isDeletePending}>
            <X className="w-4 h-4 mr-2" />
            Delete
          </Button>
        </div>

        {instance.qr_code && <QRCodeDisplay qrCode={instance.qr_code} />}
      </CardContent>
    </Card>
  )
}
