/**
 * useQuizTemplates Hook
 *
 * Custom hook for managing quiz template state and operations.
 */

import { useTemplates, type QuizTemplate } from '@/hooks/useTemplates'
import type { TemplateFilter } from '../../TemplateManagementPage'
import { useTemplateList } from '../../utils/useTemplateList'

interface UseQuizTemplatesOptions {
  filter?: TemplateFilter
}

export function useQuizTemplates(options: UseQuizTemplatesOptions = {}) {
  const { loading, listQuizTemplates } = useTemplates()

  return useTemplateList<QuizTemplate>({
    loading,
    listTemplates: listQuizTemplates,
    filter: options.filter,
    logLabel: 'quiz',
    errorStateMessage: 'Erro ao carregar templates de quiz',
    toastErrorDescription: 'Falha ao carregar templates de quiz',
  })
}
