/**
 * Testing utilities and type declarations
 */

import '@testing-library/jest-dom'
import 'vitest'

declare module 'vitest' {
  // @ts-ignore - Extending Vitest's Assertion interface with jest-dom matchers
  interface Assertion {
    toBeInTheDocument(): void
    toHaveClass(className: string): void
    toHaveAttribute(attr: string, value?: string): void
    toBeVisible(): void
    toBeDisabled(): void
    toBeEnabled(): void
    toHaveValue(value: string | number): void
    toHaveTextContent(text: string): void
    toBeChecked(): void
  }
}

export {}
