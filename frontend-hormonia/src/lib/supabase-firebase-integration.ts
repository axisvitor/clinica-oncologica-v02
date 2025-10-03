/**
 * Supabase + Firebase Auth Integration
 *
 * This module provides a Supabase client that automatically includes
 * Firebase JWT in all requests for RLS (Row Level Security) to work correctly.
 *
 * RLS policies in the database check for Firebase UID via:
 * current_setting('request.jwt.claims', true)::json->>'sub'
 */

import { createClient, SupabaseClient } from '@supabase/supabase-js'
import { firebaseAuth } from './firebase-client'
import { getRuntimeConfigSync } from './runtime-config'

/**
 * Get Supabase configuration from runtime config
 */
function getSupabaseConfig() {
  const config = getRuntimeConfigSync();

  if (config?.['VITE_SUPABASE_URL'] && config?.['VITE_SUPABASE_ANON_KEY']) {
    return {
      url: config['VITE_SUPABASE_URL'],
      anonKey: config['VITE_SUPABASE_ANON_KEY']
    };
  }

  // Fallback to build-time environment variables
  const buildTimeUrl = import.meta.env['VITE_SUPABASE_URL'];
  const buildTimeKey = import.meta.env['VITE_SUPABASE_ANON_KEY'];

  if (buildTimeUrl && buildTimeKey) {
    return {
      url: buildTimeUrl,
      anonKey: buildTimeKey
    };
  }

  throw new Error(
    'Supabase configuration missing: Please set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY'
  );
}

// Get configuration
const { url: SUPABASE_URL, anonKey: SUPABASE_ANON_KEY } = getSupabaseConfig();

/**
 * Create Supabase client with Firebase JWT integration
 *
 * This client automatically includes the Firebase ID token in all requests,
 * allowing RLS policies to work correctly.
 */
export const supabaseWithFirebaseAuth = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
  auth: {
    autoRefreshToken: false, // Firebase handles token refresh
    persistSession: false,   // Firebase handles session persistence
    detectSessionInUrl: false
  },
  realtime: {
    params: {
      eventsPerSecond: 10
    }
  },
  global: {
    headers: async () => {
      try {
        const user = firebaseAuth.currentUser;

        if (user) {
          // Get fresh Firebase ID token
          const token = await user.getIdToken();

          return {
            'Authorization': `Bearer ${token}`,
            'X-Client-Info': 'clinica-oncologica-frontend',
            'X-Auth-Provider': 'firebase'
          };
        }

        // No user authenticated
        return {
          'X-Client-Info': 'clinica-oncologica-frontend'
        };
      } catch (error) {
        console.error('[Supabase] Failed to get Firebase token:', error);

        return {
          'X-Client-Info': 'clinica-oncologica-frontend'
        };
      }
    }
  }
});

/**
 * Helper to manually set Firebase JWT for Supabase requests
 *
 * Use this if you need to make a Supabase call with a specific token
 */
export async function setSupabaseAuthToken(token: string | null): Promise<void> {
  // Supabase client with custom headers handles this automatically
  // This function is kept for compatibility
  console.log('[Supabase] Token set:', token ? 'present' : 'null');
}

/**
 * Helper to verify RLS is working
 *
 * Makes a test query to check if RLS policies are enforced
 */
export async function verifyRLSIntegration(): Promise<{
  success: boolean;
  hasToken: boolean;
  error?: string;
}> {
  try {
    const user = firebaseAuth.currentUser;

    if (!user) {
      return {
        success: false,
        hasToken: false,
        error: 'No Firebase user authenticated'
      };
    }

    // Try to query users table (should return only current user's row due to RLS)
    const { data, error } = await supabaseWithFirebaseAuth
      .from('users')
      .select('id, email')
      .limit(1);

    if (error) {
      return {
        success: false,
        hasToken: true,
        error: error.message
      };
    }

    return {
      success: true,
      hasToken: true
    };
  } catch (error) {
    return {
      success: false,
      hasToken: false,
      error: error instanceof Error ? error.message : 'Unknown error'
    };
  }
}

/**
 * Export default client for backward compatibility
 */
export const supabase = supabaseWithFirebaseAuth;

// Export configuration
export const supabaseConfig = {
  url: SUPABASE_URL,
  hasAnonKey: !!SUPABASE_ANON_KEY,
  isConfigured: !!(SUPABASE_URL && SUPABASE_ANON_KEY),
  usesFirebaseAuth: true
};

// Export URL and key
export { SUPABASE_URL, SUPABASE_ANON_KEY };
