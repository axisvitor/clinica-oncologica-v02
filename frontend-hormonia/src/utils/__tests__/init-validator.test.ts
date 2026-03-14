/**
 * Tests for Frontend Initialization Validator
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { FrontendInitValidator, validateFrontendInit } from '../init-validator'

// Mock dependencies
vi.mock('../../lib/runtime-config', () => ({
  getRuntimeConfig: vi.fn(() =>
    Promise.resolve({
      VITE_API_URL: 'http://localhost:8000/api/v2',
      VITE_API_BASE_URL: 'http://localhost:8000',
      VITE_ENVIRONMENT: 'test',
    })
  ),
}))

vi.mock('../../lib/api-client', () => ({
  apiClient: {
    getBaseURL: () => 'http://localhost:8000',
  },
}))

vi.mock('../../lib/logger', () => ({
  createLogger: () => ({
    info: vi.fn(),
    error: vi.fn(),
    warn: vi.fn(),
    debug: vi.fn(),
  }),
}))

describe('FrontendInitValidator', () => {
  let validator: FrontendInitValidator

  beforeEach(() => {
    validator = new FrontendInitValidator()
    // Reset fetch mock
    global.fetch = vi.fn()
  })

  describe('validateEnvironment', () => {
    it('should pass with all required variables', async () => {
      await validator['validateEnvironment']()

      const envResult = validator['results'].find((r) => r.component === 'Environment Variables')
      expect(envResult).toBeDefined()
      expect(envResult?.valid).toBe(true)
      expect(envResult?.message).toMatch(/session-first environment variables/i)
      expect(envResult?.details).toMatchObject({
        sessionAuth: 'backend cookies + verify-session',
      })
    })
  })

  describe('validateBrowser', () => {
    it('should detect browser features', async () => {
      // Mock browser features
      Object.defineProperty(window, 'fetch', { value: vi.fn(), writable: true })
      Object.defineProperty(window, 'localStorage', {
        value: {
          setItem: vi.fn(),
          getItem: vi.fn(),
          removeItem: vi.fn(),
        },
        writable: true,
      })

      await validator['validateBrowser']()

      const browserResult = validator['results'].find(
        (r) => r.component === 'Browser Compatibility'
      )
      expect(browserResult).toBeDefined()
      expect(browserResult?.details?.features).toBeDefined()
    })

    it('should detect missing features', async () => {
      // Remove a feature
      const originalFetch = global.fetch
      // @ts-ignore
      delete global.fetch

      await validator['validateBrowser']()

      const browserResult = validator['results'].find(
        (r) => r.component === 'Browser Compatibility'
      )
      expect(browserResult).toBeDefined()

      // Restore
      global.fetch = originalFetch
    })
  })

  describe('validateConfiguration', () => {
    it('should validate API URL format', async () => {
      await validator['validateConfiguration']()

      const configResult = validator['results'].find((r) => r.component === 'Configuration')
      expect(configResult).toBeDefined()
      expect(configResult?.valid).toBe(true)
      expect(configResult?.message).toMatch(/backend session auth/i)
      expect(configResult?.details).toMatchObject({
        sessionAuth: 'httpOnly cookies + verify-session',
      })
    })
  })

  describe('validateAPIConnectivity', () => {
    it('should pass when API is healthy', async () => {
      global.fetch = vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              status: 'healthy',
              version: '2.0.0',
            }),
        } as Response)
      )

      await validator['validateAPIConnectivity']()

      const apiResult = validator['results'].find((r) => r.component === 'API Connectivity')
      expect(apiResult).toBeDefined()
      expect(apiResult?.valid).toBe(true)
      expect(apiResult?.message).toMatch(/session verification/i)
      expect(apiResult?.details).toMatchObject({
        sessionAuth: expect.stringMatching(/verify-session\/login\/logout/i),
      })
    })

    it('should fail when API is unreachable', async () => {
      global.fetch = vi.fn(() => Promise.reject(new Error('Network error')))

      await validator['validateAPIConnectivity']()

      const apiResult = validator['results'].find((r) => r.component === 'API Connectivity')
      expect(apiResult).toBeDefined()
      expect(apiResult?.valid).toBe(false)
      expect(apiResult?.message).toMatch(/session restore/i)
    })

    it('should fail when API returns error status', async () => {
      global.fetch = vi.fn(() =>
        Promise.resolve({
          ok: false,
          status: 500,
          statusText: 'Internal Server Error',
        } as Response)
      )

      await validator['validateAPIConnectivity']()

      const apiResult = validator['results'].find((r) => r.component === 'API Connectivity')
      expect(apiResult).toBeDefined()
      expect(apiResult?.valid).toBe(false)
    })
  })

  describe('validateFeatures', () => {
    it('should validate required features', async () => {
      await validator['validateFeatures']()

      const featuresResult = validator['results'].find((r) => r.component === 'Features')
      expect(featuresResult).toBeDefined()
      expect(featuresResult?.valid).toBe(true)
      expect(featuresResult?.message).toMatch(/backend-owned session auth/i)
      expect(featuresResult?.details).toMatchObject({
        features: expect.objectContaining({ backendSessionAuth: true }),
      })
    })
  })

  describe('validate', () => {
    it('should run all validation checks', async () => {
      global.fetch = vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ status: 'healthy', version: '2.0.0' }),
        } as Response)
      )

      const results = await validator.validate()

      expect(results.overall).toBeDefined()
      expect(results.results.length).toBeGreaterThan(0)
      expect(results.timestamp).toBeDefined()
    })

    it('should set overall to false if any check fails', async () => {
      // Make API check fail
      global.fetch = vi.fn(() => Promise.reject(new Error('Network error')))

      const results = await validator.validate()

      expect(results.overall).toBe(false)
    })

    it('keeps validation output free of Firebase readiness wording', async () => {
      global.fetch = vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ status: 'healthy', version: '2.0.0' }),
        } as Response)
      )

      const results = await validator.validate()

      expect(JSON.stringify(results).toLowerCase()).not.toContain('firebase')
    })
  })

  describe('checkLocalStorage', () => {
    it('should return true when localStorage is available', () => {
      const result = validator['checkLocalStorage']()
      expect(result).toBe(true)
    })

    it('should return false when localStorage throws error', () => {
      const originalLocalStorage = window.localStorage

      Object.defineProperty(window, 'localStorage', {
        configurable: true,
        value: {
          setItem: () => {
            throw new Error('QuotaExceeded')
          },
          getItem: vi.fn(),
          removeItem: vi.fn(),
        },
      })

      const result = validator['checkLocalStorage']()
      expect(result).toBe(false)

      Object.defineProperty(window, 'localStorage', {
        configurable: true,
        value: originalLocalStorage,
      })
    })
  })
})

describe('validateFrontendInit', () => {
  it('should return validation results', async () => {
    global.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ status: 'healthy', version: '2.0.0' }),
      } as Response)
    )

    const results = await validateFrontendInit()

    expect(results).toBeDefined()
    expect(results.overall).toBeDefined()
    expect(results.results).toBeDefined()
    expect(Array.isArray(results.results)).toBe(true)
  })
})
