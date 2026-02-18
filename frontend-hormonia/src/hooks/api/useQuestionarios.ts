import { useQuery, type UseQueryOptions } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import type { QuizTemplate, QuizTemplateResponse } from '@/lib/api-client/types'

interface QuestionariosResponse {
  items: QuizTemplate[]
  total: number
  page: number
  size: number
}

type TemplateAnalytics = NonNullable<QuizTemplate['analytics']>
type TemplatesResponse = QuizTemplateResponse | QuizTemplate[]
type QuestionariosQueryOverrides = Omit<
  UseQueryOptions<QuestionariosResponse, Error>,
  'queryKey' | 'queryFn'
>

const getEmptyAnalytics = (): TemplateAnalytics => ({
  total_responses: 0,
  completion_rate: 0,
  average_completion_time: undefined
})

interface UseQuestionariosOptions {
  search?: string
  type?: 'all' | 'medical' | 'wellness'
  status?: 'all' | 'active' | 'inactive'
  sortBy?: 'created_at' | 'name' | 'responses'
  sortOrder?: 'asc' | 'desc'
  page?: number
  size?: number
  queryOverrides?: QuestionariosQueryOverrides // For testing (e.g. retry: 0)
}

export function useQuestionarios(options?: UseQuestionariosOptions) {
  const {
    search = '',
    type = 'all',
    status = 'all',
    sortBy = 'created_at',
    sortOrder = 'desc',
    page = 1,
    size = 12,
    queryOverrides = {}
  } = options ?? {}

  return useQuery<QuestionariosResponse, Error>({
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
      const result = await apiClient.quizzes.listTemplates({ limit: 100 }) as TemplatesResponse
      const resultData = Array.isArray(result) ? result : result.items ?? []

      // Filter
      let filtered: QuizTemplate[] = resultData

      if (search) {
        filtered = filtered.filter((t: QuizTemplate) =>
          t.name.toLowerCase().includes(search.toLowerCase())
        )
      }

      if (type !== 'all') {
        filtered = filtered.filter((t: QuizTemplate) => {
          const templateType = t.name.toLowerCase().includes('medical') ||
            t.name.toLowerCase().includes('oncolog') ? 'medical' : 'wellness'
          return templateType === type
        })
      }

      if (status !== 'all') {
        filtered = filtered.filter((t: QuizTemplate) => {
          const isActive = t.is_active
          return (status === 'active' && isActive) || (status === 'inactive' && !isActive)
        })
      }

      // If sorting by responses, we MUST fetch analytics for all filtered items first
      // since the backend doesn't support server-side sorting for this virtual field yet
      if (sortBy === 'responses') {
        filtered = (await Promise.all(
          filtered.map(async (template: QuizTemplate) => {
            try {
              const analytics = await apiClient.quizzes.getTemplateAnalytics(template.id) as TemplateAnalytics
              return { ...template, analytics }
            } catch {
              return {
                ...template,
                analytics: getEmptyAnalytics()
              }
            }
          })
        ))
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

      // Fetch analytics for paginated templates (if not already fetched for sorting)
      const templatesWithAnalytics = await Promise.all(
        paginatedData.map(async (template: QuizTemplate) => {
          if (template.analytics) return template
          try {
            const analytics = await apiClient.quizzes.getTemplateAnalytics(template.id) as TemplateAnalytics
            return { ...template, analytics }
          } catch {
            return {
              ...template,
              analytics: getEmptyAnalytics()
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
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
    retry: 3,
    ...queryOverrides
  })
}
