export interface ApiResponse<T> {
  data: T
  message?: string
  success: boolean
  timestamp?: string
}

export interface PaginatedResponse<T> {
  data: T[]
  items?: T[]
  pagination?: {
    page: number
    limit: number
    total: number
    hasMore: boolean
  }
  total?: number
  page?: number
  size?: number
  pages?: number
  has_more?: boolean
  next_cursor?: string | null
}

export interface ApiErrorResponse {
  error: {
    message: string
    code: string
    details?: Record<string, unknown>
  }
  timestamp?: string
}

export type EntityId = string | number

export interface BaseFilters {
  page?: number
  size?: number
  limit?: number
  cursor?: string
  sortBy?: string
  sortOrder?: 'asc' | 'desc'
}

export interface SearchFilters extends BaseFilters {
  search?: string
  q?: string
}

export interface TimeRangeFilters {
  start_date?: string
  end_date?: string
  created_after?: string
  created_before?: string
}

export interface CreateResponse {
  id: EntityId
  createdAt: string
  created_at?: string
}

export interface UpdateResponse {
  id: EntityId
  updatedAt: string
  updated_at?: string
}

export interface DeleteResponse {
  success: boolean
  message: string
  deletedAt?: string
  deleted_at?: string
}

export interface MessageResponse {
  message: string
  success?: boolean
}

export interface ListResponse<T> {
  items: T[]
  total: number
}

export interface ListWithMetadata<T> {
  items: T[]
  total: number
  metadata?: Record<string, unknown>
}
