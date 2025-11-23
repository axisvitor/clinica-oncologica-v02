/**
 * CORS Validation for Quiz API
 * Validates origin and adds appropriate CORS headers
 */

import { NextRequest, NextResponse } from 'next/server'

/**
 * Allowed origins for CORS
 * In production, this should be configured via environment variables
 */
function getAllowedOrigins(): string[] {
  const envOrigins = process.env.ALLOWED_ORIGINS

  if (envOrigins) {
    return envOrigins.split(',').map(origin => origin.trim())
  }

  // Default allowed origins
  const origins = ['http://localhost:3000']

  // Add production domains if available
  if (process.env.NEXT_PUBLIC_APP_URL) {
    origins.push(process.env.NEXT_PUBLIC_APP_URL)
  }

  return origins
}

const ALLOWED_ORIGINS = getAllowedOrigins()

/**
 * Validate request origin against whitelist
 */
export function validateOrigin(request: NextRequest): boolean {
  const origin = request.headers.get('origin')

  // If no origin header, it's a same-origin request
  if (!origin) {
    return true
  }

  // Check if origin is in whitelist
  return ALLOWED_ORIGINS.some(allowedOrigin => {
    // Support wildcard subdomains (e.g., *.example.com)
    if (allowedOrigin.startsWith('*.')) {
      const domain = allowedOrigin.substring(2)
      return origin.endsWith(domain)
    }
    return origin === allowedOrigin
  })
}

/**
 * Add CORS headers to response
 */
export function addCorsHeaders(response: NextResponse, request: NextRequest): NextResponse {
  const origin = request.headers.get('origin')

  if (origin && validateOrigin(request)) {
    response.headers.set('Access-Control-Allow-Origin', origin)
    response.headers.set('Access-Control-Allow-Credentials', 'true')
    response.headers.set('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    response.headers.set('Access-Control-Allow-Headers', 'Content-Type, X-CSRF-Token')
    response.headers.set('Access-Control-Max-Age', '86400') // 24 hours
  }

  return response
}

/**
 * Handle CORS preflight requests
 */
export function handleCorsPreFlight(request: NextRequest): NextResponse | null {
  if (request.method !== 'OPTIONS') {
    return null
  }

  if (!validateOrigin(request)) {
    return NextResponse.json(
      { error: 'Origin not allowed' },
      { status: 403 }
    )
  }

  const response = new NextResponse(null, { status: 204 })
  return addCorsHeaders(response, request)
}

/**
 * CORS middleware wrapper
 */
export function withCors(
  handler: (request: NextRequest) => Promise<NextResponse>
) {
  return async (request: NextRequest): Promise<NextResponse> => {
    // Handle preflight
    const preflightResponse = handleCorsPreFlight(request)
    if (preflightResponse) {
      return preflightResponse
    }

    // Validate origin for actual requests
    if (!validateOrigin(request)) {
      return NextResponse.json(
        { error: 'Origin not allowed' },
        { status: 403 }
      )
    }

    // Execute handler
    const response = await handler(request)

    // Add CORS headers
    return addCorsHeaders(response, request)
  }
}
