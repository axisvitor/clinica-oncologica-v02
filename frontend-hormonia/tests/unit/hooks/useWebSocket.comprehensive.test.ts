import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const hookSource = readFileSync(resolve(process.cwd(), 'src/hooks/useWebSocket.ts'), 'utf8')
const metricsHookSource = readFileSync(resolve(process.cwd(), 'src/hooks/useMetricsWebSocket.ts'), 'utf8')

describe('realtime hook seams', () => {
  it('keeps helper hooks wired through the generic websocket seam', () => {
    expect(hookSource).toMatch(/export function useSystemNotifications\(\)/)
    expect(hookSource).toMatch(/message\.type === 'system_notification'/)
    expect(hookSource).toMatch(/export function usePatientUpdates\(\)/)
    expect(hookSource).toMatch(/message\.type === 'patient_update'/)
  })

  it('keeps outbound generic-hook messaging timestamped and connection-guarded', () => {
    expect(hookSource).toMatch(/const sendMessage = useCallback\(/)
    expect(hookSource).toMatch(/timestamp: new Date\(\)\.toISOString\(\)/)
    expect(hookSource).toMatch(/Cannot send message: WebSocket not connected/)
  })

  it('bootstraps the metrics websocket without legacy session_id query fallback', () => {
    expect(metricsHookSource).toMatch(/function buildMetricsWebSocketUrl\(baseUrl: string\): string/)
    expect(metricsHookSource).not.toMatch(/searchParams\.set\(['"]session_id['"],/)
    expect(metricsHookSource).not.toMatch(/apiClient\.getAuthToken\(/)
    expect(metricsHookSource).toMatch(/session\?\.session_id \|\| session\?\.access_token \|\| null/)
  })

  it('preserves stable auth diagnostics on the metrics websocket path', () => {
    expect(metricsHookSource).toMatch(/AUTH_WEBSOCKET_SESSION_INVALID/)
    expect(metricsHookSource).toMatch(/AUTH_WEBSOCKET_SESSION_LOOKUP_FAILED/)
    expect(metricsHookSource).toMatch(/Metrics websocket auth diagnostics received/)
    expect(metricsHookSource).toMatch(/connection_id/)
  })

  it('keeps metrics reconnect and heartbeat diagnostics inspectable', () => {
    expect(metricsHookSource).toMatch(/Heartbeat ping sent/)
    expect(metricsHookSource).toMatch(/Scheduling reconnection/)
    expect(metricsHookSource).toMatch(/connectRef\.current\(\)/)
    expect(metricsHookSource).toMatch(/Max reconnection attempts reached/)
  })

  it('keeps metrics auth gating aligned with the cookie-first generic hook rule', () => {
    expect(metricsHookSource).toMatch(/const sessionAuthState = useMemo\(/)
    expect(metricsHookSource).toMatch(/if \(!user && !sessionAuthState\)/)
    expect(metricsHookSource).toMatch(/if \(user \|\| sessionAuthState\)/)
    expect(metricsHookSource).not.toMatch(/sessionQueryId/)
  })
})
