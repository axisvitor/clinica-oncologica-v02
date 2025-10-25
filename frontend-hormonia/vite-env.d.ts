/// <reference types="vite/client" />

/**
 * Type definitions for Vite environment variables
 *
 * This file defines all available environment variables for the application.
 * Environment variables must be prefixed with VITE_ to be exposed to the client.
 *
 * AI Configuration:
 * - VITE_OPENAI_API_KEY: OpenAI API key for GPT models
 * - VITE_GEMINI_API_KEY: Google Gemini API key for AI features
 * - VITE_LANGCHAIN_API_KEY: LangChain API key for orchestration
 *
 * AI Feature Flags:
 * - VITE_AI_CHAT_ENABLED: Enable/disable AI chat (default: true if keys present)
 * - VITE_AI_ANALYTICS_ENABLED: Enable/disable AI analytics (default: true)
 * - VITE_AI_INSIGHTS_ENABLED: Enable/disable AI insights (default: true)
 * - VITE_AI_RECOMMENDATIONS_ENABLED: Enable/disable AI recommendations (default: true)
 */
interface ImportMetaEnv {
  // Core API Configuration
  readonly VITE_API_URL: string
  readonly VITE_API_BASE_URL: string
  readonly VITE_WS_URL: string
  readonly VITE_WS_BASE_URL: string
  readonly VITE_WHATSAPP_INSTANCE_NAME: string

  // AI Service API Keys
  readonly VITE_OPENAI_API_KEY: string
  readonly VITE_LANGCHAIN_API_KEY: string
  readonly VITE_GEMINI_API_KEY: string

  // AI Feature Flags
  readonly VITE_AI_CHAT_ENABLED: string
  readonly VITE_AI_ANALYTICS_ENABLED: string
  readonly VITE_AI_INSIGHTS_ENABLED: string
  readonly VITE_AI_RECOMMENDATIONS_ENABLED: string

  // Monitoring & Analytics
  readonly VITE_SENTRY_DSN: string
  readonly VITE_ANALYTICS_TRACKING_ID: string

  // Environment Settings
  readonly VITE_ENVIRONMENT: string
  readonly VITE_DEBUG_MODE: string
  readonly VITE_MAX_FILE_SIZE: string
  readonly VITE_SUPPORTED_FILE_TYPES: string
  readonly VITE_SESSION_TIMEOUT: string
  readonly VITE_TOKEN_REFRESH_THRESHOLD: string
  readonly VITE_CLIENT_TARGET: string
  readonly VITE_ENABLE_PREFETCH: string

  // Vite Built-in
  readonly MODE: string
  readonly DEV: boolean
  readonly PROD: boolean
  readonly SSR: boolean
  readonly BASE_URL: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

// Node.js process.env types
declare namespace NodeJS {
  interface ProcessEnv {
    readonly CI?: string
    readonly NODE_ENV?: string
    readonly PORT?: string
  }
}
