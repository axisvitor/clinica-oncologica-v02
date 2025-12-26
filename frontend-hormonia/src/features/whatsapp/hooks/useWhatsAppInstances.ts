import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useToast } from '@/hooks/use-toast'
import { apiClient } from '@/lib/api-client'
import { WhatsAppInstance } from '../types'

export function useWhatsAppInstances() {
  const { toast } = useToast()
  const queryClient = useQueryClient()

  const { data: instances = [], isLoading } = useQuery<WhatsAppInstance[]>({
    queryKey: ['whatsapp-instances'],
    queryFn: () => apiClient.request('/api/v2/whatsapp/instances'),
    refetchInterval: 30000 // Refresh every 30 seconds
  })

  const createInstanceMutation = useMutation({
    mutationFn: (instanceName: string) =>
      apiClient.request('/api/v2/whatsapp/instances', {
        method: 'POST',
        body: JSON.stringify({ name: instanceName })
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['whatsapp-instances'] })
      toast({ title: 'Instance created successfully' })
    },
    onError: (error: unknown) => {
      const errorMessage = error instanceof Error ? error.message : 'Failed to create instance'
      toast({
        title: 'Failed to create instance',
        description: errorMessage,
        variant: 'destructive'
      })
    }
  })

  const restartInstanceMutation = useMutation({
    mutationFn: (instanceName: string) =>
      apiClient.request(`/api/v2/whatsapp/instances/${instanceName}/restart`, {
        method: 'POST'
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['whatsapp-instances'] })
      toast({ title: 'Instance restart initiated' })
    },
    onError: (error: unknown) => {
      const errorMessage = error instanceof Error ? error.message : 'Failed to restart instance'
      toast({
        title: 'Failed to restart instance',
        description: errorMessage,
        variant: 'destructive'
      })
    }
  })

  const deleteInstanceMutation = useMutation({
    mutationFn: (instanceName: string) =>
      apiClient.request(`/api/v2/whatsapp/instances/${instanceName}`, {
        method: 'DELETE'
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['whatsapp-instances'] })
      toast({ title: 'Instance deleted successfully' })
    },
    onError: (error: unknown) => {
      const errorMessage = error instanceof Error ? error.message : 'Failed to delete instance'
      toast({
        title: 'Failed to delete instance',
        description: errorMessage,
        variant: 'destructive'
      })
    }
  })

  return {
    instances,
    isLoading,
    createInstance: createInstanceMutation.mutate,
    isCreating: createInstanceMutation.isPending,
    restartInstance: restartInstanceMutation.mutate,
    isRestarting: restartInstanceMutation.isPending,
    deleteInstance: deleteInstanceMutation.mutate,
    isDeleting: deleteInstanceMutation.isPending
  }
}
