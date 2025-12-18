import { useCallback } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useToast } from '@/components/ui/use-toast'
import { apiClient } from '@/lib/api-client'
import { getErrorMessage } from '@/lib/type-guards'
import type { QuizHistoryEntry, QuizLinkStatus } from '@/lib/api-client/monthly-quiz'

type DeliveryMethod = 'whatsapp' | 'email' | 'sms' | 'manual'

interface CreateQuizLinkData {
  patient_id: string
  quiz_template_id: string
  delivery_method?: DeliveryMethod
  expiry_hours?: number
  custom_message?: string
  send_immediately?: boolean
}

interface BulkCreateQuizLinkData {
  patient_ids: string[]
  quiz_template_id: string
  delivery_method?: DeliveryMethod
  expiry_hours?: number
  custom_message?: string
  send_immediately?: boolean
}

export function useMonthlyQuizAdmin() {
  const { toast } = useToast()
  const queryClient = useQueryClient()

  // Send quiz link to a single patient
  const sendQuizLink = useCallback(async (data: CreateQuizLinkData) => {
    return await apiClient.monthlyQuiz.createLink(data)
  }, [])

  // Send quiz link to multiple patients (bulk)
  const sendBulkQuizLinks = useCallback(async (data: BulkCreateQuizLinkData) => {
    return await apiClient.monthlyQuiz.bulkCreate(data)
  }, [])

  // Resend quiz link
  const resendQuizLink = useCallback(async (sessionId: string) => {
    try {
      const result = await apiClient.monthlyQuiz.resend(sessionId)

      toast({
        title: 'Link reenviado',
        description: 'O link do quiz foi reenviado com sucesso'
      })

      // Invalidate queries to refresh data
      queryClient.invalidateQueries({ queryKey: ['monthly-quiz-active-links'] })
      queryClient.invalidateQueries({ queryKey: ['monthly-quiz-stats'] })

      return result
    } catch (error: unknown) {
      toast({
        title: 'Erro ao reenviar link',
        description: getErrorMessage(error) || 'Ocorreu um erro ao reenviar o link',
        variant: 'destructive'
      })
      throw error
    }
  }, [queryClient, toast])

  // Get quiz link status for a patient
  const getQuizLinkStatus = useCallback(async (patientId: string) => {
    return await apiClient.monthlyQuiz.getPatientStatus(patientId)
  }, [])

  // Use query to get quiz link status with caching
  const useQuizLinkStatus = (patientId: string) => {
    return useQuery<any>({
      queryKey: ['monthly-quiz-status', patientId],
      queryFn: async () => {
        const list = await getQuizLinkStatus(patientId)
        if (!Array.isArray(list) || list.length === 0) return null
        const first = list[0] as QuizLinkStatus
        const expired = first.expires_at ? (new Date(first.expires_at) < new Date()) : false
        const uiStatus = !expired && !['completed', 'cancelled', 'expired'].includes(first.status) ? 'active' : first.status
        return { ...first, status: uiStatus }
      },
      enabled: !!patientId,
      staleTime: 30000 // 30 seconds
    })
  }

  // Get quiz link history for a patient
  const getQuizLinkHistory = useCallback(async (patientId: string) => {
    return await apiClient.monthlyQuiz.getHistory(patientId)
  }, [])

  // Use query to get quiz link history with caching
  const useQuizLinkHistory = (patientId: string) => {
    return useQuery<QuizHistoryEntry[]>({
      queryKey: ['monthly-quiz-history', patientId],
      queryFn: () => getQuizLinkHistory(patientId),
      enabled: !!patientId
    })
  }

  // Cancel quiz link
  const cancelQuizLink = useCallback(async (sessionId: string) => {
    try {
      const result = await apiClient.monthlyQuiz.cancel(sessionId)

      toast({
        title: 'Link cancelado',
        description: 'O link do quiz foi cancelado com sucesso'
      })

      // Invalidate queries to refresh data
      queryClient.invalidateQueries({ queryKey: ['monthly-quiz-active-links'] })
      queryClient.invalidateQueries({ queryKey: ['monthly-quiz-stats'] })

      return result
    } catch (error: unknown) {
      toast({
        title: 'Erro ao cancelar link',
        description: getErrorMessage(error) || 'Ocorreu um erro ao cancelar o link',
        variant: 'destructive'
      })
      throw error
    }
  }, [queryClient, toast])

  // Get quiz statistics
  const getQuizStats = useCallback(async (dateFrom?: string, dateTo?: string) => {
    const statsParams: { start_date?: string; end_date?: string } = {}
    if (dateFrom) statsParams.start_date = dateFrom
    if (dateTo) statsParams.end_date = dateTo

    return await apiClient.monthlyQuiz.getStats(statsParams)
  }, [])

  // Use query to get quiz stats with caching
  const useQuizStats = (dateFrom?: string, dateTo?: string) => {
    return useQuery({
      queryKey: ['monthly-quiz-stats', dateFrom, dateTo],
      queryFn: () => getQuizStats(dateFrom, dateTo),
      staleTime: 60000 // 1 minute
    })
  }

  // Mutation for sending quiz link
  const useSendQuizLinkMutation = () => {
    return useMutation({
      mutationFn: sendQuizLink,
      onSuccess: () => {
        toast({
          title: 'Link enviado',
          description: 'O link do quiz foi enviado com sucesso'
        })
        queryClient.invalidateQueries({ queryKey: ['monthly-quiz-stats'] })
        queryClient.invalidateQueries({ queryKey: ['patients'] })
      },
      onError: (error: unknown) => {
        toast({
          title: 'Erro ao enviar link',
          description: getErrorMessage(error) || 'Ocorreu um erro ao enviar o link',
          variant: 'destructive'
        })
      }
    })
  }

  // Mutation for bulk sending quiz links
  const useBulkSendQuizLinksMutation = () => {
    return useMutation({
      mutationFn: sendBulkQuizLinks,
      onSuccess: () => {
        toast({
          title: 'Links enviados',
          description: 'Os links do quiz foram enviados com sucesso'
        })
        queryClient.invalidateQueries({ queryKey: ['monthly-quiz-stats'] })
        queryClient.invalidateQueries({ queryKey: ['patients'] })
      },
      onError: (error: unknown) => {
        toast({
          title: 'Erro ao enviar links',
          description: getErrorMessage(error) || 'Ocorreu um erro ao enviar os links',
          variant: 'destructive'
        })
      }
    })
  }

  return {
    sendQuizLink,
    sendBulkQuizLinks,
    resendQuizLink,
    getQuizLinkStatus,
    useQuizLinkStatus,
    getQuizLinkHistory,
    useQuizLinkHistory,
    cancelQuizLink,
    getQuizStats,
    useQuizStats,
    useSendQuizLinkMutation,
    useBulkSendQuizLinksMutation
  }
}
