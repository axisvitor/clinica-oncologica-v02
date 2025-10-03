import { useState, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { FlowDesign } from '../lib/types/flow-designer'

// Extended interface for flow list display
export interface FlowListItem extends FlowDesign {
  status: 'active' | 'inactive' | 'draft' | 'archived'
  executionsCount: number
  successRate: number
  nodesCount: number
}

// Mock API functions - replace with actual API calls
const mockFlowDesigns: FlowListItem[] = [
  {
    id: '1',
    name: 'Fluxo de Onboarding',
    description: 'Processo inicial de cadastro e orientação de novos pacientes',
    version: '1.0.0',
    status: 'active',
    executionsCount: 45,
    successRate: 95,
    nodesCount: 12,
    nodes: [],
    connections: [],
    variables: [],
    metadata: {
      author: 'Dr. Silva',
      tags: ['onboarding', 'pacientes'],
      category: 'inicial',
      complexity_level: 'simple'
    },
    created_at: '2024-01-15T10:00:00Z',
    updated_at: '2024-01-20T15:30:00Z'
  },
  {
    id: '2',
    name: 'Acompanhamento Semanal',
    description: 'Fluxo automatizado de mensagens semanais de acompanhamento',
    version: '1.2.0',
    status: 'active',
    executionsCount: 120,
    successRate: 88,
    nodesCount: 8,
    nodes: [],
    connections: [],
    variables: [],
    metadata: {
      author: 'Dr. Costa',
      tags: ['acompanhamento', 'semanal'],
      category: 'monitoramento',
      complexity_level: 'medium'
    },
    created_at: '2024-01-10T09:00:00Z',
    updated_at: '2024-01-18T14:45:00Z'
  },
  {
    id: '3',
    name: 'Lembretes de Medicação',
    description: 'Envio de lembretes personalizados para medicação',
    version: '2.0.0',
    status: 'inactive',
    executionsCount: 200,
    successRate: 92,
    nodesCount: 6,
    nodes: [],
    connections: [],
    variables: [],
    metadata: {
      author: 'Dra. Santos',
      tags: ['medicação', 'lembretes'],
      category: 'medicação',
      complexity_level: 'simple'
    },
    created_at: '2024-01-05T08:00:00Z',
    updated_at: '2024-01-12T16:20:00Z'
  },
  {
    id: '4',
    name: 'Fluxo de Emergência',
    description: 'Protocolo de resposta rápida para situações de emergência',
    version: '1.0.0',
    status: 'draft',
    executionsCount: 0,
    successRate: 0,
    nodesCount: 15,
    nodes: [],
    connections: [],
    variables: [],
    metadata: {
      author: 'Dr. Lima',
      tags: ['emergência', 'protocolo'],
      category: 'urgência',
      complexity_level: 'complex'
    },
    created_at: '2024-01-20T11:00:00Z',
    updated_at: '2024-01-20T11:00:00Z'
  }
]

// Mock API functions
const flowsApi = {
  async getFlows(): Promise<FlowListItem[]> {
    // Simulate network delay
    await new Promise(resolve => setTimeout(resolve, 800))
    return mockFlowDesigns
  },

  async getFlow(id: string): Promise<FlowDesign> {
    await new Promise(resolve => setTimeout(resolve, 500))
    const flow = mockFlowDesigns.find(f => f.id === id)
    if (!flow) throw new Error('Flow not found')
    return flow
  },

  async createFlow(design: Omit<FlowDesign, 'id' | 'created_at' | 'updated_at'>): Promise<FlowDesign> {
    await new Promise(resolve => setTimeout(resolve, 1000))
    const newFlow: FlowDesign = {
      ...design,
      id: Date.now().toString(),
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    }
    mockFlowDesigns.push({
      ...newFlow,
      status: 'draft',
      executionsCount: 0,
      successRate: 0,
      nodesCount: design.nodes.length
    } as FlowListItem)
    return newFlow
  },

  async updateFlow(id: string, design: Partial<FlowDesign>): Promise<FlowDesign> {
    await new Promise(resolve => setTimeout(resolve, 1000))
    const index = mockFlowDesigns.findIndex(f => f.id === id)
    if (index === -1) throw new Error('Flow not found')

    const updatedFlow = {
      ...mockFlowDesigns[index],
      ...design,
      updated_at: new Date().toISOString(),
      nodesCount: design.nodes?.length || mockFlowDesigns[index].nodesCount
    }

    mockFlowDesigns[index] = updatedFlow
    return updatedFlow
  },

  async deleteFlow(id: string): Promise<void> {
    await new Promise(resolve => setTimeout(resolve, 500))
    const index = mockFlowDesigns.findIndex(f => f.id === id)
    if (index === -1) throw new Error('Flow not found')
    mockFlowDesigns.splice(index, 1)
  },

  async duplicateFlow(id: string): Promise<FlowDesign> {
    await new Promise(resolve => setTimeout(resolve, 800))
    const original = mockFlowDesigns.find(f => f.id === id)
    if (!original) throw new Error('Flow not found')

    const duplicate: FlowDesign = {
      ...original,
      id: Date.now().toString(),
      name: `${original.name} (Cópia)`,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    }

    mockFlowDesigns.push({
      ...duplicate,
      status: 'draft',
      executionsCount: 0,
      successRate: 0
    } as FlowListItem)

    return duplicate
  },

  async updateFlowStatus(id: string, status: FlowListItem['status']): Promise<FlowListItem> {
    await new Promise(resolve => setTimeout(resolve, 500))
    const index = mockFlowDesigns.findIndex(f => f.id === id)
    if (index === -1) throw new Error('Flow not found')

    mockFlowDesigns[index].status = status
    mockFlowDesigns[index].updated_at = new Date().toISOString()

    return mockFlowDesigns[index]
  }
}

// Custom hooks
export function useFlows() {
  return useQuery({
    queryKey: ['flows'],
    queryFn: () => flowsApi.getFlows(),
    staleTime: 5 * 60 * 1000, // 5 minutes
    refetchInterval: 2 * 60 * 1000 // 2 minutes
  })
}

export function useFlow(id: string) {
  return useQuery({
    queryKey: ['flow', id],
    queryFn: () => flowsApi.getFlow(id),
    enabled: !!id,
    staleTime: 5 * 60 * 1000
  })
}

export function useCreateFlow() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (design: Omit<FlowDesign, 'id' | 'created_at' | 'updated_at'>) =>
      flowsApi.createFlow(design),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['flows'] })
    }
  })
}

export function useUpdateFlow() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, design }: { id: string; design: Partial<FlowDesign> }) =>
      flowsApi.updateFlow(id, design),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['flows'] })
      queryClient.setQueryData(['flow', data['id']], data)
    }
  })
}

export function useDeleteFlow() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => flowsApi.deleteFlow(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['flows'] })
    }
  })
}

export function useDuplicateFlow() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: string) => flowsApi.duplicateFlow(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['flows'] })
    }
  })
}

export function useUpdateFlowStatus() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: FlowListItem['status'] }) =>
      flowsApi.updateFlowStatus(id, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['flows'] })
    }
  })
}

// Flow operations hook
export function useFlowOperations() {
  const createFlow = useCreateFlow()
  const updateFlow = useUpdateFlow()
  const deleteFlow = useDeleteFlow()
  const duplicateFlow = useDuplicateFlow()
  const updateStatus = useUpdateFlowStatus()

  const operations = {
    create: useCallback((design: Omit<FlowDesign, 'id' | 'created_at' | 'updated_at'>) =>
      createFlow.mutate(design), [createFlow]),

    update: useCallback((id: string, design: Partial<FlowDesign>) =>
      updateFlow.mutate({ id, design }), [updateFlow]),

    delete: useCallback((id: string) =>
      deleteFlow.mutate(id), [deleteFlow]),

    duplicate: useCallback((id: string) =>
      duplicateFlow.mutate(id), [duplicateFlow]),

    updateStatus: useCallback((id: string, status: FlowListItem['status']) =>
      updateStatus.mutate({ id, status }), [updateStatus])
  }

  const isLoading = createFlow.isPending || updateFlow.isPending ||
                   deleteFlow.isPending || duplicateFlow.isPending ||
                   updateStatus.isPending

  const error = createFlow.error || updateFlow.error ||
               deleteFlow.error || duplicateFlow.error ||
               updateStatus.error

  return {
    operations,
    isLoading,
    error
  }
}

// Flow statistics hook
export function useFlowStatistics() {
  const { data: flows = [] } = useFlows()

  return {
    total: flows.length,
    active: flows.filter(f => f.status === 'active').length,
    inactive: flows.filter(f => f.status === 'inactive').length,
    draft: flows.filter(f => f.status === 'draft').length,
    archived: flows.filter(f => f.status === 'archived').length,
    averageSuccessRate: flows.length > 0
      ? Math.round(flows.reduce((sum, f) => sum + f.successRate, 0) / flows.length)
      : 0,
    totalExecutions: flows.reduce((sum, f) => sum + f.executionsCount, 0)
  }
}