// Simple client types export to avoid import errors
export interface ApiResponse<T = any> {
  data: T
  status: number
  statusText: string
}

export interface ApiError {
  message: string
  status: number
  details?: any
}

// Placeholder for client types that may be needed
export type ClientResponse<T = any> = ApiResponse<T>
export type ClientError = ApiError