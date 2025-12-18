/**
 * Testing utilities and type declarations
 */

import '@testing-library/jest-dom'
import 'vitest'

declare module 'vitest' {
  // @ts-ignore
  interface Assertion {
    toBeInTheDocument(): any
    toHaveClass(className: string): any
    toHaveAttribute(attr: string, value?: string): any
    toBeVisible(): any
    toBeDisabled(): any
    toBeEnabled(): any
    toHaveValue(value: string | number): any
    toHaveTextContent(text: string): any
    toBeChecked(): any
  }
}

export { }
