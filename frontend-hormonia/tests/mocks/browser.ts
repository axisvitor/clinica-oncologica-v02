import { setupWorker } from 'msw/browser'
import { handlers } from './handlers'

// Setup Mock Service Worker for browser testing environment
export const worker = setupWorker(...handlers)

// Start the worker for development/testing
if (import.meta.env.MODE === 'development' || import.meta.env.MODE === 'test') {
  worker.start({
    onUnhandledRequest: 'warn',
    serviceWorker: {
      url: '/mockServiceWorker.js'
    }
  }).catch(console.error)
}