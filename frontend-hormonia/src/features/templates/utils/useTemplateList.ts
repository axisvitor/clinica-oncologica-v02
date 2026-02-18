import { useCallback, useEffect, useState } from 'react'
import { useToast } from '@/components/ui/use-toast'
import { logger } from '@/lib/logger'
import type { TemplateFilter } from '../TemplateManagementPage'

type TemplateListParams = {
  page: number
  size: number
  is_active?: boolean
  is_draft?: boolean
}

type TemplateListResponse<T> = {
  items: T[]
  pages: number
}

type ListTemplatesFn<T> = (params: TemplateListParams) => Promise<TemplateListResponse<T> | null | undefined>

type UseTemplateListOptions<T> = {
  loading: boolean
  listTemplates: ListTemplatesFn<T>
  filter?: TemplateFilter
  includeDraftFilter?: boolean
  logLabel: string
  errorStateMessage: string
  toastErrorDescription: string
}

export function useTemplateList<T>({
  loading,
  listTemplates,
  filter,
  includeDraftFilter = false,
  logLabel,
  errorStateMessage,
  toastErrorDescription,
}: UseTemplateListOptions<T>) {
  const { toast } = useToast()

  const [templates, setTemplates] = useState<T[]>([])
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)

  const loadTemplates = useCallback(async () => {
    try {
      setError(null)
      const params: TemplateListParams = { page, size: 10 }

      if (filter === 'active') {
        params.is_active = true
      }
      if (includeDraftFilter && filter === 'draft') {
        params.is_draft = true
      }

      const response = await listTemplates(params)
      if (response) {
        setTemplates(response.items)
        setTotalPages(response.pages)
      }
    } catch (err) {
      logger.error(`Failed to load ${logLabel} templates`, err)
      setError(errorStateMessage)
      toast({
        title: 'Erro',
        description: toastErrorDescription,
        variant: 'destructive',
      })
    }
  }, [errorStateMessage, filter, includeDraftFilter, listTemplates, logLabel, page, toast, toastErrorDescription])

  useEffect(() => {
    loadTemplates()
  }, [loadTemplates])

  return {
    templates,
    loading,
    error,
    page,
    totalPages,
    setPage,
    refetch: loadTemplates,
  }
}
