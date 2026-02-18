/**
 * useFlowTemplates Hook
 *
 * Custom hook for managing flow template state and operations.
 */

import { useTemplates, type FlowTemplate } from '@/hooks/useTemplates'
import type { TemplateFilter } from '../../TemplateManagementPage'
import { useTemplateList } from '../../utils/useTemplateList'

interface UseFlowTemplatesOptions {
  filter?: TemplateFilter
}

export function useFlowTemplates(options: UseFlowTemplatesOptions = {}) {
  const { loading, listFlowTemplates } = useTemplates()

  return useTemplateList<FlowTemplate>({
    loading,
    listTemplates: listFlowTemplates,
    filter: options.filter,
    includeDraftFilter: true,
    logLabel: 'flow',
    errorStateMessage: 'Erro ao carregar templates de flow',
    toastErrorDescription: 'Falha ao carregar templates de flow',
  })
}
