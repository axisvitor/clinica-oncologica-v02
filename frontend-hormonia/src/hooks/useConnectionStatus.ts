import { useState, useEffect, useCallback } from 'react'
import { createLogger } from '../lib/logger'

const logger = createLogger('ConnectionStatus')

export interface ConnectionStatus {
  isOnline: boolean
  isSlowConnection: boolean
  lastOnlineAt: Date | null
  connectionType: string
  estimatedBandwidth: number | null
}

export function useConnectionStatus() {
  const [status, setStatus] = useState<ConnectionStatus>({
    isOnline: navigator.onLine,
    isSlowConnection: false,
    lastOnlineAt: navigator.onLine ? new Date() : null,
    connectionType: 'unknown',
    estimatedBandwidth: null
  })

  const updateConnectionInfo = useCallback(() => {
    if ('connection' in navigator) {
      const connection = (navigator as any).connection

      setStatus(prev => ({
        ...prev,
        connectionType: connection.effectiveType || 'unknown',
        estimatedBandwidth: connection.downlink || null,
        isSlowConnection: connection.effectiveType === '2g' || connection.effectiveType === 'slow-2g'
      }))
    }
  }, [])

  const handleOnline = useCallback(() => {
    logger.info('Connection restored')
    setStatus(prev => ({
      ...prev,
      isOnline: true,
      lastOnlineAt: new Date()
    }))
    updateConnectionInfo()
  }, [updateConnectionInfo])

  const handleOffline = useCallback(() => {
    logger.warn('Connection lost')
    setStatus(prev => ({
      ...prev,
      isOnline: false
    }))
  }, [])

  useEffect(() => {
    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    // Listen for connection changes
    if ('connection' in navigator) {
      const connection = (navigator as any).connection
      const handleConnectionChange = () => updateConnectionInfo()

      connection.addEventListener('change', handleConnectionChange)

      // Initial connection info
      updateConnectionInfo()

      return () => {
        window.removeEventListener('online', handleOnline)
        window.removeEventListener('offline', handleOffline)
        connection.removeEventListener('change', handleConnectionChange)
      }
    }

    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [handleOnline, handleOffline, updateConnectionInfo])

  return status
}