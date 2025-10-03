import { createClient, SupabaseClient, User, Session, AuthError } from '@supabase/supabase-js'
import { RealtimeChannel, RealtimePostgresChangesPayload } from '@supabase/supabase-js'
import { errorHandler, isRLSError, createUserFriendlyError, getPermissionContext } from './auth-error-handler'
import { validateRuntimeConfig, validateAndLogConfig } from './env-validator'
import { getRuntimeConfig, RuntimeConfig } from './runtime-config'

// Deferred initialization state
let supabaseInstance: SupabaseClient | null = null
let realtimeEnabledFlag = import.meta.env['VITE_SUPABASE_REALTIME_ENABLED'] === 'true'
let isInitialized = false

/**
 * Initialize Supabase client with runtime configuration
 * @param url - Supabase project URL
 * @param anonKey - Supabase anonymous key
 * @param realtimeEnabled - Enable real-time features (optional)
 */
export function initializeSupabase(url: string, anonKey: string, realtimeEnabled?: boolean) {
  if (!url || !anonKey) {
    const error = new Error(
      'Supabase configuration missing: VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY are required. ' +
      'Please check your environment variables or .env file.'
    )
    console.error('[Supabase] Missing credentials for initialization:', error.message)
    throw error
  }

  // Validate configuration
  const config: Partial<RuntimeConfig> = {
    VITE_SUPABASE_URL: url,
    VITE_SUPABASE_ANON_KEY: anonKey
  }

  const isValidConfig = validateAndLogConfig(config)
  if (!isValidConfig) {
    throw new Error('Supabase configuration validation failed. Check console for details.')
  }

  console.log('[Supabase] Initializing client with URL:', url)

  if (realtimeEnabled !== undefined) {
    realtimeEnabledFlag = realtimeEnabled
  }

  try {
    supabaseInstance = createClient(url, anonKey, {
      auth: {
        autoRefreshToken: true,
        persistSession: true,
        detectSessionInUrl: true,
        flowType: 'pkce',
        // Add custom headers for better error tracking
      },
      realtime: {
        params: {
          eventsPerSecond: 10
        }
      },
      global: {
        headers: {
          'X-Client-Info': 'clinica-oncologica-frontend'
        }
      }
    })

    isInitialized = true
    console.log('[Supabase] Client initialized successfully')
    return supabaseInstance
  } catch (error) {
    console.error('[Supabase] Failed to initialize client:', error)
    throw new Error(`Failed to initialize Supabase client: ${error instanceof Error ? error.message : 'Unknown error'}`)
  }
}

/**
 * Get Supabase client instance (lazy initialization fallback)
 */
function getSupabaseClient(): SupabaseClient {
  if (!supabaseInstance) {
    // Try to get configuration from runtime config
    const config = getRuntimeConfig()
    const url = import.meta.env['VITE_SUPABASE_URL']
    const anonKey = import.meta.env['VITE_SUPABASE_ANON_KEY']

    if (!url || !anonKey) {
      const error = new Error(
        'Supabase not initialized and configuration is missing. ' +
        'Please ensure VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY are set in your environment variables.'
      )
      console.error('[Supabase] Configuration error:', error.message)
      throw error
    }

    console.warn('[Supabase] Using lazy initialization from configuration')
    return initializeSupabase(url, anonKey)
  }

  return supabaseInstance
}

/**
 * Check if Supabase is initialized
 */
export function isSupabaseInitialized(): boolean {
  return isInitialized
}

/**
 * Initialize Supabase with runtime configuration
 */
export async function initializeSupabaseFromConfig(): Promise<SupabaseClient> {
  try {
    const config = await getRuntimeConfig()

    if (!config.VITE_SUPABASE_URL || !config.VITE_SUPABASE_ANON_KEY) {
      throw new Error('Supabase configuration missing in runtime config')
    }

    return initializeSupabase(
      config.VITE_SUPABASE_URL,
      config.VITE_SUPABASE_ANON_KEY,
      config.VITE_SUPABASE_REALTIME_ENABLED === 'true'
    )
  } catch (error) {
    console.error('[Supabase] Failed to initialize from config:', error)
    throw error
  }
}

/**
 * Get Supabase configuration status
 */
export function getSupabaseStatus() {
  return {
    initialized: isInitialized,
    hasInstance: !!supabaseInstance,
    realtimeEnabled: realtimeEnabledFlag
  }
}

// Database types
export interface Patient {
  id: string
  full_name: string
  email: string
  phone_number?: string
  whatsapp_number?: string
  birth_date?: string
  gender?: string
  treatment_type?: string
  treatment_stage?: string
  diagnosis_date?: string
  status: 'active' | 'inactive' | 'completed'
  created_at: string
  updated_at: string
}

export interface Message {
  id: string
  patient_id: string
  content: string
  message_type: 'text' | 'image' | 'audio' | 'document'
  direction: 'inbound' | 'outbound'
  status: 'sent' | 'delivered' | 'read' | 'failed'
  scheduled_for?: string
  sent_at?: string
  metadata?: Record<string, any>
  created_at: string
}

export interface QuizSession {
  id: string
  patient_id: string
  template_id: string
  status: 'active' | 'completed' | 'expired'
  responses: Record<string, any>
  score?: number
  completed_at?: string
  created_at: string
}

// Export lazy Supabase client getter
export const supabase: SupabaseClient = new Proxy({} as SupabaseClient, {
  get(target, prop) {
    const client = getSupabaseClient()
    const value = (client as any)[prop]
    return typeof value === 'function' ? value.bind(client) : value
  }
})

// Authentication interface
export interface AuthUser {
  id: string
  email: string
  full_name?: string
  role?: string
  is_active: boolean
  permissions?: string[]
  created_at: string
}

// Authentication functions
export const auth = {
  // Sign in with email and password
  signIn: async (email: string, password: string) => {
    const client = getSupabaseClient()

    try {
      const { data, error } = await client.auth.signInWithPassword({
        email,
        password
      })

      if (error) {
        const userFriendlyError = createUserFriendlyError(error, 'signing in')
        throw new Error(userFriendlyError.message)
      }

      return {
        user: data.user,
        session: data.session,
        access_token: data.session?.access_token || '',
        refresh_token: data.session?.refresh_token || ''
      }
    } catch (error) {
      // Let user-friendly errors pass through
      if (error instanceof Error && error.message.includes('sign in')) {
        throw error
      }

      // Handle other errors
      const userFriendlyError = createUserFriendlyError(error, 'signing in')
      throw new Error(userFriendlyError.message)
    }
  },

  // Sign up new user
  signUp: async (email: string, password: string, metadata?: Record<string, any>) => {
    const client = getSupabaseClient()
    const { data, error } = await client.auth.signUp({
      email,
      password,
      options: {
        data: metadata || {}
      }
    })
    
    if (error) {
      throw new Error(`Sign up failed: ${error.message}`)
    }
    
    return data
  },

  // Sign out
  signOut: async () => {
    const client = getSupabaseClient()
    const { error } = await client.auth.signOut()
    if (error) {
      throw new Error(`Sign out failed: ${error.message}`)
    }
  },

  // Get current user
  getCurrentUser: async (): Promise<User | null> => {
    const client = getSupabaseClient()
    const { data: { user }, error } = await client.auth.getUser()
    if (error) {
      console.error('Error getting current user:', error.message)
      return null
    }
    return user
  },

  // Get current session
  getCurrentSession: async (): Promise<Session | null> => {
    const client = getSupabaseClient()
    const { data: { session }, error } = await client.auth.getSession()
    if (error) {
      console.error('Error getting session:', error.message)
      return null
    }
    return session
  },

  // Refresh session
  refreshSession: async (): Promise<Session | null> => {
    const client = getSupabaseClient()
    const { data: { session }, error } = await client.auth.refreshSession()
    if (error) {
      throw new Error(`Session refresh failed: ${error.message}`)
    }
    return session
  },

  // Reset password
  resetPassword: async (email: string) => {
    const client = getSupabaseClient()
    const { error } = await client.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/reset-password`
    })
    
    if (error) {
      throw new Error(`Password reset failed: ${error.message}`)
    }
  },

  // Update password
  updatePassword: async (password: string) => {
    const client = getSupabaseClient()
    const { error } = await client.auth.updateUser({
      password
    })
    
    if (error) {
      throw new Error(`Password update failed: ${error.message}`)
    }
  },

  // Listen to auth changes
  onAuthStateChange: (callback: (event: string, session: Session | null) => void) => {
    const client = getSupabaseClient()
    return client.auth.onAuthStateChange(callback)
  }
}

// Database operations
export const database = {
  // Patients
  patients: {
    // Get all patients with optional filtering
    list: async (filters?: {
      status?: string
      treatment_type?: string
      search?: string
      page?: number
      limit?: number
    }) => {
      return await errorHandler.withErrorHandling(async () => {
        const client = getSupabaseClient()
        let query = client
          .from('patients')
          .select('*', { count: 'exact' })
          .order('created_at', { ascending: false })

        if (filters?.status) {
          query = query.eq('status', filters.status)
        }

        if (filters?.treatment_type) {
          query = query.eq('treatment_type', filters.treatment_type)
        }

        if (filters?.search) {
          query = query.or(`full_name.ilike.%${filters.search}%,email.ilike.%${filters.search}%,phone_number.ilike.%${filters.search}%`)
        }

        if (filters?.page && filters?.limit) {
          const from = (filters.page - 1) * filters.limit
          const to = from + filters.limit - 1
          query = query.range(from, to)
        }

        const result = await query

        return {
          data: result.data || [],
          error: null,
          total: result.count || 0,
          page: filters?.page || 1,
          limit: filters?.limit || 50
        }
      }, getPermissionContext('patients', 'select'))
    },

    // Get patient by ID
    get: async (id: string): Promise<Patient | null> => {
      try {
        return await errorHandler.withErrorHandling(async () => {
          const client = getSupabaseClient()
          const { data, error } = await client
            .from('patients')
            .select('*')
            .eq('id', id)
            .single()

          if (error) {
            if (error.code === 'PGRST116') {
              return null // Patient not found
            }
            throw error
          }

          return data
        }, getPermissionContext('patients', 'select'))
      } catch (error) {
        // Handle not found as null return instead of error
        if (error instanceof Error && error.message.includes('not found')) {
          return null
        }
        throw error
      }
    },

    // Create new patient
    create: async (patient: Omit<Patient, 'id' | 'created_at' | 'updated_at'>): Promise<Patient> => {
      return await errorHandler.withErrorHandling(async () => {
        const client = getSupabaseClient()
        const { data, error } = await client
          .from('patients')
          .insert([patient])
          .select()
          .single()

        if (error) {
          throw error
        }

        return data
      }, getPermissionContext('patients', 'insert'))
    },

    // Update patient
    update: async (id: string, updates: Partial<Omit<Patient, 'id' | 'created_at'>>) => {
      return await errorHandler.withErrorHandling(async () => {
        const client = getSupabaseClient()
        const { data, error } = await client
          .from('patients')
          .update({
            ...updates,
            updated_at: new Date().toISOString()
          })
          .eq('id', id)
          .select()
          .single()

        if (error) {
          throw error
        }

        return data
      }, getPermissionContext('patients', 'update'))
    },

    // Delete patient
    delete: async (id: string) => {
      return await errorHandler.withErrorHandling(async () => {
        const client = getSupabaseClient()
        const { error } = await client
          .from('patients')
          .delete()
          .eq('id', id)

        if (error) {
          throw error
        }

        return { data: true, error: null }
      }, getPermissionContext('patients', 'delete'))
    }
  },

  // Messages
  messages: {
    // Get messages for a patient
    list: async (patientId: string, limit = 50) => {
      const client = getSupabaseClient()
      const { data, error } = await client
        .from('messages')
        .select('*')
        .eq('patient_id', patientId)
        .order('created_at', { ascending: false })
        .limit(limit)

      if (error) {
        throw new Error(`Failed to fetch messages: ${error.message}`)
      }

      return data || []
    },

    // Create new message
    create: async (message: Omit<Message, 'id' | 'created_at'>): Promise<Message> => {
      const client = getSupabaseClient()
      const { data, error } = await client
        .from('messages')
        .insert([message])
        .select()
        .single()

      if (error) {
        throw new Error(`Failed to create message: ${error.message}`)
      }

      return data
    },

    // Update message status
    updateStatus: async (id: string, status: Message['status']) => {
      const client = getSupabaseClient()
      const { data, error } = await client
        .from('messages')
        .update({ status })
        .eq('id', id)
        .select()
        .single()

      if (error) {
        throw new Error(`Failed to update message status: ${error.message}`)
      }

      return data
    }
  },

  // Quiz sessions
  quizSessions: {
    // Get sessions for a patient
    list: async (patientId: string) => {
      const client = getSupabaseClient()
      const { data, error } = await client
        .from('quiz_sessions')
        .select('*')
        .eq('patient_id', patientId)
        .order('created_at', { ascending: false })

      if (error) {
        throw new Error(`Failed to fetch quiz sessions: ${error.message}`)
      }

      return data || []
    },

    // Get session by ID
    get: async (id: string): Promise<QuizSession | null> => {
      const client = getSupabaseClient()
      const { data, error } = await client
        .from('quiz_sessions')
        .select('*')
        .eq('id', id)
        .single()

      if (error) {
        if (error.code === 'PGRST116') {
          return null
        }
        throw new Error(`Failed to fetch quiz session: ${error.message}`)
      }

      return data
    },

    // Create new session
    create: async (session: Omit<QuizSession, 'id' | 'created_at'>): Promise<QuizSession> => {
      const client = getSupabaseClient()
      const { data, error } = await client
        .from('quiz_sessions')
        .insert([session])
        .select()
        .single()

      if (error) {
        throw new Error(`Failed to create quiz session: ${error.message}`)
      }

      return data
    },

    // Update session
    update: async (id: string, updates: Partial<Omit<QuizSession, 'id' | 'created_at'>>) => {
      const client = getSupabaseClient()
      const { data, error } = await client
        .from('quiz_sessions')
        .update(updates)
        .eq('id', id)
        .select()
        .single()

      if (error) {
        throw new Error(`Failed to update quiz session: ${error.message}`)
      }

      return data
    }
  }
}

// Real-time subscriptions
export class RealtimeManager {
  private channels: Map<string, RealtimeChannel> = new Map()
  private get isEnabled(): boolean {
    return realtimeEnabledFlag
  }

  constructor() {
    if (!this.isEnabled) {
      console.warn('Supabase real-time is disabled. Set VITE_SUPABASE_REALTIME_ENABLED=true to enable.')
    }
  }

  // Subscribe to patient changes
  subscribeToPatients(callback: (payload: RealtimePostgresChangesPayload<Patient>) => void) {
    if (!this.isEnabled) return null

    const client = getSupabaseClient()
    const channel = client
      .channel('patients-channel')
      .on(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table: 'patients'
        },
        callback
      )
      .subscribe()

    this.channels.set('patients', channel)
    return channel
  }

  // Subscribe to messages for a specific patient
  subscribeToPatientMessages(
    patientId: string,
    callback: (payload: RealtimePostgresChangesPayload<Message>) => void
  ) {
    if (!this.isEnabled) return null

    const channelName = `messages-${patientId}`
    const client = getSupabaseClient()
    const channel = client
      .channel(channelName)
      .on(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table: 'messages',
          filter: `patient_id=eq.${patientId}`
        },
        callback
      )
      .subscribe()

    this.channels.set(channelName, channel)
    return channel
  }

  // Subscribe to all messages (for admin dashboard)
  subscribeToAllMessages(callback: (payload: RealtimePostgresChangesPayload<Message>) => void) {
    if (!this.isEnabled) return null

    const client = getSupabaseClient()
    const channel = client
      .channel('all-messages-channel')
      .on(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table: 'messages'
        },
        callback
      )
      .subscribe()

    this.channels.set('all-messages', channel)
    return channel
  }

  // Subscribe to quiz sessions
  subscribeToQuizSessions(
    patientId: string,
    callback: (payload: RealtimePostgresChangesPayload<QuizSession>) => void
  ) {
    if (!this.isEnabled) return null

    const channelName = `quiz-sessions-${patientId}`
    const client = getSupabaseClient()
    const channel = client
      .channel(channelName)
      .on(
        'postgres_changes',
        {
          event: '*',
          schema: 'public',
          table: 'quiz_sessions',
          filter: `patient_id=eq.${patientId}`
        },
        callback
      )
      .subscribe()

    this.channels.set(channelName, channel)
    return channel
  }

  // Unsubscribe from a channel
  unsubscribe(channelName: string) {
    const channel = this.channels.get(channelName)
    if (channel) {
      const client = getSupabaseClient()
      client.removeChannel(channel)
      this.channels.delete(channelName)
    }
  }

  // Unsubscribe from all channels
  unsubscribeAll() {
    const client = getSupabaseClient()
    for (const [channelName, channel] of this.channels) {
      client.removeChannel(channel)
    }
    this.channels.clear()
  }

  // Get active channels
  getActiveChannels() {
    return Array.from(this.channels.keys())
  }
}

// Create singleton instance
export const realtimeManager = new RealtimeManager()

// Utility functions
export const utils = {
  // Check if Supabase is properly configured
  isConfigured: () => {
    return isInitialized
  },

  // Get connection status
  getConnectionStatus: () => {
    try {
      const client = getSupabaseClient()
      return client.realtime.isConnected()
    } catch {
      return false
    }
  },

  // Health check
  healthCheck: async () => {
    try {
      const client = getSupabaseClient()
      const { data, error } = await client
        .from('patients')
        .select('count', { count: 'exact', head: true })

      const healthStatus = {
        configured: utils.isConfigured(),
        connected: !error,
        realtimeEnabled: realtimeEnabledFlag,
        realtimeConnected: utils.getConnectionStatus(),
        error: error?.message,
        permissions: {
          canRead: !error,
          hasRLSError: error ? isRLSError(error) : false
        }
      }

      if (error && isRLSError(error)) {
        const userFriendlyError = createUserFriendlyError(error, 'checking database connection')
        healthStatus.error = userFriendlyError.message
      }

      return healthStatus
    } catch (err) {
      const isRLS = isRLSError(err)
      return {
        configured: utils.isConfigured(),
        connected: false,
        realtimeEnabled: realtimeEnabledFlag,
        realtimeConnected: false,
        error: err instanceof Error ? err.message : 'Unknown error',
        permissions: {
          canRead: false,
          hasRLSError: isRLS
        }
      }
    }
  }
}

// Export enhanced error handler for use in components
export { errorHandler } from './auth-error-handler'

export default supabase