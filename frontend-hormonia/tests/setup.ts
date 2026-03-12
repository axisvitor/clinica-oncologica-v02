import '@testing-library/jest-dom'
import { beforeAll, afterEach, vi, expect } from 'vitest'
import { cleanup } from '@testing-library/react'

// Extend Vitest's expect with jest-dom matchers
import * as matchers from '@testing-library/jest-dom/matchers'
expect.extend(matchers)

// Mock environment variables
vi.mock('../config', () => ({
  API_BASE_URL: 'http://localhost:8000/api/v2',
  WS_URL: 'ws://localhost:8000/ws',
  SUPABASE_URL: 'https://test.supabase.co',
  SUPABASE_ANON_KEY: 'test-key',
  ENVIRONMENT: 'test'
}))

// Mock window.matchMedia (not implemented in JSDOM)
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(), // deprecated
    removeListener: vi.fn(), // deprecated
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})

// Mock ResizeObserver
global.ResizeObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
}))

// Mock IntersectionObserver
global.IntersectionObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
}))

// Mock HTMLElement.scrollIntoView
Element.prototype.scrollIntoView = vi.fn()

// Mock HTMLButtonElement.indeterminate property
Object.defineProperty(HTMLButtonElement.prototype, 'indeterminate', {
  get: function () {
    return this.getAttribute('data-indeterminate') === 'true'
  },
  set: function (value: boolean) {
    if (value) {
      this.setAttribute('data-indeterminate', 'true')
    } else {
      this.removeAttribute('data-indeterminate')
    }
  },
  configurable: true,
})

// Polyfill pointer capture APIs used by Radix in JSDOM
if (!(Element.prototype as any).setPointerCapture) {
  ;(Element.prototype as any).setPointerCapture = vi.fn()
}
if (!(Element.prototype as any).releasePointerCapture) {
  ;(Element.prototype as any).releasePointerCapture = vi.fn()
}
if (!(Element.prototype as any).hasPointerCapture) {
  ;(Element.prototype as any).hasPointerCapture = vi.fn().mockReturnValue(false)
}

// Mock console methods to reduce noise in tests
global.console = {
  ...console,
  warn: vi.fn(),
  error: vi.fn(),
  debug: vi.fn(),
}

// Setup for Web APIs that might not be available in test environment
beforeAll(() => {
  // Mock fetch if not available
  if (!global.fetch) {
    global.fetch = vi.fn()
  }

  // Mock WebSocket
  global.WebSocket = vi.fn().mockImplementation(() => ({
    close: vi.fn(),
    send: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    readyState: 1,
    CONNECTING: 0,
    OPEN: 1,
    CLOSING: 2,
    CLOSED: 3,
  }))
})

// Cleanup after each test case
afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

// Global test utilities
declare global {
  namespace Vi {
    interface JestAssertion<T = any> extends jest.Matchers<T> {}
  }
}