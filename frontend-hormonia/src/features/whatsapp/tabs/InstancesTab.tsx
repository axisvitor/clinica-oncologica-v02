import React from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { RefreshCw } from 'lucide-react'
import { InstanceCard } from '../components/InstanceCard'
import { useWhatsAppInstances } from '../hooks/useWhatsAppInstances'
import type { WhatsAppInstance } from '../types'

interface InstancesTabProps {
  selectedInstance: string
  onSelectInstance: (instanceName: string) => void
}

export function InstancesTab({ selectedInstance, onSelectInstance }: InstancesTabProps) {
  const {
    instances,
    isLoading,
    createInstance,
    isCreating,
    restartInstance,
    isRestarting,
    deleteInstance,
    isDeleting
  } = useWhatsAppInstances()

  const handleCreateInstance = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const formData = new FormData(e.target as HTMLFormElement)
    const instanceName = formData.get('instanceName') as string
    if (instanceName.trim()) {
      createInstance(instanceName.trim())
      ;(e.target as HTMLFormElement).reset()
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Create New Instance</CardTitle>
          <CardDescription>
            Create a new WhatsApp instance for messaging
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleCreateInstance}>
            <div className="flex gap-4">
              <Input
                name="instanceName"
                placeholder="Instance name (e.g., clinica-main)"
                className="flex-1"
              />
              <Button
                type="submit"
                disabled={isCreating}
              >
                {isCreating ? 'Creating...' : 'Create Instance'}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <div className="grid gap-4">
        {isLoading ? (
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
          instances.map((instance: WhatsAppInstance) => (
            <InstanceCard
              key={instance.name}
              instance={instance}
              isSelected={selectedInstance === instance.name}
              onSelect={() => onSelectInstance(instance.name)}
              onRestart={() => restartInstance(instance.name)}
              onDelete={() => deleteInstance(instance.name)}
              isRestartPending={isRestarting}
              isDeletePending={isDeleting}
            />
          ))
        )}
      </div>
    </div>
  )
}
