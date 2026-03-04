/**
 * Response transformation utilities to harmonize Backend and Frontend data structures
 */

/**
 * Transform backend pagination response to frontend format
 */
export function transformPaginationResponse<T>(
  backendResponse: unknown,
  responseType: 'patients' | 'messages' | 'default' = 'default'
): PaginatedResponse<T> {
  const response = backendResponse as Record<string, unknown>
  switch (responseType) {
    case 'patients':
      // Backend returns: { data, total, page, limit, pages }
      // Frontend expects: { items, total, page, size, pages }
      return {
        items: (response['data'] as T[]) || [],
        total: (response['total'] as number) || 0,
        page: (response['page'] as number) || 1,
        size: (response['limit'] as number) || 20,
        pages: (response['pages'] as number) || 1,
      }

    case 'messages': {
      // Backend returns: { messages, total, skip, limit }
      // Frontend expects: { items, total, page, size, pages }
      const messagesPage =
        Math.floor(((response['skip'] as number) || 0) / ((response['limit'] as number) || 20)) + 1
      const messagesPages = Math.ceil(
        ((response['total'] as number) || 0) / ((response['limit'] as number) || 20)
      )
      return {
        items: (response['messages'] as T[]) || [],
        total: (response['total'] as number) || 0,
        page: messagesPage,
        size: (response['limit'] as number) || 20,
        pages: messagesPages,
      }
    }

    default:
      // Generic transformation - try to detect the structure
      if ('data' in response) {
        return transformPaginationResponse<T>(backendResponse, 'patients')
      } else if ('messages' in response) {
        return transformPaginationResponse<T>(backendResponse, 'messages')
      } else if ('items' in response) {
        // Already in correct format
        return response as unknown as PaginatedResponse<T>
      } else if (Array.isArray(backendResponse)) {
        // Simple array - wrap in pagination structure
        return {
          items: backendResponse as T[],
          total: backendResponse.length,
          page: 1,
          size: backendResponse.length,
          pages: 1,
        }
      }

      // Fallback - return as is
      return response as unknown as PaginatedResponse<T>
  }
}

/**
 * Transform reports download response
 * Backend returns binary/stream, Frontend needs Blob
 */
export async function transformReportDownload(response: Response): Promise<{
  blob: Blob
  filename: string
  contentType: string
}> {
  // Get filename from Content-Disposition header if available
  const contentDisposition = response.headers.get('content-disposition')
  let filename = 'report.pdf'

  if (contentDisposition) {
    const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/)
    if (filenameMatch && filenameMatch[1]) {
      filename = filenameMatch[1].replace(/['"]/g, '')
    }
  }

  // Get content type
  const contentType = response.headers.get('content-type') || 'application/pdf'

  // Get blob
  const blob = await response.blob()

  return {
    blob,
    filename,
    contentType,
  }
}

/**
 * PaginatedResponse interface (should match the one in api-client.ts)
 */
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  size: number
  pages: number
}

/**
 * Transform flow list response
 * Backend returns array, Frontend expects PaginatedResponse
 */
export function transformFlowListResponse<T = unknown>(flows: T[]): PaginatedResponse<T> {
  return {
    items: flows,
    total: flows.length,
    page: 1,
    size: flows.length,
    pages: 1,
  }
}
