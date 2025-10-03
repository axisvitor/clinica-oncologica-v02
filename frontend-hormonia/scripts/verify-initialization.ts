/**
 * Frontend Initialization Verification Script
 *
 * This script verifies all critical frontend initialization steps:
 * - Runtime configuration loading
 * - API client setup
 * - Supabase client initialization
 * - WebSocket connection capability
 * - Environment variables validation
 */

import { getRuntimeConfig, isProduction } from '../src/lib/runtime-config'
import { apiClient } from '../src/lib/api-client'
import { isSupabaseInitialized } from '../src/lib/supabase-client'

interface InitializationStatus {
  timestamp: string
  environment: string
  checks: {
    runtimeConfig: CheckResult
    apiClient: CheckResult
    supabaseClient: CheckResult
    environmentVars: CheckResult
    apiConnectivity: CheckResult
  }
  summary: {
    passed: number
    failed: number
    warnings: number
    totalChecks: number
  }
}

interface CheckResult {
  status: 'pass' | 'fail' | 'warning'
  message: string
  details?: any
}

async function verifyRuntimeConfig(): Promise<CheckResult> {
  try {
    const config = await getRuntimeConfig()

    const requiredFields = [
      'VITE_SUPABASE_URL',
      'VITE_SUPABASE_ANON_KEY',
      'VITE_API_URL',
      'VITE_API_BASE_URL',
      'VITE_WS_BASE_URL'
    ]

    const missingFields = requiredFields.filter(field => !config[field as keyof typeof config])

    if (missingFields.length > 0) {
      return {
        status: 'fail',
        message: `Runtime configuration missing required fields: ${missingFields.join(', ')}`,
        details: { config, missingFields }
      }
    }

    return {
      status: 'pass',
      message: 'Runtime configuration loaded successfully',
      details: {
        supabaseUrl: config.VITE_SUPABASE_URL,
        apiUrl: config.VITE_API_URL,
        wsUrl: config.VITE_WS_BASE_URL,
        environment: config.VITE_ENVIRONMENT || 'unknown'
      }
    }
  } catch (error) {
    return {
      status: 'fail',
      message: `Failed to load runtime configuration: ${error instanceof Error ? error.message : 'Unknown error'}`,
      details: { error }
    }
  }
}

async function verifyApiClient(): Promise<CheckResult> {
  try {
    const baseUrl = apiClient.getBaseURL()
    const isInit = apiClient.isInitialized()

    if (!baseUrl) {
      return {
        status: 'fail',
        message: 'API client has no base URL configured',
        details: { baseUrl, isInitialized: isInit }
      }
    }

    if (!isInit) {
      return {
        status: 'warning',
        message: 'API client is using fallback URL (not explicitly initialized)',
        details: { baseUrl, isInitialized: isInit }
      }
    }

    return {
      status: 'pass',
      message: 'API client configured successfully',
      details: { baseUrl, isInitialized: isInit }
    }
  } catch (error) {
    return {
      status: 'fail',
      message: `API client verification failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
      details: { error }
    }
  }
}

async function verifySupabaseClient(): Promise<CheckResult> {
  try {
    const isInit = isSupabaseInitialized()

    if (!isInit) {
      return {
        status: 'warning',
        message: 'Supabase client not explicitly initialized (will use lazy initialization)',
        details: { isInitialized: isInit }
      }
    }

    return {
      status: 'pass',
      message: 'Supabase client initialized successfully',
      details: { isInitialized: isInit }
    }
  } catch (error) {
    return {
      status: 'fail',
      message: `Supabase client verification failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
      details: { error }
    }
  }
}

async function verifyEnvironmentVars(): Promise<CheckResult> {
  try {
    const config = await getRuntimeConfig()

    const criticalVars = {
      VITE_SUPABASE_URL: config.VITE_SUPABASE_URL,
      VITE_SUPABASE_ANON_KEY: config.VITE_SUPABASE_ANON_KEY ? '***' : undefined,
      VITE_API_URL: config.VITE_API_URL,
      VITE_API_BASE_URL: config.VITE_API_BASE_URL,
      VITE_WS_BASE_URL: config.VITE_WS_BASE_URL,
      VITE_ENVIRONMENT: config.VITE_ENVIRONMENT
    }

    const missingCritical = Object.entries(criticalVars)
      .filter(([_, value]) => !value)
      .map(([key, _]) => key)

    if (missingCritical.length > 0) {
      return {
        status: 'fail',
        message: `Missing critical environment variables: ${missingCritical.join(', ')}`,
        details: criticalVars
      }
    }

    const optionalVars = {
      VITE_WHATSAPP_INSTANCE_NAME: config.VITE_WHATSAPP_INSTANCE_NAME,
      VITE_SENTRY_DSN: config.VITE_SENTRY_DSN,
      VITE_ANALYTICS_TRACKING_ID: config.VITE_ANALYTICS_TRACKING_ID
    }

    const missingOptional = Object.entries(optionalVars)
      .filter(([_, value]) => !value)
      .map(([key, _]) => key)

    if (missingOptional.length > 0) {
      return {
        status: 'warning',
        message: `Optional environment variables not set: ${missingOptional.join(', ')}`,
        details: { ...criticalVars, ...optionalVars }
      }
    }

    return {
      status: 'pass',
      message: 'All environment variables configured',
      details: { ...criticalVars, ...optionalVars }
    }
  } catch (error) {
    return {
      status: 'fail',
      message: `Environment variables verification failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
      details: { error }
    }
  }
}

async function verifyApiConnectivity(): Promise<CheckResult> {
  try {
    const config = await getRuntimeConfig()
    const apiUrl = config.VITE_API_URL || config.VITE_API_BASE_URL

    if (!apiUrl) {
      return {
        status: 'fail',
        message: 'No API URL configured',
        details: { apiUrl }
      }
    }

    // Try to reach the health endpoint
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 5000)

    try {
      const response = await fetch(`${apiUrl}/health`, {
        method: 'GET',
        signal: controller.signal
      })

      clearTimeout(timeoutId)

      if (response.ok) {
        const data = await response.json()
        return {
          status: 'pass',
          message: 'API connectivity verified',
          details: { apiUrl, healthStatus: data }
        }
      } else {
        return {
          status: 'warning',
          message: `API responded with status ${response.status}`,
          details: { apiUrl, status: response.status, statusText: response.statusText }
        }
      }
    } catch (fetchError) {
      clearTimeout(timeoutId)

      if (fetchError instanceof DOMException && fetchError.name === 'AbortError') {
        return {
          status: 'fail',
          message: 'API health check timed out (5s)',
          details: { apiUrl, error: 'Timeout' }
        }
      }

      return {
        status: 'fail',
        message: `API connectivity check failed: ${fetchError instanceof Error ? fetchError.message : 'Unknown error'}`,
        details: { apiUrl, error: fetchError }
      }
    }
  } catch (error) {
    return {
      status: 'fail',
      message: `API connectivity verification failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
      details: { error }
    }
  }
}

async function runVerification(): Promise<InitializationStatus> {
  console.log('🔍 Starting Frontend Initialization Verification...\n')

  const checks = {
    runtimeConfig: await verifyRuntimeConfig(),
    apiClient: await verifyApiClient(),
    supabaseClient: await verifySupabaseClient(),
    environmentVars: await verifyEnvironmentVars(),
    apiConnectivity: await verifyApiConnectivity()
  }

  const summary = {
    passed: Object.values(checks).filter(c => c.status === 'pass').length,
    failed: Object.values(checks).filter(c => c.status === 'fail').length,
    warnings: Object.values(checks).filter(c => c.status === 'warning').length,
    totalChecks: Object.keys(checks).length
  }

  const status: InitializationStatus = {
    timestamp: new Date().toISOString(),
    environment: isProduction() ? 'production' : 'development',
    checks,
    summary
  }

  return status
}

function displayResults(status: InitializationStatus) {
  console.log('\n📊 INITIALIZATION VERIFICATION RESULTS')
  console.log('=' .repeat(80))
  console.log(`Timestamp: ${status.timestamp}`)
  console.log(`Environment: ${status.environment}`)
  console.log('=' .repeat(80))

  Object.entries(status.checks).forEach(([name, result]) => {
    const icon = result.status === 'pass' ? '✅' : result.status === 'warning' ? '⚠️' : '❌'
    console.log(`\n${icon} ${name.toUpperCase()}`)
    console.log(`   Status: ${result.status.toUpperCase()}`)
    console.log(`   Message: ${result.message}`)
    if (result.details) {
      console.log(`   Details:`, JSON.stringify(result.details, null, 2).split('\n').map(l => `   ${l}`).join('\n'))
    }
  })

  console.log('\n' + '=' .repeat(80))
  console.log('SUMMARY:')
  console.log(`  ✅ Passed: ${status.summary.passed}/${status.summary.totalChecks}`)
  console.log(`  ❌ Failed: ${status.summary.failed}/${status.summary.totalChecks}`)
  console.log(`  ⚠️  Warnings: ${status.summary.warnings}/${status.summary.totalChecks}`)
  console.log('=' .repeat(80))

  const overallStatus = status.summary.failed === 0 ?
    (status.summary.warnings === 0 ? '✅ ALL CHECKS PASSED' : '⚠️  PASSED WITH WARNINGS') :
    '❌ VERIFICATION FAILED'

  console.log(`\n${overallStatus}\n`)
}

// Run verification if executed directly
if (import.meta.url === `file://${process.argv[1]}`) {
  runVerification()
    .then(status => {
      displayResults(status)

      // Write results to file
      const fs = require('fs')
      const path = require('path')
      const outputPath = path.join(__dirname, '..', 'init-status.json')
      fs.writeFileSync(outputPath, JSON.stringify(status, null, 2))
      console.log(`\n📝 Results saved to: ${outputPath}`)

      // Exit with appropriate code
      process.exit(status.summary.failed > 0 ? 1 : 0)
    })
    .catch(error => {
      console.error('❌ Verification script failed:', error)
      process.exit(1)
    })
}

export { runVerification, type InitializationStatus, type CheckResult }