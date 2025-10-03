import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import { useToast } from '@/components/ui/use-toast'

export interface FlowData {
  id: string
  patient_id: string
  patient_name: string
  flow_type: string
  current_day: number
  status: 'active' | 'paused' | 'completed' | 'cancelled'
  enrollment_date: string
  last_message_sent?: string
  monthly_cycle?: number
  state_data?: Record<string, any>
  created_at: string
  updated_at: string
}

export interface FlowsParams {
  patient_id?: string
  status?: string
  page?: number
  size?: number
}

export interface FlowStats {
  total_active_flows: number
  total_paused_flows: number
  total_completed_flows: number
  completion_rate: number
  engagement_rate: number
  average_response_time: number
  flows_by_type: Record<string, number>
}

export function useFlows(params: FlowsParams = {}) {
  return useQuery({
    queryKey: ['flows', params],
    queryFn: () => apiClient.flows.list(params),
    refetchInterval: 30000, // Refetch every 30 seconds for real-time updates
  })
}

export function useFlowStats() {
  return useQuery({
    queryKey: ['flow-stats'],
    queryFn: () => apiClient.flows.getAnalytics(),
    refetchInterval: 60000, // Refetch every minute
  })
}

export function usePauseFlow() {
  const { toast } = useToast()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (patientId: string) => apiClient.flows.pause(patientId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['flows'] })
      queryClient.invalidateQueries({ queryKey: ['flow-stats'] })
      toast({
        title: 'Fluxo pausado',
        description: 'O fluxo foi pausado com sucesso.',
      })
    },
    onError: (error: any) => {
      toast({
        title: 'Erro ao pausar fluxo',
        description: error.data?.message || 'Ocorreu um erro ao pausar o fluxo.',
        variant: 'destructive',
      })
    },
  })
}

export function useResumeFlow() {
  const { toast } = useToast()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (patientId: string) => apiClient.flows.resume(patientId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['flows'] })
      queryClient.invalidateQueries({ queryKey: ['flow-stats'] })
      toast({
        title: 'Fluxo retomado',
        description: 'O fluxo foi retomado com sucesso.',
      })
    },
    onError: (error: any) => {
      toast({
        title: 'Erro ao retomar fluxo',
        description: error.data?.message || 'Ocorreu um erro ao retomar o fluxo.',
        variant: 'destructive',
      })
    },
  })
}

export function useStartFlow() {
  const { toast } = useToast()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ patientId, flowType }: { patientId: string; flowType: string }) =>
      apiClient.flows.start(patientId, flowType),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['flows'] })
      queryClient.invalidateQueries({ queryKey: ['flow-stats'] })
      toast({
        title: 'Fluxo iniciado',
        description: 'O fluxo foi iniciado com sucesso.',
      })
    },
    onError: (error: any) => {
      toast({
        title: 'Erro ao iniciar fluxo',
        description: error.data?.message || 'Ocorreu um erro ao iniciar o fluxo.',
        variant: 'destructive',
      })
    },
  })
}