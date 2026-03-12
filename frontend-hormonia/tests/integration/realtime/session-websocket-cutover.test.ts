import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const websocketSource = readFileSync(resolve(process.cwd(), 'src/lib/websocket.ts'), 'utf8')

describe('session websocket cutover proof', () => {
  it('fails while the browser websocket handshake still appends token=<firebase_jwt>', () => {
    expect(websocketSource).not.toMatch(/params\.append\('token',\s*token\)/)
    expect(websocketSource).not.toMatch(/params\.append\("token",\s*token\)/)
  })

  it('keeps explicit reconnect and re-subscribe behavior for existing room subscriptions', () => {
    expect(websocketSource).toMatch(/roomSubscriptions\.forEach/)
    expect(websocketSource).toMatch(/joinPatientRoom/)
    expect(websocketSource).toMatch(/subscribeToQuizEvents/)
  })

  it('pins stable invalid-session diagnostics on the frontend websocket auth path', () => {
    expect(websocketSource).toMatch(/AUTH_WEBSOCKET_SESSION_INVALID/)
    expect(websocketSource).toMatch(/connection_id/)
  })
})
