import { describe, it, expect, vi, afterEach } from 'vitest'
import { createAuthLock, AUTH_LOCK_TIMEOUT_MS, type AuthLockState } from '@/app/providers/AuthContext'

const createLockRef = (state: Partial<AuthLockState> = {}) => ({
  current: {
    locked: false,
    timestamp: 0,
    operation: null,
    ...state
  }
})

const createLogger = () => ({
  log: vi.fn(),
  warn: vi.fn()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('Auth Lock - Acquisition and Release', () => {
  it('acquireAuthLock retorna true se lock livre', () => {
    vi.spyOn(Date, 'now').mockReturnValue(1000)
    const lockRef = createLockRef()
    const logger = createLogger()
    const { acquireAuthLock } = createAuthLock(lockRef, logger)

    expect(acquireAuthLock('login')).toBe(true)
    expect(lockRef.current.locked).toBe(true)
    expect(lockRef.current.operation).toBe('login')
    expect(logger.log).toHaveBeenCalledWith('Auth lock acquired for login')
  })

  it('acquireAuthLock retorna false se lock ativo', () => {
    vi.spyOn(Date, 'now').mockReturnValue(1500)
    const lockRef = createLockRef({ locked: true, timestamp: 1000, operation: 'login' })
    const logger = createLogger()
    const { acquireAuthLock } = createAuthLock(lockRef, logger)

    expect(acquireAuthLock('restore')).toBe(false)
    expect(lockRef.current.operation).toBe('login')
    expect(logger.warn).toHaveBeenCalled()
  })

  it('acquireAuthLock retorna true se lock expirou (>5s)', () => {
    vi.spyOn(Date, 'now').mockReturnValue(1000 + AUTH_LOCK_TIMEOUT_MS + 1)
    const lockRef = createLockRef({ locked: true, timestamp: 1000, operation: 'login' })
    const logger = createLogger()
    const { acquireAuthLock } = createAuthLock(lockRef, logger)

    expect(acquireAuthLock('restore')).toBe(true)
    expect(lockRef.current.operation).toBe('restore')
  })

  it('releaseAuthLock limpa lock corretamente', () => {
    vi.spyOn(Date, 'now').mockReturnValue(1000)
    const lockRef = createLockRef()
    const logger = createLogger()
    const { acquireAuthLock, releaseAuthLock } = createAuthLock(lockRef, logger)

    acquireAuthLock('login')
    releaseAuthLock()

    expect(lockRef.current.locked).toBe(false)
    expect(lockRef.current.timestamp).toBe(0)
    expect(lockRef.current.operation).toBeNull()
    expect(logger.log).toHaveBeenCalledWith('Auth lock released (login)')
  })
})

describe('Auth Lock - Timeout Behavior', () => {
  it('Lock expira apos 5 segundos', () => {
    const lockRef = createLockRef({ locked: true, timestamp: 1000, operation: 'login' })
    const logger = createLogger()
    const { acquireAuthLock } = createAuthLock(lockRef, logger)

    vi.spyOn(Date, 'now').mockReturnValue(1000 + AUTH_LOCK_TIMEOUT_MS + 10)
    expect(acquireAuthLock('restore')).toBe(true)
  })

  it('Lock nao expira antes de 5 segundos', () => {
    const lockRef = createLockRef({ locked: true, timestamp: 1000, operation: 'login' })
    const logger = createLogger()
    const { acquireAuthLock } = createAuthLock(lockRef, logger)

    vi.spyOn(Date, 'now').mockReturnValue(1000 + AUTH_LOCK_TIMEOUT_MS - 1)
    expect(acquireAuthLock('restore')).toBe(false)
  })

  it('Multiplas operacoes respeitam timeout', () => {
    const lockRef = createLockRef()
    const logger = createLogger()
    const { acquireAuthLock } = createAuthLock(lockRef, logger)

    const nowSpy = vi.spyOn(Date, 'now')
    nowSpy.mockReturnValue(2000)
    expect(acquireAuthLock('login')).toBe(true)

    nowSpy.mockReturnValue(2000 + 100)
    expect(acquireAuthLock('restore')).toBe(false)

    nowSpy.mockReturnValue(2000 + AUTH_LOCK_TIMEOUT_MS + 1)
    expect(acquireAuthLock('restore')).toBe(true)
  })
})

describe('Auth Lock - Operation Tracking', () => {
  it("Lock registra operacao 'login' corretamente", () => {
    vi.spyOn(Date, 'now').mockReturnValue(1234)
    const lockRef = createLockRef()
    const logger = createLogger()
    const { acquireAuthLock } = createAuthLock(lockRef, logger)

    acquireAuthLock('login')
    expect(lockRef.current.operation).toBe('login')
  })

  it("Lock registra operacao 'restore' corretamente", () => {
    vi.spyOn(Date, 'now').mockReturnValue(1234)
    const lockRef = createLockRef()
    const logger = createLogger()
    const { acquireAuthLock } = createAuthLock(lockRef, logger)

    acquireAuthLock('restore')
    expect(lockRef.current.operation).toBe('restore')
  })

  it('releaseAuthLock limpa operation field', () => {
    vi.spyOn(Date, 'now').mockReturnValue(1234)
    const lockRef = createLockRef({ locked: true, timestamp: 1234, operation: 'login' })
    const logger = createLogger()
    const { releaseAuthLock } = createAuthLock(lockRef, logger)

    releaseAuthLock()
    expect(lockRef.current.operation).toBeNull()
  })
})
