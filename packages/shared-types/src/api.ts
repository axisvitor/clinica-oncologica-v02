// Shared API Types - Common response structures for frontend and backend

/**
 * Standard paginated response with cursor support
 */
export interface PaginatedResponse<T> {
    data: T[]
    items?: T[] // Backward compatibility alias
    total: number
    page?: number
    size?: number
    pages?: number
    has_more?: boolean
    next_cursor?: string | null
}

/**
 * Standard API response wrapper
 */
export interface ApiResponse<T> {
    data: T
    message?: string
    success: boolean
    timestamp?: string
}

/**
 * Error response structure
 */
export interface ApiErrorResponse {
    error: {
        message: string
        code: string
        details?: Record<string, unknown>
    }
    timestamp?: string
}

/**
 * Base filter parameters for list endpoints
 */
export interface BaseFilters {
    page?: number
    size?: number
    limit?: number
    cursor?: string
    sortBy?: string
    sortOrder?: 'asc' | 'desc'
}

/**
 * Search filters extending base filters
 */
export interface SearchFilters extends BaseFilters {
    search?: string
    q?: string
}

/**
 * Time range filters
 */
export interface TimeRangeFilters {
    start_date?: string
    end_date?: string
    created_after?: string
    created_before?: string
}

/**
 * Generic success message response
 */
export interface MessageResponse {
    message: string
    success?: boolean
}

/**
 * Entity ID type
 */
export type EntityId = string | number
