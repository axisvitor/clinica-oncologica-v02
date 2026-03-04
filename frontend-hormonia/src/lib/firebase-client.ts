/// <reference types="vite/client" />

/**
 * Firebase Authentication Client
 * Production-ready Firebase-only authentication implementation
 */

import { initializeApp, getApps, FirebaseApp, FirebaseOptions } from 'firebase/app'
import {
  getAuth,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signOut as firebaseSignOut,
  onAuthStateChanged as firebaseOnAuthStateChanged,
  onIdTokenChanged as firebaseOnIdTokenChanged,
  User as FirebaseUser,
  Auth,
  updateProfile,
  sendPasswordResetEmail,
  sendEmailVerification,
  setPersistence,
  browserLocalPersistence,
  browserSessionPersistence,
  UserCredential,
} from 'firebase/auth'
import { createLogger } from './logger'
import { getRuntimeConfigSync } from './runtime-config'

const logger = createLogger('FirebaseClient')

/**
 * Build Firebase configuration from runtime config with fallback to import.meta.env
 */
function buildFirebaseConfig(): FirebaseOptions {
  const runtimeConfig = getRuntimeConfigSync()

  logger.info('[Firebase Config] Environment check:', {
    hasRuntime: !!runtimeConfig,
    importMetaEnv: {
      VITE_FIREBASE_API_KEY: !!import.meta.env['VITE_FIREBASE_API_KEY'],
      VITE_FIREBASE_AUTH_DOMAIN: !!import.meta.env['VITE_FIREBASE_AUTH_DOMAIN'],
      VITE_FIREBASE_PROJECT_ID: !!import.meta.env['VITE_FIREBASE_PROJECT_ID'],
    },
  })

  const config: FirebaseOptions = {
    apiKey: runtimeConfig?.VITE_FIREBASE_API_KEY || import.meta.env['VITE_FIREBASE_API_KEY'] || '',
    authDomain:
      runtimeConfig?.VITE_FIREBASE_AUTH_DOMAIN ||
      import.meta.env['VITE_FIREBASE_AUTH_DOMAIN'] ||
      '',
    projectId:
      runtimeConfig?.VITE_FIREBASE_PROJECT_ID || import.meta.env['VITE_FIREBASE_PROJECT_ID'] || '',
    storageBucket:
      runtimeConfig?.VITE_FIREBASE_STORAGE_BUCKET ||
      import.meta.env['VITE_FIREBASE_STORAGE_BUCKET'] ||
      '',
    messagingSenderId:
      runtimeConfig?.VITE_FIREBASE_MESSAGING_SENDER_ID ||
      import.meta.env['VITE_FIREBASE_MESSAGING_SENDER_ID'] ||
      '',
    appId: runtimeConfig?.VITE_FIREBASE_APP_ID || import.meta.env['VITE_FIREBASE_APP_ID'] || '',
    measurementId:
      runtimeConfig?.VITE_FIREBASE_MEASUREMENT_ID ||
      import.meta.env['VITE_FIREBASE_MEASUREMENT_ID'],
  }

  logger.info('[Firebase Config] Building configuration:', {
    hasApiKey: !!config.apiKey,
    apiKeyPreview: config.apiKey ? config.apiKey.substring(0, 10) + '...' : 'MISSING',
    authDomain: config.authDomain || 'MISSING',
    projectId: config.projectId || 'MISSING',
    storageBucket: config.storageBucket || 'MISSING',
    hasAppId: !!config.appId,
    appIdPreview: config.appId ? config.appId.substring(0, 15) + '...' : 'MISSING',
    source: runtimeConfig ? 'runtime' : 'import.meta.env',
  })

  return config
}

const firebaseConfig: FirebaseOptions = buildFirebaseConfig()

/**
 * Validate Firebase configuration
 * Checks for required fields and throws error if missing
 */
function validateFirebaseConfig(config: FirebaseOptions): void {
  const requiredFields: (keyof FirebaseOptions)[] = ['apiKey', 'authDomain', 'projectId']
  const missingFields = requiredFields.filter((field) => !config[field])

  if (missingFields.length > 0) {
    const errorMsg = `Firebase configuration is incomplete. Missing required fields: ${missingFields.join(', ')}. Please check your environment variables (VITE_FIREBASE_*)`
    logger.error(errorMsg)
    throw new Error(errorMsg)
  }
}

/**
 * Check if Firebase is properly configured
 */
function isFirebaseConfigured(): boolean {
  return Boolean(firebaseConfig.apiKey && firebaseConfig.authDomain && firebaseConfig.projectId)
}

// Initialize Firebase App
let app: FirebaseApp | null = null
let auth: Auth | null = null

/**
 * Initialize Firebase application
 * @throws Error if Firebase is not configured
 */
export function initializeFirebase(): FirebaseApp {
  const existingApps = getApps()

  if (existingApps.length > 0) {
    logger.info('Using existing Firebase app instance')
    const existingApp = existingApps[0]! // Non-null assertion since length > 0
    app = existingApp
    auth = getAuth(existingApp)
    return existingApp
  }

  // Validate configuration before initialization
  if (!isFirebaseConfigured()) {
    const errorMsg =
      'Firebase is not configured. Please set the required environment variables: VITE_FIREBASE_API_KEY, VITE_FIREBASE_AUTH_DOMAIN, VITE_FIREBASE_PROJECT_ID'
    logger.error('[Firebase] Configuration missing:', errorMsg)
    throw new Error(errorMsg)
  }

  validateFirebaseConfig(firebaseConfig)

  logger.info('[Firebase] Initializing with project:', firebaseConfig.projectId)

  try {
    app = initializeApp(firebaseConfig)
    auth = getAuth(app)
    logger.info('[Firebase] Initialized successfully!', {
      projectId: firebaseConfig.projectId,
      authDomain: firebaseConfig.authDomain,
    })
    return app
  } catch (error) {
    logger.error('[Firebase] Initialization failed:', error)
    throw new Error(
      `Firebase initialization failed: ${error instanceof Error ? error.message : String(error)}`
    )
  }
}

/**
 * Extract Firebase error code from error object
 */
function getFirebaseErrorCode(error: unknown): string {
  if (error && typeof error === 'object' && 'code' in error) {
    return String(error.code)
  }
  return 'unknown'
}

/**
 * Map Firebase error codes to user-friendly messages
 */
function mapFirebaseErrorToMessage(errorCode: string): string {
  const errorMessages: Record<string, string> = {
    'auth/invalid-email': 'Email inválido.',
    'auth/user-disabled': 'Esta conta foi desabilitada.',
    'auth/user-not-found': 'Email ou senha incorretos.',
    'auth/wrong-password': 'Email ou senha incorretos.',
    'auth/invalid-credential': 'Email ou senha incorretos.',
    'auth/email-already-in-use': 'Este email já está em uso.',
    'auth/operation-not-allowed': 'Operação não permitida.',
    'auth/weak-password': 'A senha deve ter pelo menos 6 caracteres.',
    'auth/too-many-requests': 'Muitas tentativas. Tente novamente mais tarde.',
    'auth/network-request-failed': 'Erro de conexão. Verifique sua internet.',
    'auth/requires-recent-login': 'Esta operação requer login recente. Faça login novamente.',
  }

  return errorMessages[errorCode] || 'Erro ao processar sua solicitação. Tente novamente.'
}

// Initialize Firebase on module load
try {
  logger.info('[Firebase] Starting module initialization...')
  initializeFirebase()
  logger.info('[Firebase] Module initialization complete')
} catch (error) {
  logger.error('[Firebase] CRITICAL: Module initialization failed:', error)
  throw error
}

/**
 * Firebase Authentication API
 */
const firebaseAuth = {
  /**
   * Sign in with email and password
   */
  async signInWithPassword(credentials: { email: string; password: string }): Promise<{
    user: FirebaseUser | null
    session: { access_token: string } | null
    error: Error | null
  }> {
    if (!auth) {
      const errorMsg =
        'Firebase authentication is not initialized. Please check your Firebase configuration.'
      logger.error(errorMsg)
      return {
        user: null,
        session: null,
        error: new Error(errorMsg),
      }
    }

    try {
      logger.info('Attempting sign in with email:', credentials.email)

      const userCredential: UserCredential = await signInWithEmailAndPassword(
        auth,
        credentials.email,
        credentials.password
      )

      const token = await userCredential.user.getIdToken()
      logger.info('[Firebase Auth] Sign in successful!', {
        uid: userCredential.user.uid,
        email: userCredential.user.email,
        tokenLength: token.length,
      })

      return {
        user: userCredential.user,
        session: { access_token: token },
        error: null,
      }
    } catch (error: unknown) {
      const errorCode = getFirebaseErrorCode(error)
      const userMessage = mapFirebaseErrorToMessage(errorCode)

      logger.error('[Firebase Auth] Sign in failed:', {
        errorCode,
        message: userMessage,
        email: credentials.email,
      })

      return {
        user: null,
        session: null,
        error: new Error(userMessage),
      }
    }
  },

  /**
   * Sign up with email and password
   */
  async signUp(credentials: {
    email: string
    password: string
    options?: { data?: { full_name?: string; role?: string } }
  }): Promise<{
    user: FirebaseUser | null
    session: { access_token: string } | null
    error: Error | null
  }> {
    if (!auth) {
      const errorMsg =
        'Firebase authentication is not initialized. Please check your Firebase configuration.'
      logger.error(errorMsg)
      return {
        user: null,
        session: null,
        error: new Error(errorMsg),
      }
    }

    try {
      logger.info('Creating new user account for email:', credentials.email)
      const userCredential: UserCredential = await createUserWithEmailAndPassword(
        auth,
        credentials.email,
        credentials.password
      )

      // Update profile with display name if provided
      if (credentials.options?.data?.full_name) {
        await updateProfile(userCredential.user, {
          displayName: credentials.options.data.full_name,
        })
        logger.info('User profile updated with display name')
      }

      // Send email verification
      try {
        await sendEmailVerification(userCredential.user)
        logger.info('Email verification sent')
      } catch (verificationError) {
        logger.warn('Failed to send verification email:', verificationError)
        // Don't fail signup if email verification fails
      }

      const token = await userCredential.user.getIdToken()

      logger.info('User account created successfully:', userCredential.user.uid)
      return {
        user: userCredential.user,
        session: { access_token: token },
        error: null,
      }
    } catch (error: unknown) {
      const errorCode = getFirebaseErrorCode(error)
      const userMessage = mapFirebaseErrorToMessage(errorCode)

      logger.error('Sign up error:', errorCode, error)

      return {
        user: null,
        session: null,
        error: new Error(userMessage),
      }
    }
  },

  /**
   * Sign out current user
   */
  async signOut(): Promise<{ error: Error | null }> {
    if (!auth) {
      logger.warn('Firebase not initialized - no sign out needed')
      return { error: null }
    }

    try {
      const currentUser = auth.currentUser
      if (currentUser) {
        logger.info('Signing out user:', currentUser.uid)
      }
      await firebaseSignOut(auth)
      logger.info('Sign out successful')
      return { error: null }
    } catch (error: unknown) {
      const errorCode = getFirebaseErrorCode(error)
      const userMessage = mapFirebaseErrorToMessage(errorCode)

      logger.error('Sign out error:', errorCode, error)

      return { error: new Error(userMessage) }
    }
  },

  /**
   * Get current session with access token
   */
  async getCurrentSession(): Promise<{ access_token: string } | null> {
    if (!auth) {
      logger.warn('Firebase not initialized - cannot get session')
      return null
    }

    try {
      const user = auth.currentUser
      if (user) {
        const token = await user.getIdToken()
        return { access_token: token }
      }
      return null
    } catch (error: unknown) {
      const errorCode = getFirebaseErrorCode(error)
      logger.error('Get session error:', errorCode, error)
      return null
    }
  },

  /**
   * Get current authenticated user
   */
  async getCurrentUser(): Promise<FirebaseUser | null> {
    if (!auth) {
      logger.warn('Firebase not initialized - cannot get current user')
      return null
    }
    return auth.currentUser
  },

  /**
   * Refresh session token (force refresh)
   */
  async refreshSession(): Promise<{ access_token: string } | null> {
    if (!auth) {
      logger.warn('Firebase not initialized - cannot refresh session')
      return null
    }

    try {
      const user = auth.currentUser
      if (user) {
        logger.info('Refreshing session token for user:', user.uid)
        const token = await user.getIdToken(true) // Force refresh
        logger.info('Session token refreshed successfully')
        return { access_token: token }
      }
      return null
    } catch (error: unknown) {
      const errorCode = getFirebaseErrorCode(error)
      logger.error('Refresh session error:', errorCode, error)
      return null
    }
  },

  /**
   * Send password reset email
   */
  async resetPasswordForEmail(email: string): Promise<{ error: Error | null }> {
    if (!auth) {
      const errorMsg =
        'Firebase authentication is not initialized. Please check your Firebase configuration.'
      logger.error(errorMsg)
      return { error: new Error(errorMsg) }
    }

    try {
      logger.info('Sending password reset email to:', email)
      await sendPasswordResetEmail(auth, email)
      logger.info('Password reset email sent successfully')
      return { error: null }
    } catch (error: unknown) {
      const errorCode = getFirebaseErrorCode(error)
      const userMessage = mapFirebaseErrorToMessage(errorCode)

      logger.error('Password reset error:', errorCode, error)

      return { error: new Error(userMessage) }
    }
  },

  /**
   * Set authentication persistence (local or session)
   */
  async setPersistence(rememberMe: boolean): Promise<void> {
    if (!auth) {
      logger.warn('Firebase not initialized - cannot set persistence')
      return
    }

    try {
      const persistence = rememberMe ? browserLocalPersistence : browserSessionPersistence
      await setPersistence(auth, persistence)
      logger.info('Auth persistence set to:', rememberMe ? 'local' : 'session')
    } catch (error) {
      logger.error('Failed to set persistence:', error)
      throw error
    }
  },

  /**
   * Listen to authentication state changes
   */
  onAuthStateChanged(callback: (user: FirebaseUser | null) => void): () => void {
    if (!auth) {
      logger.warn('Firebase not initialized - auth state listener not active')
      return () => {}
    }
    return firebaseOnAuthStateChanged(auth, callback)
  },

  /**
   * Listen to authentication state changes (alias for backward compatibility)
   */
  onAuthStateChange(callback: (user: FirebaseUser | null) => void): () => void {
    return this.onAuthStateChanged(callback)
  },

  /**
   * Listen to ID token changes (for token refresh detection)
   */
  onIdTokenChanged(callback: (user: FirebaseUser | null) => void): () => void {
    if (!auth) {
      logger.warn('Firebase not initialized - ID token listener not active')
      return () => {}
    }
    return firebaseOnIdTokenChanged(auth, callback)
  },

  /**
   * Check if Firebase is properly configured and initialized
   */
  isConfigured(): boolean {
    return auth !== null && isFirebaseConfigured()
  },
}

// Export Firebase instances and auth object
export { app as firebaseApp, auth as firebaseAuthInstance, auth, firebaseAuth }
export default firebaseAuth
