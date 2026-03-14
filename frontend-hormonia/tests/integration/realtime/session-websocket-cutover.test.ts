import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const websocketManagerSource = readFileSync(resolve(process.cwd(), 'src/lib/websocket.ts'), 'utf8')
const websocketHookSource = readFileSync(resolve(process.cwd(), 'src/hooks/useWebSocket.ts'), 'utf8')
const metricsWebSocketSource = readFileSync(
  resolve(process.cwd(), 'src/hooks/useMetricsWebSocket.ts'),
  'utf8'
)

describe('session websocket cutover proof', () => {
  it('fails while the browser websocket handshake still appends token=<firebase_jwt>', () => {
    expect(websocketManagerSource).not.toMatch(/params\.append\('token',\s*token\)/)
    expect(websocketManagerSource).not.toMatch(/params\.append\("token",\s*token\)/)
  })

  it('fails while the shared websocket manager still appends legacy ?session_id= fallback', () => {
    expect(websocketManagerSource).not.toMatch(/searchParams\.set\(['"]session_id['"],/)
  })

  it('fails while the hook websocket builders still append legacy ?session_id= fallback', () => {
    expect(websocketHookSource).not.toMatch(/searchParams\.set\(['"]session_id['"],/)
    expect(metricsWebSocketSource).not.toMatch(/searchParams\.set\(['"]session_id['"],/)
  })

  it('keeps explicit reconnect and re-subscribe behavior for existing room subscriptions', () => {
    expect(websocketManagerSource).toMatch(/roomSubscriptions\.forEach/)
    expect(websocketManagerSource).toMatch(/joinPatientRoom/)
    expect(websocketManagerSource).toMatch(/subscribeToQuizEvents/)
  })

  it('pins stable invalid-session diagnostics on the frontend websocket auth path', () => {
    for (const source of [websocketManagerSource, websocketHookSource, metricsWebSocketSource]) {
      expect(source).toMatch(/AUTH_WEBSOCKET_SESSION_INVALID/)
      expect(source).toMatch(/AUTH_WEBSOCKET_SESSION_LOOKUP_FAILED/)
    }

    expect(websocketManagerSource).toMatch(/connection_id/)
    expect(websocketHookSource).toMatch(/connection_id/)
    expect(metricsWebSocketSource).toMatch(/connection_id/)
  })
})
