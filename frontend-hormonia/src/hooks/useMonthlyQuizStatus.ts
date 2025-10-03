import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import { useToast } from '@/components/ui/use-toast'
import type { QuizLinkStatus } from '@/components/patients/MonthlyQuizStatus'

export interface MonthlyQuizStatusData {
  patient_id: string
  session_id?: string
  status: QuizLinkStatus
  last_sent?: string
  access_date?: string
  completion_date?: string
  expires_at?: string
  template_name?: string
  template_id?: string
}

export interface MonthlyQuizHistoryItem {
  id: string
  patient_id: string
  patient_name: string
  template_name: string
  template_id: string
  status: QuizLinkStatus
  sent_at: string
  accessed_at?: string
  completed_at?: string
  expires_at: string
  delivery_method: 'whatsapp' | 'email' | 'sms'
}

export interface MonthlyQuizBulkStatus {
  [patientId: string]: MonthlyQuizStatusData
}

/**
 * Hook to fetch quiz link status for a single patient
 */
export function useMonthlyQuizStatus(patientId: string) {
  return useQuery<MonthlyQuizStatusData>({
    queryKey: ['monthly-quiz-status', patientId],
    queryFn: async () => {
      try {
        const response = await apiClient.monthlyQuiz.getPatientStatus(patientId)
        return {
          patient_id: patientId,
          session_id: response.session_id,
          status: mapBackendStatus(response.status),
          last_sent: response.last_sent,
          access_date: response.last_response,
          completion_date: response.status === 'completed' ? response.last_response : undefined,
          expires_at: response.expires_at,
          template_name: response.template_name,
          template_id: response.template_id
        }
      } catch (error: any) {
        // If patient has no quiz link, return not_sent status
        if (error.status === 404) {
          return {
            patient_id: patientId,
            status: 'not_sent' as QuizLinkStatus,
          }
        }
        throw error
      }
    },
    enabled: !!patientId,
    staleTime: 30000, // 30 seconds
    retry: 1
  })
}

/**
 * Hook to fetch quiz link statuses for multiple patients (bulk)
 */
export function useBulkMonthlyQuizStatus(patientIds: string[]) {
  return useQuery<MonthlyQuizBulkStatus>({
    queryKey: ['monthly-quiz-bulk-status', patientIds],
    queryFn: async () => {
      const statuses: MonthlyQuizBulkStatus = {}

      // Fetch statuses in parallel
      const results = await Promise.allSettled(
        patientIds.map(id => apiClient.monthlyQuiz.getPatientStatus(id))
      )

      results.forEach((result, index) => {
        const patientId = patientIds[index]

        if (result.status === 'fulfilled') {
          const data = result.value
          const patientIdSafe = patientIds[index]
          if (patientIdSafe) {
            statuses[patientIdSafe] = {
              patient_id: patientIdSafe,
              session_id: data.session_id,
              status: mapBackendStatus(data.status),
              last_sent: data.last_sent,
              access_date: data.last_response,
              completion_date: data.status === 'completed' ? data.last_response : undefined,
              expires_at: data.expires_at,
              template_name: data.template_name,
              template_id: data.template_id
            }
          }
        } else {
          // Patient has no quiz link
          const patientIdSafe = patientIds[index]
          if (patientIdSafe) {
            statuses[patientIdSafe] = {
              patient_id: patientIdSafe,
              status: 'not_sent' as QuizLinkStatus
            }
          }
        }
      })

      return statuses
    },
    enabled: patientIds.length > 0,
    staleTime: 30000, // 30 seconds
  })
}

/**
 * Hook to fetch quiz link history for a patient
 */
export function useMonthlyQuizHistory(patientId: string) {
  return useQuery<MonthlyQuizHistoryItem[]>({
    queryKey: ['monthly-quiz-history', patientId],
    queryFn: async () => {
      const response = await apiClient.monthlyQuiz.getHistory(patientId)
      return response.map((item: any) => ({
        id: item.session_id || item['id'],
        patient_id: item.patient_id,
        patient_name: item.patient_name,
        template_name: item.template_name,
        template_id: item.quiz_template_id || item.template_id,
        status: mapBackendStatus(item.status),
        sent_at: item.sent_at,
        accessed_at: item.accessed_at,
        completed_at: item.completed_at,
        expires_at: item.expires_at,
        delivery_method: item.delivery_method || 'whatsapp'
      }))
    },
    enabled: !!patientId,
    staleTime: 60000 // 1 minute
  })
}

/**
 * Hook to resend quiz link mutation
 */
export function useResendQuizLink() {
  const { toast } = useToast()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (sessionId: string) => {
      return await apiClient.monthlyQuiz.resend(sessionId)
    },
    onSuccess: (_, sessionId) => {
      toast({
        title: 'Link reenviado',
        description: 'O link do quiz foi reenviado com sucesso'
      })

      // Invalidate all related queries
      queryClient.invalidateQueries({ queryKey: ['monthly-quiz-status'] })
      queryClient.invalidateQueries({ queryKey: ['monthly-quiz-history'] })
      queryClient.invalidateQueries({ queryKey: ['monthly-quiz-stats'] })
    },
    onError: (error: any) => {
      toast({
        title: 'Erro ao reenviar link',
        description: error.data?.message || 'Não foi possível reenviar o link do quiz',
        variant: 'destructive'
      })
    }
  })
}

/**
 * Map backend status to frontend QuizLinkStatus
 */
function mapBackendStatus(backendStatus: string): QuizLinkStatus {
  switch (backendStatus) {
    case 'active':
    case 'pending':
      return 'sent'
    case 'accessed':
      return 'accessed'
    case 'completed':
      return 'completed'
    case 'expired':
      return 'expired'
    case 'not_sent':
    default:
      return 'not_sent'
  }
}