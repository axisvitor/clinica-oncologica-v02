import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useToast } from '@/components/ui/use-toast'
import { apiClient } from '@/lib/api-client'
import { useAuth } from '@/contexts/AuthContext'
import { quizPermissions, getPermissionErrorMessage } from '@/utils/quizPermissions'

interface CreateQuizLinkData {
  patient_id: string
  quiz_template_id: string
  delivery_method: string
  expiry_hours: number
  custom_message?: string
  send_immediately?: boolean
}

interface BulkCreateQuizLinkData {
  patient_ids: string[]
  quiz_template_id: string
  delivery_method: string
  expiry_hours: number
  custom_message?: string
  send_immediately?: boolean
}

export function useMonthlyQuizAdminSecure() {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const { user } = useAuth()

  // Permission-aware functions
  const canCreateLink = quizPermissions.canCreateQuizLink(user)
  const canViewStats = quizPermissions.canViewQuizStats(user)
  const canResendLinks = quizPermissions.canResendLink(user)
  const canCancelLinks = quizPermissions.canCancelQuizLink(user)
  const canPerformBulk = quizPermissions.canPerformBulkOperations(user)

  // Send quiz link to a single patient
  const sendQuizLink = async (data: CreateQuizLinkData) => {
    if (!canCreateLink) {
      throw new Error(getPermissionErrorMessage('create_quiz_link', user?.role))
    }
    return await apiClient.monthlyQuiz.createLink(data)
  }

  // Send quiz link to multiple patients (bulk)
  const sendBulkQuizLinks = async (data: BulkCreateQuizLinkData) => {
    if (!canPerformBulk) {
      throw new Error(getPermissionErrorMessage('bulk_operations', user?.role))
    }
    return await apiClient.monthlyQuiz.bulkCreate(data)
  }

  // Resend quiz link with permission check
  const resendQuizLink = async (sessionId: string) => {
    if (!canResendLinks) {
      toast({
        title: 'Acesso negado',
        description: getPermissionErrorMessage('resend_link', user?.role),
        variant: 'destructive'
      })
      throw new Error(getPermissionErrorMessage('resend_link', user?.role))
    }

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
    } catch (error: any) {
      toast({
        title: 'Erro ao reenviar link',
        description: error.message || 'Ocorreu um erro ao reenviar o link',
        variant: 'destructive'
      })
      throw error
    }
  }

  // Cancel quiz link with permission check
  const cancelQuizLink = async (sessionId: string) => {
    if (!canCancelLinks) {
      toast({
        title: 'Acesso negado',
        description: getPermissionErrorMessage('cancel_link', user?.role),
        variant: 'destructive'
      })
      throw new Error(getPermissionErrorMessage('cancel_link', user?.role))
    }

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
    } catch (error: any) {
      toast({
        title: 'Erro ao cancelar link',
        description: error.message || 'Ocorreu um erro ao cancelar o link',
        variant: 'destructive'
      })
      throw error
    }
  }

  // Get quiz link status for a patient
  const getQuizLinkStatus = async (patientId: string) => {
    if (!canViewStats) {
      throw new Error(getPermissionErrorMessage('view_quiz_stats', user?.role))
    }
    return await apiClient.monthlyQuiz.getPatientStatus(patientId)
  }

  // Use query to get quiz link status with caching and permission check
  const useQuizLinkStatus = (patientId: string) => {
    return useQuery({
      queryKey: ['monthly-quiz-status', patientId],
      queryFn: () => getQuizLinkStatus(patientId),
      enabled: !!patientId && canViewStats,
      staleTime: 30000 // 30 seconds
    })
  }

  // Get quiz statistics with permission filtering
  const getQuizStats = async (dateFrom?: string, dateTo?: string) => {
    if (!canViewStats) {
      throw new Error(getPermissionErrorMessage('view_quiz_stats', user?.role))
    }
    
    const scope = quizPermissions.getQuizStatsScope(user)
    const params: any = { start_date: dateFrom, end_date: dateTo }
    
    // Add scope filtering for doctors
    if (scope === 'own_patients' && user?.id) {
      params.doctor_id = user['id']
    }
    
    return await apiClient.monthlyQuiz.getStats(params)
  }

  // Use query to get quiz stats with caching and permission filtering
  const useQuizStats = (dateFrom?: string, dateTo?: string) => {
    return useQuery({
      queryKey: ['monthly-quiz-stats', dateFrom, dateTo, user?.id],
      queryFn: () => getQuizStats(dateFrom, dateTo),
      enabled: canViewStats,
      staleTime: 60000 // 1 minute
    })
  }

  // Mutation for sending quiz link with permission check
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
      onError: (error: any) => {
        toast({
          title: 'Erro ao enviar link',
          description: error.message || 'Ocorreu um erro ao enviar o link',
          variant: 'destructive'
        })
      }
    })
  }

  // Mutation for bulk sending quiz links with permission check
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
      onError: (error: any) => {
        toast({
          title: 'Erro ao enviar links',
          description: error.message || 'Ocorreu um erro ao enviar os links',
          variant: 'destructive'
        })
      }
    })
  }

  return {
    // Permission flags
    canCreateLink,
    canViewStats,
    canResendLinks,
    canCancelLinks,
    canPerformBulk,
    
    // Functions
    sendQuizLink,
    sendBulkQuizLinks,
    resendQuizLink,
    cancelQuizLink,
    getQuizLinkStatus,
    useQuizLinkStatus,
    getQuizStats,
    useQuizStats,
    useSendQuizLinkMutation,
    useBulkSendQuizLinksMutation,
    
    // User info for permission checks
    user,
    userScope: quizPermissions.getQuizStatsScope(user)
  }
}
