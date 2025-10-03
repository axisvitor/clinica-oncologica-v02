import { setupServer } from 'msw/node'
import { handlers } from './handlers'

// Setup Mock Service Worker server for Node.js testing environment
export const server = setupServer(...handlers)

// Enable API mocking before all tests
beforeAll(() => {
  server.listen({
    onUnhandledRequest: 'warn'
  })
})

// Reset any runtime request handlers after each test
afterEach(() => {
  server.resetHandlers()
})

// Disable API mocking after all tests
afterAll(() => {
  server.close()
})