/// <reference types="vite/client" />

// Vite environment variables
interface ImportMetaEnv {
  readonly VITE_SUPABASE_URL: string
  readonly VITE_SUPABASE_ANON_KEY: string
  readonly VITE_API_URL?: string
  readonly VITE_API_BASE_URL?: string
  readonly VITE_WS_URL?: string
  readonly VITE_WS_BASE_URL?: string
  readonly VITE_WHATSAPP_INSTANCE_NAME?: string
  readonly VITE_OPENAI_API_KEY?: string
  readonly VITE_LANGCHAIN_API_KEY?: string
  readonly VITE_GEMINI_API_KEY?: string
  readonly VITE_ENVIRONMENT?: string
  readonly VITE_DEBUG_MODE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
