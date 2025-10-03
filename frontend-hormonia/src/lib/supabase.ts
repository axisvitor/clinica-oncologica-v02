import { createClient } from '@supabase/supabase-js'
import { getRuntimeConfigSync } from './runtime-config'

// Get Supabase configuration from runtime config
function getSupabaseConfig() {
  // First try sync config (if already loaded)
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

  // No fallback - throw error if configuration is missing
  throw new Error(
    'Supabase configuration missing: Please set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY environment variables. ' +
    'Check your .env file or deployment configuration.'
  );
}

// Get configuration
const { url: SUPABASE_URL, anonKey: SUPABASE_ANON_KEY } = getSupabaseConfig();

// Create Supabase client with robust configuration
// Uses runtime configuration which handles environment variables and fallbacks
export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
  auth: {
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: true,
    flowType: 'pkce'
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
});

// Export configuration for debugging purposes
export const supabaseConfig = {
  url: SUPABASE_URL,
  // Don't expose the key in logs
  hasAnonKey: !!SUPABASE_ANON_KEY,
  isConfigured: !!(SUPABASE_URL && SUPABASE_ANON_KEY)
};

// Export URL and key for backward compatibility
export { SUPABASE_URL, SUPABASE_ANON_KEY };