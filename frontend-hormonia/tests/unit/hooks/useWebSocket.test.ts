import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const hookSource = readFileSync(resolve(process.cwd(), 'src/hooks/useWebSocket.ts'), 'utf8')

describe('useWebSocket hook seam', () => {
  it('bootstraps cookie-first websocket URLs without legacy session_id query fallback', () => {
    expect(hookSource).toMatch(
      /function buildWebSocketUrl\(requestedUrl: string, configUrl: string\): string/
    )
    expect(hookSource).not.toMatch(/searchParams\.set\(['"]session_id['"],/)
    expect(hookSource).not.toMatch(/isLikelyJwt/)
  })

  it('keeps authenticated-session gating without reintroducing query transport', () => {
    expect(hookSource).toMatch(/const sessionAuthState = useMemo\(/)
    expect(hookSource).toMatch(/if \(!user && !sessionAuthState\)/)
    expect(hookSource).toMatch(/if \(user \|\| sessionAuthState\)/)
    expect(hookSource).not.toMatch(/sessionQueryId/)
  })

  it('preserves stable websocket auth diagnostics on the generic hook path', () => {
    expect(hookSource).toMatch(/AUTH_WEBSOCKET_SESSION_INVALID/)
    expect(hookSource).toMatch(/AUTH_WEBSOCKET_SESSION_LOOKUP_FAILED/)
    expect(hookSource).toMatch(/connection_id/)
    expect(hookSource).toMatch(/Stable websocket auth diagnostics received/)
  })

  it('keeps reconnect scheduling and user-safe connection logging intact', () => {
    expect(hookSource).toMatch(/Scheduling reconnection attempt/)
    expect(hookSource).toMatch(/reconnectTimeoutRef\.current = setTimeout\(/)
    expect(hookSource).toMatch(/void connect\(\)/)
    expect(hookSource).toMatch(/Cannot connect WebSocket: no authenticated session available/)
  })
})
