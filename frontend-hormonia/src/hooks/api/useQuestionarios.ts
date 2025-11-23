import { useQuery, UseQueryResult } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'

interface QuizTemplate {
  id: string
  name: string
  version: string
  questions: unknown[]
  is_active: boolean
  created_at: string
  updated_at: string
  analytics?: {
    total_responses: number
    completion_rate: number
    average_completion_time?: number
  }
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

export function useQuestionarios(options?: UseQuestionariosOptions): UseQueryResult<QuestionariosResponse> {
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
      const resultData = (result as any)?.items || (Array.isArray(result) ? result : [])

      // NOTE: Backend doesn't support server-side filtering yet,
      // so we do client-side for now but structure is ready for migration
      let filtered = resultData

      // Search filter
      if (search) {
        filtered = filtered.filter((t: any) =>
          t.name.toLowerCase().includes(search.toLowerCase())
        )
      }

      // Type filter
      if (type !== 'all') {
        filtered = filtered.filter((t: any) => {
          const templateType = t.name.toLowerCase().includes('medical') ||
            t.name.toLowerCase().includes('oncolog') ? 'medical' : 'wellness'
          return templateType === type
        })
      }

      // Status filter
      if (status !== 'all') {
        filtered = filtered.filter((t: any) => {
          const isActive = t.is_active
          return (status === 'active' && isActive) || (status === 'inactive' && !isActive)
        })
      }

      // Sort
      filtered.sort((a: any, b: any) => {
        let aValue, bValue
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
        paginatedData.map(async (template: any) => {
          try {
            const analytics = await (apiClient as any).quizzes.getTemplateAnalytics(template.id)
            return { ...template, analytics }
          } catch (error) {
            return {
              ...template,
              analytics: {
                total_responses: 0,
                completion_rate: 0,
                average_completion_time: null
              }
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
