/// <reference types="vitest" />
import { defineConfig } from 'vite'
import { fileURLToPath } from 'url'
import { dirname, resolve } from 'path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

export default defineConfig({
  resolve: {
    alias: {
      '@/config': resolve(__dirname, './tests/mocks/config.mock.ts'),
      '@': resolve(__dirname, './src'),
      '~backend/client': resolve(__dirname, './client'),
      '~backend': resolve(__dirname, '../Backend'),
    },
  },
  plugins: [
    tailwindcss(),
    react(),
  ],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
    include: ['./tests/**/*.{test,spec}.{js,ts,jsx,tsx}'],
    exclude: ['./tests/e2e/**', './tests/benchmark/**', './node_modules/**'],
    css: true,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html', 'lcov'],
      reportsDirectory: './coverage',
      exclude: [
        'node_modules/',
        'tests/',
        'dist/',
        'coverage/',
        '**/*.d.ts',
        '**/*.config.*',
        '**/vite.config.*',
        '**/vitest.config.*',
        '**/*.test.*',
        '**/*.spec.*',
        '**/test-utils.*',
        '**/setup.*',
        'src/mocks/**',
        'src/**/*.mock.ts',
        'src/**/*.stories.tsx',
        '**/test-setup.*',
        '**/__mocks__/**'
      ],
      // Sprint 1 Coverage Targets: 40% minimum (increased from 26%)
      // Sprint 3 Target: 70%+
      thresholds: {
        global: {
          branches: 40,
          functions: 40,
          lines: 40,
          statements: 40
        }
      },
      skipFull: true,
      // Fail build if coverage below threshold
      all: true,
      clean: true
    },
    pool: 'threads',
    poolOptions: {
      threads: {
        minThreads: 1,
        maxThreads: 4
      }
    },
    testTimeout: 10000,
    hookTimeout: 10000,
    teardownTimeout: 5000,
    mockReset: true,
    clearMocks: true,
    restoreMocks: true,
    retry: 2,
    bail: 5,
    reporters: ['verbose', 'json', 'html'],
    outputFile: {
      json: './test-results/test-results.json',
      html: './test-results/index.html'
    },
    watch: false,
    ui: false
  }
})