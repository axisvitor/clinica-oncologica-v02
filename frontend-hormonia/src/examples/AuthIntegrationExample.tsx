/**
 * Authentication Integration Example
 *
 * This example demonstrates how to properly integrate all the authentication
 * and RLS error handling components in a React application.
 *
 * Features demonstrated:
 * - Environment variable validation
 * - Supabase client initialization with proper error handling
 * - RLS violation handling
 * - User feedback components
 * - Permission-based UI rendering
 * - API client wrapper usage
 */

import React, { useEffect, useState } from 'react'
import { supabase, initializeSupabaseFromConfig, getSupabaseStatus } from '../lib/supabase-client'
import { validateRuntimeConfig, validateAndLogConfig } from '../lib/env-validator'
import { getRuntimeConfig } from '../lib/runtime-config'
import {
  PermissionError,
  RLSViolationError,
  AuthRequiredError,
  NetworkError,
  PermissionGuard,
  useErrorHandler
} from '../components/ui/PermissionErrorFeedback'
import {
  useAuthContext,
  hasPermission,
  canAccessResource,
  getDisplayName
} from '../lib/auth-context-helpers'
import {
  createSupabaseWrapper,
  setupGlobalErrorHandling
} from '../lib/api-client-wrapper'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card'
import { Alert, AlertDescription } from '../components/ui/alert'
import { Badge } from '../components/ui/badge'

/**
 * Main component demonstrating authentication integration
 */
export function AuthIntegrationExample() {
  const [isInitialized, setIsInitialized] = useState(false)
  const [initError, setInitError] = useState<string | null>(null)
  const [configStatus, setConfigStatus] = useState<any>(null)
  const [patients, setPatients] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const { handleAuthError } = useErrorHandler()

  // Initialize the application
  useEffect(() => {
    initializeApplication()
  }, [])

  const initializeApplication = async () => {
    try {
      console.log('🚀 Starting application initialization...')

      // Step 1: Validate environment configuration
      console.log('📋 Validating environment configuration...')
      const config = await getRuntimeConfig()
      const validation = validateRuntimeConfig(config)

      setConfigStatus({
        isValid: validation.isValid,
        summary: validation.summary,
        errors: validation.errors,
        warnings: validation.warnings
      })

      if (!validation.isValid) {
        throw new Error('Environment configuration validation failed')
      }

      // Step 2: Initialize Supabase
      console.log('🗄️ Initializing Supabase client...')
      await initializeSupabaseFromConfig()

      // Step 3: Setup global error handling
      console.log('🛡️ Setting up global error handling...')
      setupGlobalErrorHandling({
        onAuthRequired: () => {
          console.log('🔐 Authentication required - redirecting to login')
          // Handle authentication required
          window.location.href = '/login'
        },
        onRLSViolation: (error) => {
          console.log('🚫 RLS violation detected:', error)
          setError(`Permission denied: ${error.message}`)
        },
        onNetworkError: (error) => {
          console.log('🌐 Network error detected:', error)
          setError(`Network error: ${error.message}`)
        }
      })

      setIsInitialized(true)
      console.log('✅ Application initialization complete')

    } catch (error) {
      console.error('❌ Application initialization failed:', error)
      setInitError(error instanceof Error ? error.message : 'Unknown error')
    }
  }

  // Example: Load patients with RLS error handling
  const loadPatients = async () => {
    setLoading(true)
    setError(null)

    try {
      // Create enhanced Supabase wrapper
      const enhancedSupabase = createSupabaseWrapper(supabase, {
        onAuthRequired: () => {
          setError('Authentication required to view patients')
        },
        onError: (error) => {
          setError(error.message)
        }
      })

      // Use the wrapper to query patients
      const data = await enhancedSupabase.executeQuery(
        supabase.from('patients').select('*').limit(10),
        'loading patient list'
      )

      // @ts-expect-error TODO: fix initial state
      setPatients(data || [])
    } catch (error) {
      const userFriendlyError = handleAuthError(error, 'loading patients')
      setError(userFriendlyError.message)
    } finally {
      setLoading(false)
    }
  }

  // Example: Try to create a patient (might trigger RLS violation)
  const createTestPatient = async () => {
    setLoading(true)
    setError(null)

    try {
      const enhancedSupabase = createSupabaseWrapper(supabase)

      const newPatient = {
        full_name: 'Test Patient',
        email: 'test@example.com',
        status: 'active'
      }

      await enhancedSupabase.executeQuery(
        supabase.from('patients').insert([newPatient]),
        'creating test patient'
      )

      console.log('✅ Patient created successfully')
      await loadPatients() // Reload the list
    } catch (error) {
      const userFriendlyError = handleAuthError(error, 'creating patient')
      setError(userFriendlyError.message)
    } finally {
      setLoading(false)
    }
  }

  // Render initialization error
  if (initError) {
    return (
      <div className="max-w-4xl mx-auto p-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-red-600">Initialization Failed</CardTitle>
          </CardHeader>
          <CardContent>
            <Alert variant="destructive">
              <AlertDescription>{initError}</AlertDescription>
            </Alert>
            <Button
              onClick={initializeApplication}
              className="mt-4"
              variant="outline"
            >
              Retry Initialization
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  // Render loading state
  if (!isInitialized) {
    return (
      <div className="max-w-4xl mx-auto p-6">
        <Card>
          <CardHeader>
            <CardTitle>Initializing Application...</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <div className="h-2 bg-gray-200 rounded animate-pulse"></div>
              <div className="h-2 bg-gray-200 rounded animate-pulse w-3/4"></div>
              <div className="h-2 bg-gray-200 rounded animate-pulse w-1/2"></div>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <h1 className="text-3xl font-bold">Authentication Integration Example</h1>

      {/* Configuration Status */}
      <Card>
        <CardHeader>
          <CardTitle>Configuration Status</CardTitle>
          <CardDescription>
            Environment variable validation results
          </CardDescription>
        </CardHeader>
        <CardContent>
          {configStatus && (
            <div className="space-y-4">
              <div className="flex items-center gap-2">
                <Badge variant={configStatus.isValid ? "default" : "destructive"}>
                  {configStatus.isValid ? "Valid" : "Invalid"}
                </Badge>
                <span className="text-sm text-gray-600">
                  {configStatus.summary.validated}/{configStatus.summary.total} variables configured
                </span>
              </div>

              {configStatus.errors.length > 0 && (
                <Alert variant="destructive">
                  <AlertDescription>
                    <strong>Errors:</strong>
                    <ul className="mt-2 list-disc list-inside">
                      {configStatus.errors.map((error: any, index: number) => (
                        <li key={index}>{error.field}: {error.message}</li>
                      ))}
                    </ul>
                  </AlertDescription>
                </Alert>
              )}

              {configStatus.warnings.length > 0 && (
                <Alert>
                  <AlertDescription>
                    <strong>Warnings:</strong>
                    <ul className="mt-2 list-disc list-inside">
                      {configStatus.warnings.map((warning: any, index: number) => (
                        <li key={index}>{warning.field}: {warning.message}</li>
                      ))}
                    </ul>
                  </AlertDescription>
                </Alert>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Supabase Status */}
      <Card>
        <CardHeader>
          <CardTitle>Supabase Status</CardTitle>
        </CardHeader>
        <CardContent>
          <SupabaseStatusDisplay />
        </CardContent>
      </Card>

      {/* Error Display */}
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Patient Management Example */}
      <Card>
        <CardHeader>
          <CardTitle>Patient Management Example</CardTitle>
          <CardDescription>
            Demonstrates RLS error handling with patient operations
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <Button
              onClick={loadPatients}
              disabled={loading}
              variant="outline"
            >
              {loading ? 'Loading...' : 'Load Patients'}
            </Button>

            <PermissionGuard
              hasPermission={true} // Replace with actual permission check
              fallbackType="alert"
            >
              <Button
                onClick={createTestPatient}
                disabled={loading}
              >
                Create Test Patient
              </Button>
            </PermissionGuard>
          </div>

          {patients.length > 0 && (
            <div className="space-y-2">
              <h4 className="font-medium">Patients ({patients.length})</h4>
              <div className="grid gap-2">
                {patients.map((patient) => (
                  <div key={patient.id} className="p-2 border rounded">
                    <div className="font-medium">{patient.full_name}</div>
                    <div className="text-sm text-gray-600">{patient.email}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Error Handling Examples */}
      <Card>
        <CardHeader>
          <CardTitle>Error Handling Examples</CardTitle>
          <CardDescription>
            Different types of error displays
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <h4 className="font-medium mb-2">RLS Violation Error</h4>
            <RLSViolationError
              resource="patients"
              action="delete"
              onContactSupport={() => alert('Contact support clicked')}
              onGoBack={() => alert('Go back clicked')}
            />
          </div>

          <div>
            <h4 className="font-medium mb-2">Authentication Required</h4>
            <AuthRequiredError
              onSignIn={() => alert('Sign in clicked')}
            />
          </div>

          <div>
            <h4 className="font-medium mb-2">Network Error</h4>
            <NetworkError
              onRetry={() => alert('Retry clicked')}
            />
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

/**
 * Component to display Supabase connection status
 */
function SupabaseStatusDisplay() {
  const [status, setStatus] = useState<any>(null)

  useEffect(() => {
    checkSupabaseStatus()
  }, [])

  const checkSupabaseStatus = async () => {
    try {
      const supabaseStatus = getSupabaseStatus()
      const healthCheck = await supabase.from('patients').select('count', { count: 'exact', head: true })

      setStatus({
        ...supabaseStatus,
        connected: !healthCheck.error,
        error: healthCheck.error?.message
      })
    } catch (error) {
      setStatus({
        initialized: false,
        connected: false,
        error: error instanceof Error ? error.message : 'Unknown error'
      })
    }
  }

  if (!status) {
    return <div>Checking status...</div>
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <Badge variant={status.initialized ? "default" : "destructive"}>
          {status.initialized ? "Initialized" : "Not Initialized"}
        </Badge>
        <Badge variant={status.connected ? "default" : "destructive"}>
          {status.connected ? "Connected" : "Disconnected"}
        </Badge>
        {status.realtimeEnabled && (
          <Badge variant="outline">Realtime Enabled</Badge>
        )}
      </div>

      {status.error && (
        <Alert variant="destructive">
          <AlertDescription>{status.error}</AlertDescription>
        </Alert>
      )}

      <Button
        onClick={checkSupabaseStatus}
        variant="outline"
        size="sm"
      >
        Refresh Status
      </Button>
    </div>
  )
}

export default AuthIntegrationExample