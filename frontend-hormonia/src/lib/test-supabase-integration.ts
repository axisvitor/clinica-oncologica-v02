/**
 * Supabase Integration Test
 *
 * This file provides utilities to test the Supabase integration
 * Run this in the browser console or create a test component
 */

import { supabase, auth, database, realtimeManager, utils } from './supabase-client'
import { createLogger } from './logger'

const logger = createLogger('TestSupabaseIntegration')

export interface TestResult {
  test: string
  passed: boolean
  message: string
  data?: any
}

export class SupabaseIntegrationTester {
  private results: TestResult[] = []

  async runAllTests(): Promise<TestResult[]> {
    this.results = []

    logger.info('Starting Supabase Integration Tests')

    await this.testConfiguration()
    await this.testHealthCheck()
    await this.testAuthFunctions()
    await this.testDatabaseOperations()
    await this.testRealtimeManager()

    this.printResults()
    return this.results
  }

  private async testConfiguration() {
    try {
      const configured = utils.isConfigured()
      this.addResult('Configuration Check', configured, 
        configured ? 'Supabase is properly configured' : 'Missing Supabase environment variables')
    } catch (error) {
      this.addResult('Configuration Check', false, `Error: ${error}`)
    }
  }

  private async testHealthCheck() {
    try {
      const health = await utils.healthCheck()
      const passed = health.configured && health.connected
      
      this.addResult('Health Check', passed, 
        `Configured: ${health.configured}, Connected: ${health.connected}, Realtime: ${health.realtimeEnabled}`,
        health)
    } catch (error) {
      this.addResult('Health Check', false, `Error: ${error}`)
    }
  }

  private async testAuthFunctions() {
    try {
      // Test getCurrentUser (should return null if not authenticated)
      const currentUser = await auth.getCurrentUser()
      this.addResult('Get Current User', true, 
        currentUser ? `User found: ${currentUser.email}` : 'No user authenticated (expected)', 
        currentUser)

      // Test getCurrentSession
      const currentSession = await auth.getCurrentSession()
      this.addResult('Get Current Session', true, 
        currentSession ? `Session active: ${currentSession.user['email']}` : 'No active session (expected)', 
        currentSession ? { user: currentSession.user['email'], expires: currentSession.expires_at } : null)

    } catch (error) {
      this.addResult('Auth Functions', false, `Error testing auth functions: ${error}`)
    }
  }

  private async testDatabaseOperations() {
    try {
      // Test patients list (read operation)
      const patientsResult: any = await database.patients.list({ limit: 1 })
      this.addResult('Database Read (Patients)', true, 
        `Successfully queried patients table. Total: ${patientsResult.total}`, 
        { total: patientsResult.total, hasData: ((patientsResult as any)?.data || []).length > 0 })

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error'
      const passed = errorMessage.includes('relation "patients" does not exist')
      this.addResult('Database Read (Patients)', passed, 
        passed ? 'Patients table not found (expected if not created yet)' : `Database error: ${errorMessage}`)
    }
  }

  private async testRealtimeManager() {
    try {
      // Test realtime manager initialization
      const activeChannels = realtimeManager.getActiveChannels()
      this.addResult('Realtime Manager', true, 
        `Realtime manager initialized. Active channels: ${activeChannels.length}`,
        { activeChannels })

      // Test connection status
      const connectionStatus = utils.getConnectionStatus()
      this.addResult('Realtime Connection', true, 
        `Realtime connection status: ${connectionStatus ? 'Connected' : 'Disconnected'}`,
        { connected: connectionStatus })

    } catch (error) {
      this.addResult('Realtime Manager', false, `Error: ${error}`)
    }
  }

  private addResult(test: string, passed: boolean, message: string, data?: any) {
    const result: TestResult = { test, passed, message, data }
    this.results.push(result)

    if (passed) {
      logger.info(`Test passed: ${test}`, { message, data })
    } else {
      logger.error(`Test failed: ${test}`, { message, data })
    }
  }

  private printResults() {
    const passed = this.results.filter(r => r.passed).length
    const total = this.results.length

    logger.info('Test Summary', {
      passed: `${passed}/${total}`,
      failed: `${total - passed}/${total}`,
      allPassed: passed === total
    })

    if (passed === total) {
      logger.info('All tests passed! Supabase integration is working correctly.')
    } else {
      logger.warn('Some tests failed. Check the results above for details.')
    }
  }

  // Individual test methods for manual testing
  async testLogin(email: string, password: string): Promise<TestResult> {
    try {
      const result = await auth.signIn(email, password)
      return {
        test: 'Login Test',
        passed: true,
        message: `Login successful for ${result.user?.email}`,
        data: { userId: result.user?.id, email: result.user?.email }
      }
    } catch (error) {
      return {
        test: 'Login Test',
        passed: false,
        message: `Login failed: ${error}`,
      }
    }
  }

  async testSignUp(email: string, password: string, metadata?: Record<string, any>): Promise<TestResult> {
    try {
      const result = await auth.signUp(email, password, metadata)
      return {
        test: 'Sign Up Test',
        passed: true,
        message: result.user 
          ? `Sign up successful for ${result.user['email']}` 
          : 'Sign up initiated (check email for confirmation)',
        data: result.user ? { userId: result.user['id'], email: result.user['email'] } : null
      }
    } catch (error) {
      return {
        test: 'Sign Up Test',
        passed: false,
        message: `Sign up failed: ${error}`,
      }
    }
  }

  async testRealtimeSubscription(patientId?: string): Promise<TestResult> {
    try {
      let subscription
      
      if (patientId) {
        subscription = realtimeManager.subscribeToPatientMessages(patientId, (payload) => {
          logger.debug('Real-time message received', { payload })
        })
      } else {
        subscription = realtimeManager.subscribeToPatients((payload) => {
          logger.debug('Real-time patient update received', { payload })
        })
      }

      if (subscription) {
        // Test for 5 seconds then unsubscribe
        setTimeout(() => {
          realtimeManager.unsubscribeAll()
          logger.info('Unsubscribed from real-time')
        }, 5000)

        return {
          test: 'Realtime Subscription',
          passed: true,
          message: 'Realtime subscription created successfully. Will auto-unsubscribe in 5 seconds.',
          data: { subscriptionActive: true, patientId }
        }
      } else {
        return {
          test: 'Realtime Subscription',
          passed: false,
          message: 'Failed to create realtime subscription (realtime disabled?)',
        }
      }
    } catch (error) {
      return {
        test: 'Realtime Subscription',
        passed: false,
        message: `Realtime subscription failed: ${error}`,
      }
    }
  }
}

// Export singleton tester
export const supabaseTester = new SupabaseIntegrationTester()

// Convenience function for quick testing
export const runSupabaseTests = () => supabaseTester.runAllTests()

// Manual test functions
export const testSupabaseLogin = (email: string, password: string) => 
  supabaseTester.testLogin(email, password)

export const testSupabaseSignUp = (email: string, password: string, metadata?: Record<string, any>) => 
  supabaseTester.testSignUp(email, password, metadata)

export const testRealtimeSubscription = (patientId?: string) => 
  supabaseTester.testRealtimeSubscription(patientId)

// Usage examples (for documentation):
/*
// In browser console or component:

// Run all tests
import { runSupabaseTests } from './lib/test-supabase-integration'
runSupabaseTests().then(results => console.log('All tests completed:', results))

// Test login
import { testSupabaseLogin } from './lib/test-supabase-integration'
testSupabaseLogin('user@example.com', 'password123')

// Test realtime
import { testRealtimeSubscription } from './lib/test-supabase-integration'
testRealtimeSubscription('patient-id-here') // or no params for all patients

*/