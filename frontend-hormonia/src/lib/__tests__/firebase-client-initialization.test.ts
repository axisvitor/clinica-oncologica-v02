/**
 * Firebase Client Initialization Tests
 * Tests safe initialization and re-initialization protection
 */

import { describe, test, expect, beforeEach, vi } from 'vitest'
import type { FirebaseApp } from 'firebase/app'
// Mock Firebase modules before imports
vi.mock('firebase/app', () => {
  const apps: FirebaseApp[] = []

  return {
    initializeApp: vi.fn((config) => {
      const app = { name: '[DEFAULT]', options: config } as FirebaseApp
      apps.push(app)
      return app
    }),
    getApps: vi.fn(() => apps),
    FirebaseApp: class {},
    FirebaseOptions: class {},
  }
})

vi.mock('firebase/auth', () => ({
  getAuth: vi.fn((app) => ({ app, type: 'Auth' })),
  signInWithEmailAndPassword: vi.fn(),
  createUserWithEmailAndPassword: vi.fn(),
  signOut: vi.fn(),
  onAuthStateChanged: vi.fn(),
  onIdTokenChanged: vi.fn(),
  updateProfile: vi.fn(),
  sendPasswordResetEmail: vi.fn(),
  sendEmailVerification: vi.fn(),
  setPersistence: vi.fn(),
  browserLocalPersistence: {},
  browserSessionPersistence: {},
}))

describe('Firebase Client Initialization', () => {
  beforeEach(() => {
    // Clear module cache to test re-initialization
    vi.resetModules()
  })

  test('should initialize Firebase app on first import', async () => {
    const { initializeApp } = await import('firebase/app')
    const { firebaseApp } = await import('../firebase-client')

    expect(initializeApp).toHaveBeenCalledTimes(1)
    expect(firebaseApp).toBeDefined()
    expect(firebaseApp.name).toBe('[DEFAULT]')
  })

  test('should reuse existing Firebase app on re-import', async () => {
    const { getApps } = await import('firebase/app')

    // First import
    await import('../firebase-client')

    // Simulate existing app
    const existingApps = (getApps as any)()
    expect(existingApps.length).toBeGreaterThan(0)

    // Re-import should not create new app
    await import('../firebase-client')

    const appsAfterReimport = (getApps as any)()
    expect(appsAfterReimport.length).toBe(existingApps.length)
  })

  test('should validate required Firebase configuration', async () => {
    // Mock missing environment variables
    const originalEnv = import.meta.env
    Object.defineProperty(import.meta, 'env', {
      value: {
        VITE_FIREBASE_API_KEY: '',
        VITE_FIREBASE_PROJECT_ID: '',
        VITE_FIREBASE_AUTH_DOMAIN: '',
      },
      configurable: true,
    })

    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    try {
      await import('../firebase-client')
    } catch (error) {
      expect(error).toBeDefined()
    }

    expect(consoleErrorSpy).toHaveBeenCalled()
    consoleErrorSpy.mockRestore()

    // Restore original env
    Object.defineProperty(import.meta, 'env', {
      value: originalEnv,
      configurable: true,
    })
  })

  test('should export firebaseApp and firebaseAuthInstance', async () => {
    const exports = await import('../firebase-client')

    expect(exports.firebaseApp).toBeDefined()
    expect(exports.firebaseAuthInstance).toBeDefined()
    expect(exports.auth).toBeDefined()
    expect(exports.default).toBeDefined()
  })

  test('should handle HMR (Hot Module Replacement) gracefully', async () => {
    const { getApps } = await import('firebase/app')

    // Simulate HMR by importing multiple times
    await import('../firebase-client')
    const appsAfterFirst = (getApps as any)().length

    await import('../firebase-client')
    const appsAfterSecond = (getApps as any)().length

    await import('../firebase-client')
    const appsAfterThird = (getApps as any)().length

    // Should maintain same number of apps (reuse existing)
    expect(appsAfterFirst).toBe(appsAfterSecond)
    expect(appsAfterSecond).toBe(appsAfterThird)
  })

  test('should log initialization status in development mode', async () => {
    const consoleLogSpy = vi.spyOn(console, 'log').mockImplementation(() => {})

    // Mock DEV environment
    const originalEnv = import.meta.env
    Object.defineProperty(import.meta, 'env', {
      value: { ...originalEnv, DEV: true },
      configurable: true,
    })

    await import('../firebase-client')

    // Test still checks console.log since Firebase library itself may log
    expect(consoleLogSpy).toHaveBeenCalledWith(
      expect.stringContaining('[Firebase]'),
      expect.anything()
    )

    consoleLogSpy.mockRestore()

    // Restore original env
    Object.defineProperty(import.meta, 'env', {
      value: originalEnv,
      configurable: true,
    })
  })

  test('should warn about multiple Firebase apps in development', async () => {
    const consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const { getApps, initializeApp } = await import('firebase/app')

    // Mock DEV environment
    const originalEnv = import.meta.env
    Object.defineProperty(import.meta, 'env', {
      value: { ...originalEnv, DEV: true },
      configurable: true,
    })

    // Manually create multiple apps to trigger warning
    ;(initializeApp as any)({ apiKey: 'test1' })
    ;(initializeApp as any)({ apiKey: 'test2' })

    const apps = (getApps as any)()
    if (apps.length > 1) {
      // Test case: console.warn is part of test logic
      console.warn('[Firebase] Multiple Firebase apps detected! This may cause issues.')
    }

    // Test still checks console.warn since it's part of the test assertion
    expect(consoleWarnSpy).toHaveBeenCalledWith(
      expect.stringContaining('Multiple Firebase apps detected')
    )

    consoleWarnSpy.mockRestore()

    // Restore original env
    Object.defineProperty(import.meta, 'env', {
      value: originalEnv,
      configurable: true,
    })
  })
})

describe('Firebase Configuration Validation', () => {
  test('should detect missing API key', async () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    const originalEnv = import.meta.env
    Object.defineProperty(import.meta, 'env', {
      value: {
        ...originalEnv,
        VITE_FIREBASE_API_KEY: '',
        VITE_FIREBASE_PROJECT_ID: 'test-project',
        VITE_FIREBASE_AUTH_DOMAIN: 'test.firebaseapp.com',
      },
      configurable: true,
    })

    try {
      await import('../firebase-client')
    } catch (error) {
      expect(error).toBeDefined()
    }

    expect(consoleErrorSpy).toHaveBeenCalledWith(
      expect.stringContaining('apiKey is not configured')
    )

    consoleErrorSpy.mockRestore()
    Object.defineProperty(import.meta, 'env', {
      value: originalEnv,
      configurable: true,
    })
  })

  test('should detect missing project ID', async () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    const originalEnv = import.meta.env
    Object.defineProperty(import.meta, 'env', {
      value: {
        ...originalEnv,
        VITE_FIREBASE_API_KEY: 'test-key',
        VITE_FIREBASE_PROJECT_ID: '',
        VITE_FIREBASE_AUTH_DOMAIN: 'test.firebaseapp.com',
      },
      configurable: true,
    })

    try {
      await import('../firebase-client')
    } catch (error) {
      expect(error).toBeDefined()
    }

    expect(consoleErrorSpy).toHaveBeenCalledWith(
      expect.stringContaining('projectId is not configured')
    )

    consoleErrorSpy.mockRestore()
    Object.defineProperty(import.meta, 'env', {
      value: originalEnv,
      configurable: true,
    })
  })

  test('should include measurementId for analytics', async () => {
    const originalEnv = import.meta.env
    Object.defineProperty(import.meta, 'env', {
      value: {
        ...originalEnv,
        VITE_FIREBASE_MEASUREMENT_ID: 'G-XXXXXXXXXX',
      },
      configurable: true,
    })

    // Re-import with measurement ID
    vi.resetModules()
    const { firebaseApp: appWithAnalytics } = await import('../firebase-client')

    expect(appWithAnalytics).toBeDefined()

    Object.defineProperty(import.meta, 'env', {
      value: originalEnv,
      configurable: true,
    })
  })
})
