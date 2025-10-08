/**
 * MSW Server Setup
 * Configures mock server for different test environments
 */
import { setupServer } from 'msw/node'
import { handlers } from './handlers'

/**
 * Node.js test server
 * Used by Jest tests
 */
export const server = setupServer(...handlers)
