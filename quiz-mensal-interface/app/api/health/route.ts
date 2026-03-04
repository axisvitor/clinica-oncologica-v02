import { NextResponse } from 'next/server'

export async function GET() {
  try {
    // Basic health check
    const healthCheck = {
      status: 'healthy',
      timestamp: new Date().toISOString(),
      uptime: process.uptime(),
      environment: process.env.NODE_ENV || 'development',
      version: process.env.APP_VERSION || '1.0.0',
      service: 'quiz-mensal-interface',
    }

    // Check API connection if configured
    let apiStatus = 'not-configured'
    if (process.env.NEXT_PUBLIC_API_URL) {
      try {
        const controller = new AbortController()
        const timeoutId = setTimeout(() => controller.abort(), 5000)

        const apiResponse = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/health/`, {
          method: 'GET',
          signal: controller.signal,
        })

        clearTimeout(timeoutId)
        apiStatus = apiResponse.ok ? 'healthy' : 'unhealthy'
      } catch (error) {
        apiStatus = 'unreachable'
      }
    }

    const response = {
      ...healthCheck,
      dependencies: {
        backend_api: {
          status: apiStatus,
          url: process.env.NEXT_PUBLIC_API_URL || 'not-configured',
        },
      },
    }

    return NextResponse.json(response, {
      status: 200,
      headers: {
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        Pragma: 'no-cache',
        Expires: '0',
      },
    })
  } catch (error) {
    const errorResponse = {
      status: 'unhealthy',
      timestamp: new Date().toISOString(),
      error: error instanceof Error ? error.message : 'Unknown error',
      service: 'quiz-mensal-interface',
    }

    return NextResponse.json(errorResponse, {
      status: 503,
      headers: {
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        Pragma: 'no-cache',
        Expires: '0',
      },
    })
  }
}

export async function HEAD() {
  return new Response(null, { status: 200 })
}
