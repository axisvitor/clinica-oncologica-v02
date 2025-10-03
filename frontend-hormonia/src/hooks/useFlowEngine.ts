import { useState, useEffect, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { flowEngine } from '../lib/flow-engine/FlowEngine'
import { templateManager } from '../lib/flow-engine/TemplateManager'
import {
  FlowType,
  type FlowState,
  type FlowTemplate,
  type MessageTemplate,
  type InboundMessage,
  type ResponseResult,
  type FlowEvent
} from '../lib/types/flow'

export function useFlowEngine() {
  const queryClient = useQueryClient()
  const [isInitialized, setIsInitialized] = useState(false)

  // Initialize flow engine
  useEffect(() => {
    const initialize = async () => {
      try {
        await flowEngine.loadTemplates()
        await templateManager.loadTemplates()
        setIsInitialized(true)
      } catch (error) {
        console.error('Failed to initialize flow engine:', error)
      }
    }

    initialize()
  }, [])

  // Listen to flow events
  useEffect(() => {
    const handleFlowEvent = (event: FlowEvent) => {
      // Invalidate relevant queries when flow events occur
      queryClient.invalidateQueries({ queryKey: ['flows'] })
      queryClient.invalidateQueries({ queryKey: ['flow-state', event.patient_id] })
      queryClient.invalidateQueries({ queryKey: ['flow-analytics'] })
    }

    flowEngine.on('flow_started', handleFlowEvent)
    flowEngine.on('flow_paused', handleFlowEvent)
    flowEngine.on('flow_resumed', handleFlowEvent)
    flowEngine.on('flow_advanced', handleFlowEvent)
    flowEngine.on('response_received', handleFlowEvent)

    return () => {
      flowEngine.removeAllListeners()
    }
  }, [queryClient])

  return {
    isInitialized,
    flowEngine,
    templateManager
  }
}

export function useFlowState(patientId: string) {
  const { flowEngine } = useFlowEngine()

  return useQuery({
    queryKey: ['flow-state', patientId],
    queryFn: () => flowEngine.getFlowState(patientId),
    enabled: !!patientId,
    staleTime: 30000, // 30 seconds
    refetchInterval: 60000 // 1 minute
  })
}

export function useFlowTemplates() {
  const { templateManager } = useFlowEngine()

  return useQuery({
    queryKey: ['flow-templates'],
    queryFn: () => templateManager.getAllTemplates(),
    staleTime: 300000 // 5 minutes
  })
}

export function useFlowAnalytics() {
  const { flowEngine } = useFlowEngine()

  return useQuery({
    queryKey: ['flow-analytics'],
    queryFn: () => flowEngine.getAnalytics(),
    staleTime: 60000, // 1 minute
    refetchInterval: 300000 // 5 minutes
  })
}

export function useStartFlow() {
  const { flowEngine } = useFlowEngine()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ patientId, flowType }: { patientId: string; flowType: FlowType }) =>
      flowEngine.startFlow(patientId, flowType),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['flows'] })
      queryClient.invalidateQueries({ queryKey: ['flow-state', variables.patientId] })
      queryClient.setQueryData(['flow-state', variables.patientId], data)
    }
  })
}

export function useAdvanceFlow() {
  const { flowEngine } = useFlowEngine()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ patientId, forceDay }: { patientId: string; forceDay?: number }) =>
      flowEngine.advanceFlow(patientId, forceDay),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['flows'] })
      queryClient.invalidateQueries({ queryKey: ['flow-state', variables.patientId] })
      queryClient.setQueryData(['flow-state', variables.patientId], data)
    }
  })
}

export function usePauseFlow() {
  const { flowEngine } = useFlowEngine()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (patientId: string) => flowEngine.pauseFlow(patientId),
    onSuccess: (data, patientId) => {
      queryClient.invalidateQueries({ queryKey: ['flows'] })
      queryClient.invalidateQueries({ queryKey: ['flow-state', patientId] })
      queryClient.setQueryData(['flow-state', patientId], data)
    }
  })
}

export function useResumeFlow() {
  const { flowEngine } = useFlowEngine()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (patientId: string) => flowEngine.resumeFlow(patientId),
    onSuccess: (data, patientId) => {
      queryClient.invalidateQueries({ queryKey: ['flows'] })
      queryClient.invalidateQueries({ queryKey: ['flow-state', patientId] })
      queryClient.setQueryData(['flow-state', patientId], data)
    }
  })
}

export function useProcessResponse() {
  const { flowEngine } = useFlowEngine()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ patientId, message }: { patientId: string; message: InboundMessage }) =>
      flowEngine.processResponse(patientId, message),
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['flows'] })
      queryClient.invalidateQueries({ queryKey: ['flow-state', variables.patientId] })
      queryClient.invalidateQueries({ queryKey: ['messages', variables.patientId] })
    }
  })
}

export function useCreateTemplate() {
  const { templateManager } = useFlowEngine()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (template: FlowTemplate) => templateManager.createTemplate(template),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['flow-templates'] })
    }
  })
}

export function useUpdateTemplate() {
  const { templateManager } = useFlowEngine()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (template: FlowTemplate) => templateManager.updateTemplate(template),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['flow-templates'] })
    }
  })
}

export function useDeleteTemplate() {
  const { templateManager } = useFlowEngine()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ templateId, flowType }: { templateId: string; flowType: FlowType }) =>
      templateManager.deleteTemplate(templateId, flowType),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['flow-templates'] })
    }
  })
}

// Custom hook for flow operations
export function useFlowOperations(patientId: string) {
  const startFlow = useStartFlow()
  const advanceFlow = useAdvanceFlow()
  const pauseFlow = usePauseFlow()
  const resumeFlow = useResumeFlow()
  const processResponse = useProcessResponse()

  const operations = {
    start: useCallback((flowType: FlowType) => 
      startFlow.mutate({ patientId, flowType }), [startFlow, patientId]),
    
    advance: useCallback((forceDay?: number) =>
      advanceFlow.mutate({ patientId, ...(forceDay !== undefined && { forceDay }) }), [advanceFlow, patientId]),
    
    pause: useCallback(() => 
      pauseFlow.mutate(patientId), [pauseFlow, patientId]),
    
    resume: useCallback(() => 
      resumeFlow.mutate(patientId), [resumeFlow, patientId]),
    
    processResponse: useCallback((message: InboundMessage) => 
      processResponse.mutate({ patientId, message }), [processResponse, patientId])
  }

  const isLoading = startFlow.isPending || advanceFlow.isPending || 
                   pauseFlow.isPending || resumeFlow.isPending || 
                   processResponse.isPending

  const error = startFlow.error || advanceFlow.error || 
               pauseFlow.error || resumeFlow.error || 
               processResponse.error

  return {
    operations,
    isLoading,
    error
  }
}
