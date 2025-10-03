/**
 * Test setup file for Jest and testing-library
 */

import '@testing-library/jest-dom'

// Extend matchers type for TypeScript
declare global {
  namespace Vi {
    interface JestAssertion<T = any> extends jest.Matchers<void, T> {
      toBeInTheDocument(): void
      toHaveValue(value: string | number | string[]): void
      toBeChecked(): void
      toBeDisabled(): void
      toBeEnabled(): void
      toBeVisible(): void
      toHaveClass(className: string): void
      toHaveTextContent(text: string | RegExp): void
      toHaveAttribute(attr: string, value?: string): void
    }
  }
}

// Mock IntersectionObserver
class MockIntersectionObserver {
  root = null
  rootMargin = ''
  thresholds = []

  constructor(callback: IntersectionObserverCallback, options?: IntersectionObserverInit) {}
  disconnect() {}
  observe() {}
  unobserve() {}
  takeRecords(): IntersectionObserverEntry[] { return [] }
}

global.IntersectionObserver = MockIntersectionObserver as any

// Mock ResizeObserver
global.ResizeObserver = class ResizeObserver {
  constructor() {}
  disconnect() {}
  observe() {}
  unobserve() {}
}

// Mock window.matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => {},
  }),
})