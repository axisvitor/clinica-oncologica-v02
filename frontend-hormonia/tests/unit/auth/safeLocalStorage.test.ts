import { vi, describe, it, expect, beforeEach, afterEach, Mock } from 'vitest'
import { safeLocalStorage } from '@/app/providers/AuthContext'

// Mock the logger to verify calls
const mockLogger = {
    log: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
}

vi.mock('@/lib/logger', () => ({
    createLogger: () => mockLogger,
}))

describe('safeLocalStorage', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        vi.spyOn(Storage.prototype, 'setItem')
        vi.spyOn(Storage.prototype, 'getItem')
        vi.spyOn(Storage.prototype, 'removeItem')
    })

    afterEach(() => {
        vi.restoreAllMocks()
    })

    describe('setItem', () => {
        it('returns true on success', () => {
            const result = safeLocalStorage.setItem('key', 'value')
            expect(result).toBe(true)
            expect(localStorage.setItem).toHaveBeenCalledWith('key', 'value')
            expect(mockLogger.log).toHaveBeenCalledWith("localStorage.setItem('key') succeeded")
        })

        it('returns false when localStorage throws error (e.g. private mode)', () => {
            vi.mocked(localStorage.setItem).mockImplementationOnce(() => {
                throw new Error('QuotaExceededError')
            })

            const result = safeLocalStorage.setItem('key', 'value')
            expect(result).toBe(false)
            expect(mockLogger.warn).toHaveBeenCalledWith(
                "localStorage.setItem('key') failed (likely private mode):",
                expect.any(Error)
            )
        })
    })

    describe('getItem', () => {
        it('returns value on success', () => {
            vi.mocked(localStorage.getItem).mockReturnValueOnce('value')
            const result = safeLocalStorage.getItem('key')
            expect(result).toBe('value')
            expect(localStorage.getItem).toHaveBeenCalledWith('key')
        })

        it('returns null when localStorage throws error', () => {
            vi.mocked(localStorage.getItem).mockImplementationOnce(() => {
                throw new Error('SecurityError')
            })

            const result = safeLocalStorage.getItem('key')
            expect(result).toBeNull()
            expect(mockLogger.warn).toHaveBeenCalledWith(
                "localStorage.getItem('key') failed:",
                expect.any(Error)
            )
        })
    })

    describe('removeItem', () => {
        it('returns true on success', () => {
            const result = safeLocalStorage.removeItem('key')
            expect(result).toBe(true)
            expect(localStorage.removeItem).toHaveBeenCalledWith('key')
            expect(mockLogger.log).toHaveBeenCalledWith("localStorage.removeItem('key') succeeded")
        })

        it('returns false when localStorage throws error', () => {
            vi.mocked(localStorage.removeItem).mockImplementationOnce(() => {
                throw new Error('SecurityError')
            })

            const result = safeLocalStorage.removeItem('key')
            expect(result).toBe(false)
            expect(mockLogger.warn).toHaveBeenCalledWith(
                "localStorage.removeItem('key') failed:",
                expect.any(Error)
            )
        })
    })
})
