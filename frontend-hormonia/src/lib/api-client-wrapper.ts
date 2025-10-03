// @ts-nocheck
// TODO: Fix TypeScript errors in this file

/**
 * API Client Wrapper with RLS Error Handling
 *
 * This module provides a wrapper around API clients (both Supabase and REST APIs)
 * with comprehensive error handling for RLS violations and authentication errors.
 *
 * Features:
 * - Automatic RLS error detection and handling
 * - Authentication error processing
 * - Retry logic for transient errors
 * - Request/response interceptors
 * - User-friendly error messages
 */

import { SupabaseClient } from '@supabase/supabase-js'
import {
  errorHandler,
  createUserFriendlyError,
  isRLSError,
  isRetryableError,
  requiresAuthentication,
  getPermissionContext,
  AuthErrorType,
  UserFriendlyError
} from './auth-error-handler'

// HTTP client configuration
export interface ApiClientConfig {
  baseURL: string
  timeout?: number
  retryAttempts?: number
  retryDelay?: number
  headers?: Record<string, string>
  onAuthRequired?: () => void
  onError?: (error: UserFriendlyError) => void
}

// Request/response types
export interface ApiRequest {
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'
  url: string
  data?: any
  headers?: Record<string, string>
  params?: Record<string, any>
}

export interface ApiResponse<T = any> {
  data: T
  status: number
  statusText: string
  headers: Record<string, string>
}

/**
 * Enhanced Supabase client wrapper with RLS error handling
 */
export class SupabaseClientWrapper {
  private client: SupabaseClient
  private onAuthRequired?: () => void
  private onError?: (error: UserFriendlyError) => void

  constructor(
    client: SupabaseClient,
    options?: {
      onAuthRequired?: () => void
      onError?: (error: UserFriendlyError) => void
    }
  ) {
    this.client = client
    this.onAuthRequired = options?.onAuthRequired
    this.onError = options?.onError
  }

  /**
   * Execute a Supabase query with comprehensive error handling
   */
  async executeQuery<T>(
    queryBuilder: any,
    context?: string
  ): Promise<T> {
    try {
      const { data, error } = await queryBuilder

      if (error) {
        return this.handleSupabaseError(error, context)
      }

      return data
    } catch (error) {
      return this.handleSupabaseError(error, context)
    }
  }

  /**
   * Handle Supabase-specific errors
   */
  private handleSupabaseError(error: any, context?: string): never {
    // Create user-friendly error
    const userFriendlyError = createUserFriendlyError(error, context)

    // Handle authentication requirements
    if (requiresAuthentication(error)) {
      this.onAuthRequired?.()
    }

    // Emit error to global handler
    this.onError?.(userFriendlyError)

    // Throw enhanced error
    throw new SupabaseOperationError(userFriendlyError, error)
  }

  /**
   * Get data from a table with error handling
   */
  async from<T>(tableName: string) {
    return {
      select: (columns = '*') => ({
        // Add common query methods with error handling
        eq: (column: string, value: any) => this.buildQuery(tableName, 'select', { columns, filters: { [column]: value } }),
        neq: (column: string, value: any) => this.buildQuery(tableName, 'select', { columns, filters: { [`${column}:neq`]: value } }),
        gt: (column: string, value: any) => this.buildQuery(tableName, 'select', { columns, filters: { [`${column}:gt`]: value } }),
        gte: (column: string, value: any) => this.buildQuery(tableName, 'select', { columns, filters: { [`${column}:gte`]: value } }),
        lt: (column: string, value: any) => this.buildQuery(tableName, 'select', { columns, filters: { [`${column}:lt`]: value } }),
        lte: (column: string, value: any) => this.buildQuery(tableName, 'select', { columns, filters: { [`${column}:lte`]: value } }),
        like: (column: string, pattern: string) => this.buildQuery(tableName, 'select', { columns, filters: { [`${column}:like`]: pattern } }),
        ilike: (column: string, pattern: string) => this.buildQuery(tableName, 'select', { columns, filters: { [`${column}:ilike`]: pattern } }),
        in: (column: string, values: any[]) => this.buildQuery(tableName, 'select', { columns, filters: { [`${column}:in`]: values } }),
        order: (column: string, options?: { ascending?: boolean }) => this.buildQuery(tableName, 'select', { columns, order: { column, ascending: options?.ascending ?? true } }),
        limit: (count: number) => this.buildQuery(tableName, 'select', { columns, limit: count }),
        range: (from: number, to: number) => this.buildQuery(tableName, 'select', { columns, range: { from, to } }),
        single: () => this.buildQuery(tableName, 'select', { columns, single: true })
      }),

      insert: (data: any) => this.buildQuery(tableName, 'insert', { data }),
      update: (data: any) => ({
        eq: (column: string, value: any) => this.buildQuery(tableName, 'update', { data, filters: { [column]: value } }),
        match: (filters: Record<string, any>) => this.buildQuery(tableName, 'update', { data, filters })
      }),
      delete: () => ({
        eq: (column: string, value: any) => this.buildQuery(tableName, 'delete', { filters: { [column]: value } }),
        match: (filters: Record<string, any>) => this.buildQuery(tableName, 'delete', { filters })
      })
    }
  }

  /**
   * Build and execute query with error handling
   */
  private async buildQuery(tableName: string, operation: string, options: any) {
    const context = getPermissionContext(tableName, operation)

    try {
      let query = this.client.from(tableName)

      // Build query based on operation
      switch (operation) {
        case 'select':
          query = query.select(options.columns || '*')
          break
        case 'insert':
          query = query.insert(options.data)
          break
        case 'update':
          query = query.update(options.data)
          break
        case 'delete':
          query = query.delete()
          break
      }

      // Apply filters
      if (options.filters) {
        Object.entries(options.filters).forEach(([key, value]) => {
          if (key.includes(':')) {
            const [column, operator] = key.split(':')
            switch (operator) {
              case 'neq':
                query = query.neq(column, value)
                break
              case 'gt':
                query = query.gt(column, value)
                break
              case 'gte':
                query = query.gte(column, value)
                break
              case 'lt':
                query = query.lt(column, value)
                break
              case 'lte':
                query = query.lte(column, value)
                break
              case 'like':
                query = query.like(column, value as string)
                break
              case 'ilike':
                query = query.ilike(column, value as string)
                break
              case 'in':
                query = query.in(column, value as any[])
                break
            }
          } else {
            query = query.eq(key, value)
          }
        })
      }

      // Apply ordering
      if (options.order) {
        query = query.order(options.order.column, { ascending: options.order.ascending })
      }

      // Apply limit
      if (options.limit) {
        query = query.limit(options.limit)
      }

      // Apply range
      if (options.range) {
        query = query.range(options.range.from, options.range.to)
      }

      // Execute query
      const { data, error } = options.single ? await query.single() : await query

      if (error) {
        this.handleSupabaseError(error, context)
      }

      return data
    } catch (error) {
      this.handleSupabaseError(error, context)
    }
  }

  /**
   * Get the underlying Supabase client
   */
  getClient(): SupabaseClient {
    return this.client
  }
}

/**
 * HTTP API client wrapper with error handling
 */
export class HttpApiClient {
  private config: ApiClientConfig

  constructor(config: ApiClientConfig) {
    this.config = {
      timeout: 30000,
      retryAttempts: 3,
      retryDelay: 1000,
      ...config
    }
  }

  /**
   * Make HTTP request with error handling and retries
   */
  async request<T>(request: ApiRequest): Promise<ApiResponse<T>> {
    let lastError: any
    let attempt = 0

    while (attempt <= (this.config.retryAttempts || 3)) {
      try {
        const response = await this.executeRequest<T>(request)
        return response
      } catch (error) {
        lastError = error
        attempt++

        // Check if error is retryable
        if (!isRetryableError(error) || attempt > (this.config.retryAttempts || 3)) {
          break
        }

        // Wait before retry
        await this.delay((this.config.retryDelay || 1000) * attempt)
      }
    }

    // Handle final error
    return this.handleHttpError(lastError, request)
  }

  /**
   * Execute HTTP request
   */
  private async executeRequest<T>(request: ApiRequest): Promise<ApiResponse<T>> {
    const url = `${this.config.baseURL}${request.url}`
    const headers = {
      'Content-Type': 'application/json',
      ...this.config.headers,
      ...request.headers
    }

    const fetchOptions: RequestInit = {
      method: request.method,
      headers,
      signal: AbortSignal.timeout(this.config.timeout || 30000)
    }

    // Add body for POST/PUT/PATCH requests
    if (request.data && ['POST', 'PUT', 'PATCH'].includes(request.method)) {
      fetchOptions.body = JSON.stringify(request.data)
    }

    // Add query parameters
    const searchParams = new URLSearchParams()
    if (request.params) {
      Object.entries(request.params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          searchParams.append(key, String(value))
        }
      })
    }

    const finalUrl = searchParams.toString() ? `${url}?${searchParams}` : url

    const response = await fetch(finalUrl, fetchOptions)

    let data: T
    try {
      const text = await response.text()
      data = text ? JSON.parse(text) : null
    } catch {
      data = null as T
    }

    if (!response.ok) {
      throw {
        status: response.status,
        statusText: response.statusText,
        data,
        message: `HTTP ${response.status}: ${response.statusText}`
      }
    }

    return {
      data,
      status: response.status,
      statusText: response.statusText,
      headers: Object.fromEntries(response.headers.entries())
    }
  }

  /**
   * Handle HTTP errors
   */
  private handleHttpError(error: any, request: ApiRequest): never {
    const context = `${request.method} ${request.url}`
    const userFriendlyError = createUserFriendlyError(error, context)

    // Handle authentication requirements
    if (requiresAuthentication(error)) {
      this.config.onAuthRequired?.()
    }

    // Emit error
    this.config.onError?.(userFriendlyError)

    throw new HttpOperationError(userFriendlyError, error)
  }

  /**
   * Convenience methods
   */
  async get<T>(url: string, params?: Record<string, any>, headers?: Record<string, string>): Promise<ApiResponse<T>> {
    return this.request<T>({ method: 'GET', url, params, headers })
  }

  async post<T>(url: string, data?: any, headers?: Record<string, string>): Promise<ApiResponse<T>> {
    return this.request<T>({ method: 'POST', url, data, headers })
  }

  async put<T>(url: string, data?: any, headers?: Record<string, string>): Promise<ApiResponse<T>> {
    return this.request<T>({ method: 'PUT', url, data, headers })
  }

  async patch<T>(url: string, data?: any, headers?: Record<string, string>): Promise<ApiResponse<T>> {
    return this.request<T>({ method: 'PATCH', url, data, headers })
  }

  async delete<T>(url: string, headers?: Record<string, string>): Promise<ApiResponse<T>> {
    return this.request<T>({ method: 'DELETE', url, headers })
  }

  /**
   * Update configuration
   */
  updateConfig(config: Partial<ApiClientConfig>) {
    this.config = { ...this.config, ...config }
  }

  /**
   * Set authentication token
   */
  setAuthToken(token: string) {
    this.config.headers = {
      ...this.config.headers,
      'Authorization': `Bearer ${token}`
    }
  }

  /**
   * Remove authentication token
   */
  clearAuthToken() {
    if (this.config.headers) {
      delete this.config.headers['Authorization']
    }
  }

  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms))
  }
}

/**
 * Custom error classes
 */
export class SupabaseOperationError extends Error {
  constructor(
    public userFriendlyError: UserFriendlyError,
    public originalError: any
  ) {
    super(userFriendlyError.message)
    this.name = 'SupabaseOperationError'
  }
}

export class HttpOperationError extends Error {
  constructor(
    public userFriendlyError: UserFriendlyError,
    public originalError: any
  ) {
    super(userFriendlyError.message)
    this.name = 'HttpOperationError'
  }
}

/**
 * Factory function to create API clients
 */
export function createApiClient(config: ApiClientConfig): HttpApiClient {
  return new HttpApiClient(config)
}

/**
 * Factory function to create enhanced Supabase client
 */
export function createSupabaseWrapper(
  client: SupabaseClient,
  options?: {
    onAuthRequired?: () => void
    onError?: (error: UserFriendlyError) => void
  }
): SupabaseClientWrapper {
  return new SupabaseClientWrapper(client, options)
}

/**
 * Global error handler setup
 */
export function setupGlobalErrorHandling(options: {
  onAuthRequired?: () => void
  onRLSViolation?: (error: UserFriendlyError) => void
  onNetworkError?: (error: UserFriendlyError) => void
}) {
  return errorHandler.onError((error) => {
    switch (error.type) {
      case AuthErrorType.AUTHENTICATION_REQUIRED:
      case AuthErrorType.SESSION_EXPIRED:
        options.onAuthRequired?.()
        break
      case AuthErrorType.RLS_VIOLATION:
      case AuthErrorType.INSUFFICIENT_PERMISSIONS:
        options.onRLSViolation?.(error)
        break
      case AuthErrorType.NETWORK_ERROR:
        options.onNetworkError?.(error)
        break
    }
  })
}