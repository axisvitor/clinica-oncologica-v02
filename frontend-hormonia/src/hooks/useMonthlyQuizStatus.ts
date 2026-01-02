import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import { useToast } from '@/components/ui/use-toast'
import { getErrorMessage } from '@/lib/type-guards'
import type { QuizLinkStatusValue, MonthlyQuizStatusData } from '@/types/api'
import type { QuizHistoryEntry } from '@/lib/api-client/monthly-quiz'

export interface MonthlyQuizHistoryItem {
  id: string
  patient_id: string
  patient_name: string
  template_name: string
  template_id: string
  status: QuizLinkStatusValue
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
interface RawQuizStatusResponse {
  session_id?: string
  quiz_session_id?: string
  status?: string
  last_sent?: string
  sent_at?: string
  last_response?: string
  accessed_at?: string
  completed_at?: string
  expires_at?: string
}

export function useMonthlyQuizStatus(patientId: string) {
  return useQuery<MonthlyQuizStatusData>({
    queryKey: ['monthly-quiz-status', patientId],
    queryFn: async () => {
      try {
        const response = await apiClient.monthlyQuiz.getPatientStatus(patientId)
        const s: RawQuizStatusResponse | undefined = Array.isArray(response) ? response[0] : response

        if (!s) {
          return {
            patient_id: patientId,
            status: 'not_sent' as QuizLinkStatusValue,
          }
        }

        return {
          patient_id: patientId,
          session_id: s.session_id ?? s.quiz_session_id,
          status: mapBackendStatus(String(s.status ?? 'not_sent')),
          last_sent: s.last_sent ?? s.sent_at,
          access_date: s.last_response ?? s.accessed_at,
          completion_date: (s.status === 'completed' ? (s.last_response ?? s.completed_at) : undefined),
          expires_at: s.expires_at,
        }
      } catch (error: unknown) {
        // If patient has no quiz link, return not_sent status
        const errorStatus = error && typeof error === 'object' && 'status' in error ? (error as { status: number }).status : null;
        if (errorStatus === 404) {
          return {
            patient_id: patientId,
            status: 'not_sent' as QuizLinkStatusValue,
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
        if (result.status === 'fulfilled') {
          const data = result.value as RawQuizStatusResponse[] | RawQuizStatusResponse
          const s = Array.isArray(data) ? data[0] : data
          const patientIdSafe = patientIds[index]
          if (patientIdSafe) {
            statuses[patientIdSafe] = {
              patient_id: patientIdSafe,
              session_id: s?.session_id ?? s?.quiz_session_id,
              status: mapBackendStatus(String(s?.status ?? 'not_sent')),
              last_sent: s?.last_sent ?? s?.sent_at,
              access_date: s?.last_response ?? s?.accessed_at,
              completion_date: s?.status === 'completed' ? (s?.last_response ?? s?.completed_at) : undefined,
              expires_at: s?.expires_at,
            }
          }
        } else {
          // Patient has no quiz link
          const patientIdSafe = patientIds[index]
          if (patientIdSafe) {
            statuses[patientIdSafe] = {
              patient_id: patientIdSafe,
              status: 'not_sent' as QuizLinkStatusValue
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

// RawQuizHistoryItem interface removed in favor of QuizHistoryEntry from api-client

/**
 * Hook to fetch quiz link history for a patient
 */
export function useMonthlyQuizHistory(patientId: string) {
  return useQuery<MonthlyQuizHistoryItem[]>({
    queryKey: ['monthly-quiz-history', patientId],
    queryFn: async () => {
      const response = await apiClient.monthlyQuiz.getHistory(patientId)
      return response.map((item: QuizHistoryEntry): MonthlyQuizHistoryItem => ({
        id: item.id,
        patient_id: item.patient_id || patientId,
        patient_name: item.patient_name || '',
        template_id: item.quiz_template_id || '',
        template_name: item.quiz_template_name || 'Questionário Mensal',
        status: mapBackendStatus(item.status),
        sent_at: item.sent_at || '',
        accessed_at: item.accessed_at,
        completed_at: item.completed_at,
        expires_at: item.expires_at || '',
        delivery_method: (item.delivery_method as 'whatsapp' | 'email' | 'sms') || 'whatsapp',
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
    onSuccess: () => {
      toast({
        title: 'Link reenviado',
        description: 'O link do quiz foi reenviado com sucesso'
      })

      // Invalidate all related queries
      queryClient.invalidateQueries({ queryKey: ['monthly-quiz-status'] })
      queryClient.invalidateQueries({ queryKey: ['monthly-quiz-history'] })
      queryClient.invalidateQueries({ queryKey: ['monthly-quiz-stats'] })
    },
    onError: (error: unknown) => {
      toast({
        title: 'Erro ao reenviar link',
        description: getErrorMessage(error) || 'Não foi possível reenviar o link do quiz',
        variant: 'destructive'
      })
    }
  })
}

/**
 * Map backend status to frontend QuizLinkStatusValue
 */
function mapBackendStatus(backendStatus: string): QuizLinkStatusValue {
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