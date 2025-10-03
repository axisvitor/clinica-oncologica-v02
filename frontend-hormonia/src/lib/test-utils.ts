/**
 * Testing utilities and type declarations
 */

import '@testing-library/jest-dom'

declare global {
  namespace Vi {
    interface Assertion<T = any> {
      toBeInTheDocument(): T
      toHaveClass(className: string): T
      toHaveAttribute(attr: string, value?: string): T
      toBeVisible(): T
      toBeDisabled(): T
      toBeEnabled(): T
      toHaveValue(value: string | number): T
      toHaveTextContent(text: string): T
      toBeChecked(): T
    }
  }
}

export {}