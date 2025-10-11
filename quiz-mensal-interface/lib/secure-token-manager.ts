/**
 * Secure Token Manager for Quiz Interface
 * Implements secure token storage and management with automatic cleanup
 */

class SecureTokenManager {
    private static instance: SecureTokenManager
    private tokenSymbol = Symbol('quiz-token')
    private tokenData: { value: string; expires: number } | null = null
    private cleanupTimer: NodeJS.Timeout | null = null

    private constructor() {
        // Bind cleanup to page unload
        if (typeof window !== 'undefined') {
            window.addEventListener('beforeunload', this.cleanup.bind(this))
            window.addEventListener('pagehide', this.cleanup.bind(this))
        }
    }

    static getInstance(): SecureTokenManager {
        if (!SecureTokenManager.instance) {
            SecureTokenManager.instance = new SecureTokenManager()
        }
        return SecureTokenManager.instance
    }

    /**
     * Store token securely with automatic expiration
     */
    setToken(token: string, expiresAt?: string): void {
        try {
            // Clear any existing token first
            this.clearToken()

            // Calculate expiration (default: 1 hour from now)
            const expires = expiresAt
                ? new Date(expiresAt).getTime()
                : Date.now() + (60 * 60 * 1000) // 1 hour

            // Store token with expiration
            this.tokenData = { value: token, expires }

            // Set automatic cleanup timer
            const timeUntilExpiry = expires - Date.now()
            if (timeUntilExpiry > 0) {
                this.cleanupTimer = setTimeout(() => {
                    this.clearToken()
                }, timeUntilExpiry)
            }

            // Log token storage (without exposing token value)
            if (process.env.NODE_ENV === 'development') {
                console.log('[SecureTokenManager] Token stored securely', {
                    hasToken: !!token,
                    expiresAt: new Date(expires).toISOString(),
                    tokenPrefix: token.substring(0, 10) + '...'
                })
            }
        } catch (error) {
            console.error('[SecureTokenManager] Error storing token:', error)
            throw new Error('Failed to store token securely')
        }
    }

    /**
     * Get current token if valid and not expired
     */
    getToken(): string | null {
        try {
            if (!this.tokenData) {
                return null
            }

            // Check if token is expired
            if (Date.now() > this.tokenData.expires) {
                this.clearToken()
                return null
            }

            return this.tokenData.value
        } catch (error) {
            console.error('[SecureTokenManager] Error retrieving token:', error)
            this.clearToken()
            return null
        }
    }

    /**
     * Update token (for token rotation)
     */
    updateToken(newToken: string, expiresAt?: string): void {
        this.setToken(newToken, expiresAt)
    }

    /**
     * Check if token exists and is valid
     */
    hasValidToken(): boolean {
        return this.getToken() !== null
    }

    /**
     * Get token expiration time
     */
    getTokenExpiration(): Date | null {
        if (!this.tokenData) {
            return null
        }
        return new Date(this.tokenData.expires)
    }

    /**
     * Clear token and cleanup resources
     */
    clearToken(): void {
        try {
            // Clear token data
            if (this.tokenData) {
                // Overwrite token value for security
                this.tokenData.value = ''
                this.tokenData = null
            }

            // Clear cleanup timer
            if (this.cleanupTimer) {
                clearTimeout(this.cleanupTimer)
                this.cleanupTimer = null
            }

            if (process.env.NODE_ENV === 'development') {
                console.log('[SecureTokenManager] Token cleared securely')
            }
        } catch (error) {
            console.error('[SecureTokenManager] Error clearing token:', error)
        }
    }

    /**
     * Complete cleanup (called on page unload)
     */
    private cleanup(): void {
        this.clearToken()
    }

    /**
     * Get token info for debugging (without exposing actual token)
     */
    getTokenInfo(): { hasToken: boolean; expiresAt: string | null; isExpired: boolean } {
        const token = this.tokenData
        if (!token) {
            return { hasToken: false, expiresAt: null, isExpired: false }
        }

        const isExpired = Date.now() > token.expires
        return {
            hasToken: true,
            expiresAt: new Date(token.expires).toISOString(),
            isExpired
        }
    }
}

// Export singleton instance
export const secureTokenManager = SecureTokenManager.getInstance()

/**
 * React hook for secure token management
 */
import { useState, useEffect, useCallback } from 'react'

export function useSecureToken(initialToken?: string, expiresAt?: string) {
    const [hasToken, setHasToken] = useState(false)
    const [isExpired, setIsExpired] = useState(false)

    // Initialize token
    useEffect(() => {
        if (initialToken) {
            secureTokenManager.setToken(initialToken, expiresAt)
            setHasToken(true)
        }
    }, [initialToken, expiresAt])

    // Check token status periodically
    useEffect(() => {
        const checkTokenStatus = () => {
            const tokenInfo = secureTokenManager.getTokenInfo()
            setHasToken(tokenInfo.hasToken && !tokenInfo.isExpired)
            setIsExpired(tokenInfo.isExpired)
        }

        // Check immediately
        checkTokenStatus()

        // Check every 30 seconds
        const interval = setInterval(checkTokenStatus, 30000)

        return () => clearInterval(interval)
    }, [])

    const getToken = useCallback(() => {
        return secureTokenManager.getToken()
    }, [])

    const updateToken = useCallback((newToken: string, newExpiresAt?: string) => {
        secureTokenManager.updateToken(newToken, newExpiresAt)
        setHasToken(true)
        setIsExpired(false)
    }, [])

    const clearToken = useCallback(() => {
        secureTokenManager.clearToken()
        setHasToken(false)
        setIsExpired(false)
    }, [])

    return {
        hasToken,
        isExpired,
        getToken,
        updateToken,
        clearToken
    }
}