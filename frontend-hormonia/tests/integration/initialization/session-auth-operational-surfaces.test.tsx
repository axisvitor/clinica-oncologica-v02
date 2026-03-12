import React from 'react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { EnvironmentSetup } from '@/features/initialization/EnvironmentSetup'
import { ServiceMonitor } from '@/features/initialization/ServiceMonitor'

const { mockLoadConfig, mockGetRuntimeConfigSync, mockToast, mockApiClient } = vi.hoisted(() => ({
  mockLoadConfig: vi.fn(),
  mockGetRuntimeConfigSync: vi.fn(),
  mockToast: vi.fn(),
  mockApiClient: {
    setBaseURL: vi.fn(),
    getSessionHeaders: vi.fn(() => ({})),
  },
}))

vi.mock('@/config', () => ({
  loadConfig: mockLoadConfig,
  getRuntimeConfigSync: mockGetRuntimeConfigSync,
}))

vi.mock('@/hooks/use-toast', () => ({
  toast: mockToast,
}))

vi.mock('@/lib/api-client', () => ({
  apiClient: mockApiClient,
}))

const baseConfig = {
  API_BASE_URL: 'http://localhost:8000',
  WS_BASE_URL: undefined,
  WHATSAPP_INSTANCE_NAME: 'hormonia-instance',
  SENTRY_DSN: 'https://abc123@o1.ingest.sentry.io/1',
  SESSION_TIMEOUT: 28800000,
  TOKEN_REFRESH_THRESHOLD: 300000,
}

describe('session-auth operational surfaces', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    mockLoadConfig.mockResolvedValue(baseConfig)
    mockGetRuntimeConfigSync.mockReturnValue({
      VITE_API_BASE_URL: 'http://localhost:8000',
      VITE_WS_BASE_URL: undefined,
      VITE_FIREBASE_API_KEY: undefined,
      VITE_FIREBASE_AUTH_DOMAIN: undefined,
      VITE_FIREBASE_PROJECT_ID: undefined,
    })

    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)

        if (url.endsWith('/health')) {
          return {
            ok: true,
            status: 200,
            json: async () => ({ status: 'ok' }),
          } satisfies Partial<Response>
        }

        if (url.endsWith('/api/v2/auth/csrf-token')) {
          return {
            ok: true,
            status: 200,
            json: async () => ({ csrf_token: 'csrf-token-123' }),
          } satisfies Partial<Response>
        }

        if (url.endsWith('/api/v2/ai/health')) {
          return {
            ok: true,
            status: 200,
            json: async () => ({
              status: 'healthy',
              gemini_api: {
                status: 'healthy',
                enabled: true,
              },
            }),
          } satisfies Partial<Response>
        }

        throw new Error(`Unexpected fetch URL: ${url}`)
      }) as typeof fetch
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders environment setup around session auth instead of Firebase config', async () => {
    const onComplete = vi.fn()
    const onError = vi.fn()

    render(<EnvironmentSetup onComplete={onComplete} onError={onError} />)

    expect(screen.queryByText('Firebase Configuration')).not.toBeInTheDocument()

    expect(await screen.findByText('Autenticação por Sessão')).toBeInTheDocument()
    expect(
      screen.getByText(/Prontidão do login\/restore via cookies HTTP \+ CSRF do backend/i)
    ).toBeInTheDocument()

    await waitFor(
      () => {
        expect(onComplete).toHaveBeenCalled()
      },
      { timeout: 3000 }
    )

    expect(onError).not.toHaveBeenCalled()
  })

  it('reports backend session readiness in service monitor without Firebase blockers', async () => {
    const onComplete = vi.fn()
    const onError = vi.fn()

    render(<ServiceMonitor onComplete={onComplete} onError={onError} />)

    expect(await screen.findByText('Sessão do Backend')).toBeInTheDocument()
    expect(screen.queryByText('Firebase Authentication')).not.toBeInTheDocument()
    expect(
      screen.getByText(/Prontidão do login e restore via cookies HTTP \+ CSRF próprio/i)
    ).toBeInTheDocument()

    await waitFor(
      () => {
        expect(onComplete).toHaveBeenCalled()
      },
      { timeout: 4000 }
    )

    expect(onError).not.toHaveBeenCalled()
  })
})
