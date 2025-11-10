// Simple client types export to avoid import errors
export interface ApiResponse<T = unknown> {
  data: T
  status: number
  statusText: string
}

export interface ApiError {
  message: string
  status: number
  details?: unknown
}

// Placeholder for client types that may be needed
export type ClientResponse<T = unknown> = ApiResponse<T>
export type ClientError = ApiError
