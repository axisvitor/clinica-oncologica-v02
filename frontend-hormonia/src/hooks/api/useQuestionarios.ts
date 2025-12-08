import { useQuery, UseQueryResult } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'

interface QuizTemplateAnalytics {
  total_responses: number
  completion_rate: number
  average_completion_time?: number | null
}

interface QuizTemplate {
  id: string
  name: string
  version: string
  questions: unknown[]
  is_active: boolean
  created_at: string
  updated_at: string
  analytics?: QuizTemplateAnalytics
}

interface UseQuestionariosOptions {
  search?: string
  type?: 'all' | 'medical' | 'wellness'
  status?: 'all' | 'active' | 'inactive'
  sortBy?: 'created_at' | 'name' | 'responses'
  sortOrder?: 'asc' | 'desc'
  page?: number
  size?: number
}

interface QuestionariosResponse {
  items: QuizTemplate[]
  total: number
  page: number
  size: number
}

export function useQuestionarios(options?: UseQuestionariosOptions) {
  const {
    search = '',
    type = 'all',
    status = 'all',
    sortBy = 'created_at',
    sortOrder = 'desc',
    page = 1,
    size = 12
  } = options ?? {}

  return useQuery({
    queryKey: ['questionarios', { search, type, status, sortBy, sortOrder, page, size }],
    queryFn: async () => {
      // Build query params for future server-side filtering
      const params = new URLSearchParams()
      if (search) params.append('search', search)
      if (type !== 'all') params.append('type', type)
      if (status !== 'all') params.append('status', status)
      params.append('sort_by', sortBy)
      params.append('sort_order', sortOrder)
      params.append('page', page.toString())
      params.append('size', size.toString())

      // Fetch templates
      const result = await apiClient.quizzes.listTemplates()
      type ResultType = { items?: QuizTemplate[] } | QuizTemplate[]
      const resultData: QuizTemplate[] = ((result as ResultType) as { items?: QuizTemplate[] })?.items ||
        (Array.isArray(result) ? result as QuizTemplate[] : [])

      // NOTE: Backend doesn't support server-side filtering yet,
      // so we do client-side for now but structure is ready for migration
      let filtered: QuizTemplate[] = resultData

      // Search filter
      if (search) {
        filtered = filtered.filter((t: QuizTemplate) =>
          t.name.toLowerCase().includes(search.toLowerCase())
        )
      }

      // Type filter
      if (type !== 'all') {
        filtered = filtered.filter((t: QuizTemplate) => {
          const templateType = t.name.toLowerCase().includes('medical') ||
            t.name.toLowerCase().includes('oncolog') ? 'medical' : 'wellness'
          return templateType === type
        })
      }

      // Status filter
      if (status !== 'all') {
        filtered = filtered.filter((t: QuizTemplate) => {
          const isActive = t.is_active
          return (status === 'active' && isActive) || (status === 'inactive' && !isActive)
        })
      }

      // Sort
      filtered.sort((a: QuizTemplate, b: QuizTemplate) => {
        let aValue: string | number | Date, bValue: string | number | Date
        switch (sortBy) {
          case 'name':
            aValue = a.name.toLowerCase()
            bValue = b.name.toLowerCase()
            break
          case 'responses':
            aValue = a.analytics?.total_responses || 0
            bValue = b.analytics?.total_responses || 0
            break
          default:
            aValue = new Date(a.created_at)
            bValue = new Date(b.created_at)
        }
        const comparison = aValue < bValue ? -1 : aValue > bValue ? 1 : 0
        return sortOrder === 'asc' ? comparison : -comparison
      })

      // Pagination
      const total = filtered.length
      const start = (page - 1) * size
      const paginatedData = filtered.slice(start, start + size)

      // Fetch analytics for paginated templates
      const templatesWithAnalytics = await Promise.all(
        paginatedData.map(async (template: QuizTemplate) => {
          try {
            // Type-safe access to analytics endpoint
            type QuizClient = typeof apiClient.quizzes & { getTemplateAnalytics?: (id: string) => Promise<QuizTemplate['analytics']> }
            const quizClient = apiClient.quizzes as QuizClient
            const analytics = quizClient.getTemplateAnalytics
              ? await quizClient.getTemplateAnalytics(template.id)
              : undefined
            return { ...template, analytics }
          } catch {
            return {
              ...template,
              analytics: {
                total_responses: 0,
                completion_rate: 0,
                average_completion_time: null
              } as QuizTemplateAnalytics
            }
          }
        })
      )

      return {
        items: templatesWithAnalytics,
        total,
        page,
        size
      }
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 10 * 60 * 1000,
    retry: 3
  })
}
