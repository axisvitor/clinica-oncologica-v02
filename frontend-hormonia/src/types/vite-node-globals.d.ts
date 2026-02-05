import type { TestingLibraryMatchers } from '@testing-library/jest-dom/matchers'

declare global {
  var afterEach: typeof import('vitest').afterEach
  var beforeEach: typeof import('vitest').beforeEach
  var expect: typeof import('vitest').expect
  var describe: typeof import('vitest').describe
  var it: typeof import('vitest').it
  var vi: typeof import('vitest').vi
}

declare module 'vitest' {
  interface Assertion<T = unknown> extends TestingLibraryMatchers<string, T> {}
  interface AsymmetricMatchersContaining extends TestingLibraryMatchers<string, unknown> {}
}

declare module 'url' {
  export function fileURLToPath(url: string | URL): string
}

declare module 'path' {
  export function dirname(path: string): string
  export function resolve(...paths: string[]): string
}

