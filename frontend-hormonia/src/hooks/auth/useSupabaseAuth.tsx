import { useState, useEffect } from 'react'
import { User, Session } from '@supabase/supabase-js'
import { auth } from '@/lib/supabase-client'

export interface UseSupabaseAuthReturn {
  user: User | null
  session: Session | null
  loading: boolean
  isAuthenticated: boolean
  accessToken: string | null
  refreshToken: string | null
  authData: { user: User | null; session: Session | null }
  error: any
  signIn: (email: string, password: string) => Promise<void>
  signUp: (email: string, password: string) => Promise<void>
  signOut: () => Promise<void>
  resetPassword: (email: string) => Promise<void>
  refreshSession: () => Promise<{ session: Session | null; error: any }>
  updatePassword: (password: string) => Promise<void>
  convertToAppUser: (user: User) => any
}

export function useSupabaseAuth(): UseSupabaseAuthReturn {
  const [user, setUser] = useState<User | null>(null)
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<any>(null)

  useEffect(() => {
    // Get initial session
    auth.getCurrentSession().then(session => {
      setSession(session)
      setUser(session?.user || null)
      setLoading(false)
    }).catch(error => {
      console.error('Error getting initial session:', error)
      setError(error)
      setLoading(false)
    })

    // Listen for auth changes
    const { data: { subscription } } = auth.onAuthStateChange(
      (event, session) => {
        setSession(session)
        setUser(session?.user || null)
        setLoading(false)
      }
    )

    return () => subscription.unsubscribe()
  }, [])

  const signIn = async (email: string, password: string) => {
    setLoading(true)
    try {
      await auth.signIn(email, password)
    } finally {
      setLoading(false)
    }
  }

  const signUp = async (email: string, password: string) => {
    setLoading(true)
    try {
      await auth.signUp(email, password)
    } finally {
      setLoading(false)
    }
  }

  const signOut = async () => {
    setLoading(true)
    try {
      await auth.signOut()
    } finally {
      setLoading(false)
    }
  }

  const resetPassword = async (email: string) => {
    await auth.resetPassword(email)
  }

  const refreshSession = async () => {
    setLoading(true)
    try {
      const session = await auth.refreshSession()

      if (!session) {
        const error = new Error('Session refresh failed')
        console.error('Session refresh error:', error)
        setError(error.message)
        return { session: null, error }
      }

      setSession(session)
      setUser(session?.user || null)
      return { session, error: null }
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : 'Session refresh failed'
      console.error('Session refresh error:', error)
      setError(errorMsg)
      return { session: null, error: { message: errorMsg } }
    } finally {
      setLoading(false)
    }
  }

  const updatePassword = async (password: string) => {
    await auth.updatePassword(password)
  }

  const convertToAppUser = (user: User) => {
    return {
      id: user['id'],
      email: user['email'] || '',
      full_name: user.user_metadata?.['full_name'] || user['email'] || '',
      role: user.user_metadata?.['role'] || 'user',
      is_active: true,
      permissions: user.user_metadata?.['permissions'] || [],
      token: session?.access_token, // Include access token for WebSocket usage
      created_at: user.created_at
    }
  }

  return {
    user,
    session,
    loading,
    isAuthenticated: !!user && !!session,
    accessToken: session?.access_token || null,
    refreshToken: session?.refresh_token || null,
    authData: { user, session },
    error,
    signIn,
    signUp,
    signOut,
    resetPassword,
    refreshSession,
    updatePassword,
    convertToAppUser
  }
}
