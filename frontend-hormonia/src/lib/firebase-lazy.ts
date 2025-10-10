/// <reference types="vite/client" />

/**
 * Lazy-loaded Firebase Authentication Module
 *
 * PERFORMANCE OPTIMIZATION:
 * Firebase SDK (107KB gzipped) is now loaded on-demand when authentication is needed
 * This reduces the initial bundle size and improves First Contentful Paint (FCP)
 *
 * Strategy:
 * - Firebase modules are imported dynamically using import()
 * - Authentication logic is wrapped in async functions
 * - Initial page load doesn't include Firebase SDK
 * - Firebase loads when user attempts to authenticate
 *
 * Bundle Impact:
 * - Before: 107KB Firebase in main bundle
 * - After: 107KB in separate chunk, loaded on login/auth check
 * - Estimated FCP improvement: 0.8-1.2s on 3G connection
 */

// Type-only imports (zero runtime cost)
import type { User as FirebaseUser, UserCredential } from 'firebase/auth'
import type { FirebaseApp, FirebaseOptions } from 'firebase/app'

// Singleton instance holders
let firebaseAppInstance: FirebaseApp | null = null
let firebaseAuthInstance: any = null

/**
 * Lazy load and initialize Firebase App
 */
async function getFirebaseApp(): Promise<FirebaseApp> {
  if (firebaseAppInstance) {
    return firebaseAppInstance
  }

  // Dynamic import - loads Firebase only when needed
  const { initializeApp, getApps } = await import('firebase/app')
  const { getRuntimeConfigSync } = await import('./runtime-config')
  const { createLogger } = await import('./logger')

  const logger = createLogger('FirebaseLazy')
  const existingApps = getApps()

  if (existingApps.length > 0) {
    logger.log('Using existing Firebase app instance')
    firebaseAppInstance = existingApps[0]!
    return firebaseAppInstance
  }

  // Build config from runtime or env vars
  const runtimeConfig = getRuntimeConfigSync()
  const config: FirebaseOptions = {
    apiKey: (runtimeConfig?.VITE_FIREBASE_API_KEY || import.meta.env['VITE_FIREBASE_API_KEY'] || ''),
    authDomain: (runtimeConfig?.VITE_FIREBASE_AUTH_DOMAIN || import.meta.env['VITE_FIREBASE_AUTH_DOMAIN'] || ''),
    projectId: (runtimeConfig?.VITE_FIREBASE_PROJECT_ID || import.meta.env['VITE_FIREBASE_PROJECT_ID'] || ''),
    storageBucket: (runtimeConfig?.VITE_FIREBASE_STORAGE_BUCKET || import.meta.env['VITE_FIREBASE_STORAGE_BUCKET'] || ''),
    messagingSenderId: (runtimeConfig?.VITE_FIREBASE_MESSAGING_SENDER_ID || import.meta.env['VITE_FIREBASE_MESSAGING_SENDER_ID'] || ''),
    appId: (runtimeConfig?.VITE_FIREBASE_APP_ID || import.meta.env['VITE_FIREBASE_APP_ID'] || ''),
    measurementId: (runtimeConfig?.VITE_FIREBASE_MEASUREMENT_ID || import.meta.env['VITE_FIREBASE_MEASUREMENT_ID'])
  }

  // Validate required fields
  if (!config.apiKey || !config.authDomain || !config.projectId) {
    const error = 'Firebase configuration is incomplete. Missing required fields.'
    logger.error(error)
    throw new Error(error)
  }

  logger.log('Initializing Firebase app lazily')
  firebaseAppInstance = initializeApp(config)
  return firebaseAppInstance
}

/**
 * Get Firebase Auth instance (lazy)
 */
async function getFirebaseAuth() {
  if (firebaseAuthInstance) {
    return firebaseAuthInstance
  }

  const { getAuth } = await import('firebase/auth')
  const app = await getFirebaseApp()
  firebaseAuthInstance = getAuth(app)
  return firebaseAuthInstance
}

/**
 * Lazy-loaded Firebase Authentication API
 */
export const firebaseAuthLazy = {
  /**
   * Sign in with email and password (lazy loaded)
   */
  async signInWithPassword(credentials: {
    email: string
    password: string
  }): Promise<{
    user: FirebaseUser | null
    session: { access_token: string } | null
    error: Error | null
  }> {
    try {
      const { signInWithEmailAndPassword } = await import('firebase/auth')
      const auth = await getFirebaseAuth()

      const userCredential: UserCredential = await signInWithEmailAndPassword(
        auth,
        credentials.email,
        credentials.password
      )

      const token = await userCredential.user.getIdToken()

      return {
        user: userCredential.user,
        session: { access_token: token },
        error: null
      }
    } catch (error: unknown) {
      return {
        user: null,
        session: null,
        error: error instanceof Error ? error : new Error('Authentication failed')
      }
    }
  },

  /**
   * Get current authenticated user (lazy loaded)
   */
  async getCurrentUser(): Promise<FirebaseUser | null> {
    try {
      const auth = await getFirebaseAuth()
      return auth.currentUser
    } catch (error) {
      console.error('Failed to get current user:', error)
      return null
    }
  },

  /**
   * Sign out current user (lazy loaded)
   */
  async signOut(): Promise<{ error: Error | null }> {
    try {
      const { signOut: firebaseSignOut } = await import('firebase/auth')
      const auth = await getFirebaseAuth()
      await firebaseSignOut(auth)
      return { error: null }
    } catch (error: unknown) {
      return {
        error: error instanceof Error ? error : new Error('Sign out failed')
      }
    }
  },

  /**
   * Listen to authentication state changes (lazy loaded)
   */
  async onAuthStateChanged(callback: (user: FirebaseUser | null) => void): Promise<() => void> {
    const { onAuthStateChanged } = await import('firebase/auth')
    const auth = await getFirebaseAuth()
    return onAuthStateChanged(auth, callback)
  },

  /**
   * Listen to ID token changes (lazy loaded)
   * Fired when token is refreshed or user signs in/out
   */
  async onIdTokenChanged(callback: (user: FirebaseUser | null) => void): Promise<() => void> {
    const { onIdTokenChanged } = await import('firebase/auth')
    const auth = await getFirebaseAuth()
    return onIdTokenChanged(auth, callback)
  },

  /**
   * Set authentication persistence (lazy loaded)
   */
  async setPersistence(rememberMe: boolean): Promise<void> {
    const {
      setPersistence,
      browserLocalPersistence,
      browserSessionPersistence
    } = await import('firebase/auth')
    const auth = await getFirebaseAuth()

    const persistence = rememberMe ? browserLocalPersistence : browserSessionPersistence
    await setPersistence(auth, persistence)
  },

  /**
   * Get current session with access token (lazy loaded)
   */
  async getCurrentSession(): Promise<{ access_token: string } | null> {
    try {
      const auth = await getFirebaseAuth()
      const user = auth.currentUser
      if (user) {
        const token = await user.getIdToken()
        return { access_token: token }
      }
      return null
    } catch (error) {
      console.error('Failed to get current session:', error)
      return null
    }
  },

  /**
   * Refresh session token (lazy loaded)
   */
  async refreshSession(): Promise<{ access_token: string } | null> {
    try {
      const auth = await getFirebaseAuth()
      const user = auth.currentUser
      if (user) {
        const token = await user.getIdToken(true) // Force refresh
        return { access_token: token }
      }
      return null
    } catch (error) {
      console.error('Failed to refresh session:', error)
      return null
    }
  },

  /**
   * Send password reset email (lazy loaded)
   */
  async resetPasswordForEmail(email: string): Promise<{ error: Error | null }> {
    try {
      const { sendPasswordResetEmail } = await import('firebase/auth')
      const auth = await getFirebaseAuth()
      await sendPasswordResetEmail(auth, email)
      return { error: null }
    } catch (error: unknown) {
      return {
        error: error instanceof Error ? error : new Error('Password reset failed')
      }
    }
  },

  /**
   * Check if Firebase is configured (sync check, no lazy load)
   */
  isConfigured(): boolean {
    return Boolean(
      import.meta.env['VITE_FIREBASE_API_KEY'] &&
      import.meta.env['VITE_FIREBASE_AUTH_DOMAIN'] &&
      import.meta.env['VITE_FIREBASE_PROJECT_ID']
    )
  }
}
