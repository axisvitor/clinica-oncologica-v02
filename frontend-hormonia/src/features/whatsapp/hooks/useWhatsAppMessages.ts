import { useQuery } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import { WhatsAppMessage, MessageStats, QueueStats } from '../types'

export function useWhatsAppMessages(selectedInstance: string) {
  const { data: queueStats } = useQuery<QueueStats>({
    queryKey: ['whatsapp-queue-stats'],
    queryFn: () => apiClient.request('/api/v2/whatsapp/queue/stats'),
    refetchInterval: 10000, // Refresh every 10 seconds
  })

  const { data: messageStats } = useQuery<MessageStats>({
    queryKey: ['whatsapp-message-stats', selectedInstance],
    queryFn: () =>
      apiClient.request(`/api/v2/whatsapp/messages/stats?instance=${selectedInstance}`),
    enabled: !!selectedInstance,
    refetchInterval: 30000,
  })

  const { data: recentMessages = [] } = useQuery<WhatsAppMessage[]>({
    queryKey: ['whatsapp-recent-messages', selectedInstance],
    queryFn: () =>
      apiClient.request(`/api/v2/whatsapp/messages?instance=${selectedInstance}&limit=20`),
    enabled: !!selectedInstance,
    refetchInterval: 5000, // Refresh every 5 seconds
  })

  return {
    queueStats,
    messageStats,
    recentMessages,
  }
}
