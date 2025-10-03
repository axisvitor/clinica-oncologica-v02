/**
 * Firebase Authentication Client
 * Replaces Supabase Auth with Firebase Auth
 */

import { initializeApp, FirebaseApp, FirebaseOptions } from 'firebase/app'
import {
  getAuth,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signOut as firebaseSignOut,
  onAuthStateChanged,
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
  appId: import.meta.env['VITE_FIREBASE_APP_ID'] || ''
}

// Initialize Firebase
console.log('[Firebase] Initializing Firebase app...')
const app: FirebaseApp = initializeApp(firebaseConfig)
const auth: Auth = getAuth(app)

console.log('[Firebase] Firebase initialized successfully')

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
      console.log('[Firebase] Signing in user:', credentials.email)
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
    } catch (error: any) {
      console.error('[Firebase] Sign in error:', error)
      return {
        user: null,
        session: null,
        error: new Error(error.message || 'Sign in failed')
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
      console.log('[Firebase] Creating user:', credentials.email)
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
    } catch (error: any) {
      console.error('[Firebase] Sign up error:', error)
      return {
        user: null,
        session: null,
        error: new Error(error.message || 'Sign up failed')
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
    } catch (error: any) {
      console.error('[Firebase] Sign out error:', error)
      return { error: new Error(error.message || 'Sign out failed') }
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
    } catch (error) {
      console.error('[Firebase] Get session error:', error)
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
    } catch (error) {
      console.error('[Firebase] Refresh session error:', error)
      return null
    }
  },

  /**
   * Send password reset email
   */
  async resetPasswordForEmail(email: string): Promise<{ error: Error | null }> {
    try {
      console.log('[Firebase] Sending password reset email to:', email)
      await sendPasswordResetEmail(auth, email)
      console.log('[Firebase] Password reset email sent')
      return { error: null }
    } catch (error: any) {
      console.error('[Firebase] Password reset error:', error)
      return { error: new Error(error.message || 'Password reset failed') }
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
  }
}

// Export auth instance for direct access if needed
export { auth }
export default firebaseAuth