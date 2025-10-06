// API Configuration
// The backend API URL - read from Vite env or fallback to production Railway URL
export const API_BASE_URL = import.meta.env['VITE_API_BASE_URL'] || 'https://clinica-oncologica-v02-production.up.railway.app'

// WebSocket Configuration
// The backend WebSocket URL - read from Vite env or fallback to production Railway WSS URL
export const WS_BASE_URL = import.meta.env['VITE_WS_BASE_URL'] || 'wss://clinica-oncologica-v02-production.up.railway.app/ws'

// WhatsApp Configuration
export const WHATSAPP_INSTANCE_NAME = import.meta.env['VITE_WHATSAPP_INSTANCE_NAME'] || 'hormonia-instance'

// AI Services Configuration
export const OPENAI_API_KEY = import.meta.env['VITE_OPENAI_API_KEY']
export const LANGCHAIN_API_KEY = import.meta.env['VITE_LANGCHAIN_API_KEY']

// Monitoring & Analytics
export const SENTRY_DSN = import.meta.env['VITE_SENTRY_DSN']
export const ANALYTICS_TRACKING_ID = import.meta.env['VITE_ANALYTICS_TRACKING_ID']

// Development Settings
export const ENVIRONMENT = import.meta.env['VITE_ENVIRONMENT'] || 'development'
export const DEBUG_MODE = import.meta.env['VITE_DEBUG_MODE'] === 'true'

// Security Settings
export const SESSION_TIMEOUT = parseInt(import.meta.env['VITE_SESSION_TIMEOUT'] || '3600000', 10) // 1 hour default
export const TOKEN_REFRESH_THRESHOLD = parseInt(import.meta.env['VITE_TOKEN_REFRESH_THRESHOLD'] || '300000', 10) // 5 minutes default

// Application Configuration
export const APP_CONFIG = {
  name: 'Neoplasias Litoral',
  version: '1.0.0',
  description: 'Sistema de Gestão de Terapia Hormonal',
  
  // Pagination defaults
  defaultPageSize: 20,
  maxPageSize: 100,
  
  // Cache settings
  cacheTime: 10 * 60 * 1000, // 10 minutes
  staleTime: 5 * 60 * 1000,  // 5 minutes
  
  // Real-time settings
  reconnectAttempts: 5,
  reconnectDelay: 1000,
  
  // File upload settings (from env vars)
  maxFileSize: parseInt(import.meta.env['VITE_MAX_FILE_SIZE'] || '10485760', 10),
  allowedFileTypes: import.meta.env['VITE_SUPPORTED_FILE_TYPES']?.split(',') || ['image/jpeg', 'image/png', 'image/gif', 'application/pdf']
}

// Theme configuration
export const THEME_CONFIG = {
  defaultTheme: 'light',
  themes: ['light', 'dark'],
  colors: {
    primary: 'hsl(221.2 83.2% 53.3%)',
    secondary: 'hsl(210 40% 98%)',
    accent: 'hsl(210 40% 96%)',
    muted: 'hsl(210 40% 96%)',
    destructive: 'hsl(0 84.2% 60.2%)',
    success: 'hsl(142.1 76.2% 36.3%)',
    warning: 'hsl(47.9 95.8% 53.1%)'
  }
}

// Feature Flags
export const FEATURES = {
  AI_CHAT: !!OPENAI_API_KEY,
  ANALYTICS: !!ANALYTICS_TRACKING_ID,
  ERROR_TRACKING: !!SENTRY_DSN,
  DEBUG: DEBUG_MODE && ENVIRONMENT === 'development',
  WHATSAPP_INTEGRATION: !!WHATSAPP_INSTANCE_NAME
}
