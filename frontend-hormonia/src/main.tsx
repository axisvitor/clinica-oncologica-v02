import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App' // App completo com autenticação
import { ConfigProvider } from '@/lib/config-initializer'
import { createLogger } from '@/lib/logger'
import './app/styles/index.css'

const logger = createLogger('main')
const sentryEnabled = Boolean(import.meta.env['VITE_SENTRY_DSN'])
let sentryInitPromise: Promise<typeof import('@/monitoring/sentry')> | null = null

const loadSentry = () => {
  if (!sentryEnabled) {
    return Promise.resolve(null)
  }

  if (!sentryInitPromise) {
    sentryInitPromise = import('@/monitoring/sentry')
  }

  return sentryInitPromise
}

const scheduleSentryInit = () => {
  void loadSentry().catch((error) => {
    logger.warn('Failed to load Sentry', error)
  })
}

if (sentryEnabled) {
  const windowWithIdle = window as Window & {
    requestIdleCallback?: (callback: () => void, options?: { timeout: number }) => number
  }

  if (windowWithIdle.requestIdleCallback) {
    windowWithIdle.requestIdleCallback(scheduleSentryInit, { timeout: 2000 })
  } else {
    setTimeout(scheduleSentryInit, 2000)
  }
}

// Global error handling for unhandled promise rejections
window.addEventListener('unhandledrejection', (event) => {
  // Prevent the default behavior (error overlay)
  event.preventDefault()

  // Check if it's a WebSocket or network error (non-critical)
  const isNonCritical =
    event.reason?.message?.includes('WebSocket') ||
    event.reason?.message?.includes('ws://') ||
    event.reason?.message?.includes('wss://') ||
    event.reason?.message?.includes('Failed to fetch') ||
    event.reason?.message?.includes('NetworkError')

  if (isNonCritical) {
    // Non-critical errors: log only in dev (logger is no-op in prod)
    logger.warn('Non-critical error handled gracefully:', event.reason?.message)
    return
  }

  // Critical errors: log and report to Sentry
  logger.error('Unhandled promise rejection:', event.reason)
  if (sentryEnabled) {
    void loadSentry()
      .then((sentryModule) => {
        sentryModule?.captureException(
          event.reason instanceof Error ? event.reason : new Error(String(event.reason)),
          {
            tags: { type: 'unhandled_rejection' },
            extra: { originalReason: event.reason },
          }
        )
      })
      .catch((error) => {
        logger.warn('Failed to report unhandled rejection', error)
      })
  }
})

const rootElement = document.getElementById('root')

if (!rootElement) {
  document.body.innerHTML = `
    <div style="display: flex; align-items: center; justify-content: center; height: 100vh; font-family: system-ui;">
      <div style="text-align: center;">
        <h1 style="color: red;">Erro: Elemento root não encontrado</h1>
        <p>Por favor, verifique o arquivo index.html</p>
      </div>
    </div>
  `
} else {
  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
      <ConfigProvider>
        <App />
      </ConfigProvider>
    </React.StrictMode>
  )
}
