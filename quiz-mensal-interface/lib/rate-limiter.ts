/**
 * Rate Limiting Middleware for Quiz API
 * Implements token bucket algorithm with in-memory storage
 * For production: Use Redis backend for distributed rate limiting
 */

import { NextRequest, NextResponse } from 'next/server'

interface RateLimitConfig {
  maxRequests: number
  windowMs: number
  message?: string
}

interface RateLimitEntry {
  count: number
  resetTime: number
}

// In-memory store (use Redis in production for distributed systems)
const rateLimitStore = new Map<string, RateLimitEntry>()

// Cleanup old entries every 5 minutes
setInterval(() => {
  const now = Date.now()
  for (const [key, entry] of rateLimitStore.entries()) {
    if (now > entry.resetTime) {
      rateLimitStore.delete(key)
    }
  }
}, 5 * 60 * 1000)

/**
 * Generate rate limit key from request
 */
function getRateLimitKey(request: NextRequest, prefix: string): string {
  // Use IP address as identifier
  const ip = request.ip ||
             request.headers.get('x-forwarded-for')?.split(',')[0] ||
             request.headers.get('x-real-ip') ||
             'unknown'

  return `${prefix}:${ip}`
}

/**
 * Rate limiting middleware factory
 */
export function createRateLimiter(config: RateLimitConfig) {
  return async (request: NextRequest, handler: () => Promise<NextResponse>) => {
    const key = getRateLimitKey(request, config.message || 'api')
    const now = Date.now()

    let entry = rateLimitStore.get(key)

    // Initialize or reset if window expired
    if (!entry || now > entry.resetTime) {
      entry = {
        count: 0,
        resetTime: now + config.windowMs
      }
      rateLimitStore.set(key, entry)
    }

    // Increment request count
    entry.count++

    // Check if limit exceeded
    if (entry.count > config.maxRequests) {
      const retryAfter = Math.ceil((entry.resetTime - now) / 1000)

      return NextResponse.json(
        {
          error: config.message || 'Too many requests',
          retryAfter: retryAfter
        },
        {
          status: 429,
          headers: {
            'Retry-After': retryAfter.toString(),
            'X-RateLimit-Limit': config.maxRequests.toString(),
            'X-RateLimit-Remaining': '0',
            'X-RateLimit-Reset': new Date(entry.resetTime).toISOString()
          }
        }
      )
    }

    // Add rate limit headers to response
    const response = await handler()
    response.headers.set('X-RateLimit-Limit', config.maxRequests.toString())
    response.headers.set('X-RateLimit-Remaining', (config.maxRequests - entry.count).toString())
    response.headers.set('X-RateLimit-Reset', new Date(entry.resetTime).toISOString())

    return response
  }
}

/**
 * Predefined rate limiters for quiz endpoints
 */
export const rateLimiters = {
  submitAnswer: createRateLimiter({
    maxRequests: 5,
    windowMs: 60 * 1000, // 1 minute
    message: 'Too many answer submissions. Please wait before submitting again.'
  }),

  csrfToken: createRateLimiter({
    maxRequests: 10,
    windowMs: 60 * 1000, // 1 minute
    message: 'Too many CSRF token requests. Please wait before requesting again.'
  }),

  initializeSession: createRateLimiter({
    maxRequests: 3,
    windowMs: 60 * 1000, // 1 minute
    message: 'Too many session initialization attempts. Please wait before trying again.'
  }),

  sessionStatus: createRateLimiter({
    maxRequests: 20,
    windowMs: 60 * 1000, // 1 minute
    message: 'Too many status check requests.'
  })
}
