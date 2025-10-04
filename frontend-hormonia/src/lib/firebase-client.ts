/**
 * Firebase Authentication Client
 * Replaces Supabase Auth with Firebase Auth
 */

import { initializeApp, getApps, FirebaseApp, FirebaseOptions } from 'firebase/app'
import {
  getAuth,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signOut as firebaseSignOut,
  onAuthStateChanged,
  onIdTokenChanged,
  User as FirebaseUser,
  Auth,
  updateProfile,
  sendPasswordResetEmail,
  sendEmailVerification,
  setPersistence,
  browserLocalPersistence,
  browserSessionPersistence,
  UserCredential
} from 'firebase/auth'

// Firebase configuration from environment variables
const firebaseConfig: FirebaseOptions = {
  apiKey: import.meta.env['VITE_FIREBASE_API_KEY'] || '',
  authDomain: import.meta.env['VITE_FIREBASE_AUTH_DOMAIN'] || '',
  projectId: import.meta.env['VITE_FIREBASE_PROJECT_ID'] || '',
  storageBucket: import.meta.env['VITE_FIREBASE_STORAGE_BUCKET'] || '',
  messagingSenderId: import.meta.env['VITE_FIREBASE_MESSAGING_SENDER_ID'] || '',
  appId: import.meta.env['VITE_FIREBASE_APP_ID'] || '',
  measurementId: import.meta.env['VITE_FIREBASE_MEASUREMENT_ID']
}

/**
 * Validate Firebase configuration
 * Checks for missing critical fields and logs warnings
 */
function validateFirebaseConfig(config: FirebaseOptions): void {
  const requiredFields = ['apiKey', 'projectId', 'authDomain'] as const
  const missingFields: string[] = []

  for (const field of requiredFields) {
    if (!config[field]) {
      missingFields.push(`VITE_FIREBASE_${field.toUpperCase().replace(/([A-Z])/g, '_$1')}`)
      console.error(`[Firebase] ${field} is not configured`)
    }
  }

  if (missingFields.length > 0) {
    console.error(
      `[Firebase] Missing required environment variables: ${missingFields.join(', ')}`
    )
  }
}

/**
 * Initialize Firebase app safely
 * Prevents "Firebase app already exists" errors by checking for existing instances
 * Handles HMR (Hot Module Replacement) and module re-imports gracefully
 *
 * @returns Firebase app instance (existing or newly created)
 * @throws Error if configuration is incomplete
 */
function initializeFirebaseApp(): FirebaseApp {
  // Check if any Firebase apps are already initialized
  const existingApps = getApps()

  if (existingApps.length > 0 && existingApps[0]) {
    console.log('[Firebase] Using existing Firebase app instance')
    return existingApps[0]
  }

  console.log('[Firebase] Initializing new Firebase app...')

  // Validate configuration before initialization
  validateFirebaseConfig(firebaseConfig)

  if (!firebaseConfig.apiKey || !firebaseConfig.projectId) {
    throw new Error(
      'Firebase configuration is incomplete. Check environment variables (VITE_FIREBASE_API_KEY, VITE_FIREBASE_PROJECT_ID).'
    )
  }

  try {
    const app = initializeApp(firebaseConfig)
    console.log('[Firebase] Firebase initialized successfully with project:', firebaseConfig.projectId)
    return app
  } catch (error: any) {
    console.error('[Firebase] Failed to initialize Firebase:', error)
    throw new Error(`Firebase initialization failed: ${error.message}`)
  }
}

// Initialize Firebase app safely
const app: FirebaseApp = initializeFirebaseApp()
const auth: Auth = getAuth(app)

// Development environment checks
if (import.meta.env.DEV) {
  // Verify single app instance
  const apps = getApps()
  console.log('[Firebase] Total apps initialized:', apps.length)

  if (apps.length > 1) {
    console.warn('[Firebase] Multiple Firebase apps detected! This may cause issues.')
  }
}

/**
 * Maps Firebase error codes to user-friendly Portuguese messages
 * Prevents information leakage about user existence
 */
function mapFirebaseErrorToMessage(errorCode: string): string {
  const errorMessages: Record<string, string> = {
    // Authentication errors - use same message for user-not-found and wrong-password
    'auth/user-not-found': 'Credenciais inválidas',
    'auth/wrong-password': 'Credenciais inválidas',
    'auth/invalid-email': 'Email inválido',
    'auth/user-disabled': 'Conta desativada. Entre em contato com o suporte.',
    'auth/invalid-credential': 'Credenciais inválidas',

    // Rate limiting
    'auth/too-many-requests': 'Muitas tentativas de login. Aguarde alguns minutos e tente novamente.',

    // Network errors
    'auth/network-request-failed': 'Erro de conexão. Verifique sua internet e tente novamente.',
    'auth/timeout': 'A solicitação expirou. Tente novamente.',

    // Token errors
    'auth/invalid-id-token': 'Sessão expirada. Faça login novamente.',
    'auth/id-token-expired': 'Sessão expirada. Faça login novamente.',
    'auth/id-token-revoked': 'Sessão revogada. Faça login novamente.',

    // Email verification
    'auth/email-already-in-use': 'Este email já está em uso',
    'auth/requires-recent-login': 'Por segurança, faça login novamente para continuar',

    // Password errors
    'auth/weak-password': 'Senha muito fraca. Use pelo menos 6 caracteres.',

    // Default
    'auth/internal-error': 'Erro interno. Tente novamente mais tarde.',
  }

  return errorMessages[errorCode] || 'Erro de autenticação. Tente novamente.'
}

/**
 * Extracts error code from Firebase error object
 */
function getFirebaseErrorCode(error: unknown): string {
  if (error && typeof error === 'object' && 'code' in error) {
    return String(error.code)
  }
  return 'unknown'
}

// Firebase Auth wrapper with Supabase-compatible API
export const firebaseAuth = {
  /**
   * Sign in with email and password
   */
  async signInWithPassword(credentials: { email: string; password: string }): Promise<{
    user: FirebaseUser | null
    session: { access_token: string } | null
    error: Error | null
  }> {
    try {
      console.log('[Firebase] Attempting sign in...')

      const userCredential: UserCredential = await signInWithEmailAndPassword(
        auth,
        credentials.email,
        credentials.password
      )

      const token = await userCredential.user.getIdToken()
      console.log('[Firebase] Sign in successful')

      return {
        user: userCredential.user,
        session: { access_token: token },
        error: null
      }
    } catch (error: unknown) {
      const errorCode = getFirebaseErrorCode(error)
      const userMessage = mapFirebaseErrorToMessage(errorCode)

      // Log actual error for debugging (but don't expose to user)
      console.error('[Firebase] Sign in error:', errorCode, error)

      return {
        user: null,
        session: null,
        error: new Error(userMessage)
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
    try {
      console.log('[Firebase] Creating user...')
      const userCredential: UserCredential = await createUserWithEmailAndPassword(
        auth,
        credentials.email,
        credentials.password
      )

      // Update profile with display name if provided
      if (credentials.options?.data?.full_name) {
        await updateProfile(userCredential.user, {
          displayName: credentials.options.data.full_name
        })
      }

      // Send email verification
      await sendEmailVerification(userCredential.user)

      const token = await userCredential.user.getIdToken()

      console.log('[Firebase] User created successfully')
      return {
        user: userCredential.user,
        session: { access_token: token },
        error: null
      }
    } catch (error: unknown) {
      const errorCode = getFirebaseErrorCode(error)
      const userMessage = mapFirebaseErrorToMessage(errorCode)

      // Log actual error for debugging (but don't expose to user)
      console.error('[Firebase] Sign up error:', errorCode, error)

      return {
        user: null,
        session: null,
        error: new Error(userMessage)
      }
    }
  },

  /**
   * Sign out
   */
  async signOut(): Promise<{ error: Error | null }> {
    try {
      console.log('[Firebase] Signing out user')
      await firebaseSignOut(auth)
      console.log('[Firebase] Sign out successful')
      return { error: null }
    } catch (error: unknown) {
      const errorCode = getFirebaseErrorCode(error)
      const userMessage = mapFirebaseErrorToMessage(errorCode)

      // Log actual error for debugging
      console.error('[Firebase] Sign out error:', errorCode, error)

      return { error: new Error(userMessage) }
    }
  },

  /**
   * Get current session
   */
  async getCurrentSession(): Promise<{ access_token: string } | null> {
    try {
      const user = auth.currentUser
      if (user) {
        const token = await user.getIdToken()
        return { access_token: token }
      }
      return null
    } catch (error: unknown) {
      const errorCode = getFirebaseErrorCode(error)
      console.error('[Firebase] Get session error:', errorCode, error)
      return null
    }
  },

  /**
   * Get current user
   */
  async getCurrentUser(): Promise<FirebaseUser | null> {
    return auth.currentUser
  },

  /**
   * Refresh session (get new token)
   */
  async refreshSession(): Promise<{ access_token: string } | null> {
    try {
      const user = auth.currentUser
      if (user) {
        const token = await user.getIdToken(true) // Force refresh
        return { access_token: token }
      }
      return null
    } catch (error: unknown) {
      const errorCode = getFirebaseErrorCode(error)
      console.error('[Firebase] Refresh session error:', errorCode, error)
      return null
    }
  },

  /**
   * Send password reset email
   */
  async resetPasswordForEmail(email: string): Promise<{ error: Error | null }> {
    try {
      console.log('[Firebase] Sending password reset email...')
      await sendPasswordResetEmail(auth, email)
      console.log('[Firebase] Password reset email sent')
      return { error: null }
    } catch (error: unknown) {
      const errorCode = getFirebaseErrorCode(error)
      const userMessage = mapFirebaseErrorToMessage(errorCode)

      // Log actual error for debugging
      console.error('[Firebase] Password reset error:', errorCode, error)

      return { error: new Error(userMessage) }
    }
  },

  /**
   * Set auth persistence
   */
  async setPersistence(rememberMe: boolean): Promise<void> {
    const persistence = rememberMe ? browserLocalPersistence : browserSessionPersistence
    await setPersistence(auth, persistence)
  },

  /**
   * Listen to auth state changes
   */
  onAuthStateChange(callback: (user: FirebaseUser | null) => void): () => void {
    return onAuthStateChanged(auth, callback)
  },

  /**
   * Listen to ID token changes (for token refresh)
   */
  onIdTokenChanged(callback: (user: FirebaseUser | null) => void): () => void {
    return onIdTokenChanged(auth, callback)
  }
}

// Export Firebase instances for advanced use cases
export { app as firebaseApp, auth as firebaseAuthInstance, auth }
export default firebaseAuth