/**
 * Response transformation utilities to harmonize Backend and Frontend data structures
 */

/**
 * Transform backend pagination response to frontend format
 */
export function transformPaginationResponse<T>(
  backendResponse: any,
  responseType: 'patients' | 'messages' | 'default' = 'default'
): PaginatedResponse<T> {
  switch (responseType) {
    case 'patients':
      // Backend returns: { data, total, page, limit, pages }
      // Frontend expects: { items, total, page, size, pages }
      return {
        items: backendResponse.data || [],
        total: backendResponse.total || 0,
        page: backendResponse.page || 1,
        size: backendResponse.limit || 20,
        pages: backendResponse.pages || 1
      };

    case 'messages':
      // Backend returns: { messages, total, skip, limit }
      // Frontend expects: { items, total, page, size, pages }
      const messagesPage = Math.floor((backendResponse.skip || 0) / (backendResponse.limit || 20)) + 1;
      const messagesPages = Math.ceil((backendResponse.total || 0) / (backendResponse.limit || 20));
      return {
        items: backendResponse.messages || [],
        total: backendResponse.total || 0,
        page: messagesPage,
        size: backendResponse.limit || 20,
        pages: messagesPages
      };

    default:
      // Generic transformation - try to detect the structure
      if ('data' in backendResponse) {
        return transformPaginationResponse<T>(backendResponse, 'patients');
      } else if ('messages' in backendResponse) {
        return transformPaginationResponse<T>(backendResponse, 'messages');
      } else if ('items' in backendResponse) {
        // Already in correct format
        return backendResponse as PaginatedResponse<T>;
      } else if (Array.isArray(backendResponse)) {
        // Simple array - wrap in pagination structure
        return {
          items: backendResponse,
          total: backendResponse.length,
          page: 1,
          size: backendResponse.length,
          pages: 1
        };
      }

      // Fallback - return as is
      return backendResponse as PaginatedResponse<T>;
  }
}

/**
 * Transform reports download response
 * Backend returns binary/stream, Frontend needs Blob
 */
export async function transformReportDownload(response: Response): Promise<{
  blob: Blob;
  filename: string;
  contentType: string;
}> {
  // Get filename from Content-Disposition header if available
  const contentDisposition = response.headers.get('content-disposition');
  let filename = 'report.pdf';

  if (contentDisposition) {
    const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
    if (filenameMatch && filenameMatch[1]) {
      filename = filenameMatch[1].replace(/['"]/g, '');
    }
  }

  // Get content type
  const contentType = response.headers.get('content-type') || 'application/pdf';

  // Get blob
  const blob = await response.blob();

  return {
    blob,
    filename,
    contentType
  };
}

/**
 * PaginatedResponse interface (should match the one in api-client.ts)
 */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

/**
 * Transform flow list response
 * Backend returns array, Frontend expects PaginatedResponse
 */
export function transformFlowListResponse(flows: any[]): PaginatedResponse<any> {
  return {
    items: flows,
    total: flows.length,
    page: 1,
    size: flows.length,
    pages: 1
  };
}