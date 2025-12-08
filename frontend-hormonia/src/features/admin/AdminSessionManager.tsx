import React, { useState, useEffect, useCallback } from 'react'
import { Clock, AlertTriangle, RefreshCw, LogOut, Shield } from 'lucide-react'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { SessionWarning } from '@/types/admin'
import { useAuth } from '@/app/providers/AuthContext'
import { createLogger } from '@/lib/logger'

const logger = createLogger('AdminSessionManager')

interface AdminSessionManagerProps {
  className?: string
}

// Session timeout configuration
const SESSION_WARNING_TIME = 5 * 60 * 1000 // 5 minutes before expiry
const SESSION_REFRESH_INTERVAL = 60 * 1000 // Check every minute
const INACTIVITY_TIMEOUT = 30 * 60 * 1000 // 30 minutes of inactivity

export const AdminSessionManager: React.FC<AdminSessionManagerProps> = ({ className }) => {
  const { user, isAuthenticated, logout } = useAuth()
  const [sessionWarning, setSessionWarning] = useState<SessionWarning | null>(null)
  const [lastActivity, setLastActivity] = useState<Date>(new Date())
  const [isExtending, setIsExtending] = useState(false)
  const [showInactivityDialog, setShowInactivityDialog] = useState(false)
  const [inactivityCountdown, setInactivityCountdown] = useState(0)
  const [sessionExpiry] = useState<Date>(() => new Date(Date.now() + 24 * 60 * 60 * 1000)) // 24h session

  // Calculate time remaining until session expires
  const getTimeRemaining = useCallback((): number => {
    if (!sessionExpiry) return 0
    return Math.max(0, sessionExpiry.getTime() - Date.now())
  }, [sessionExpiry])

  // Calculate time since last activity
  const getTimeSinceActivity = useCallback((): number => {
    return Date.now() - lastActivity.getTime()
  }, [lastActivity])

  // Update activity timestamp
  const updateActivity = useCallback(() => {
    setLastActivity(new Date())
    setShowInactivityDialog(false)
  }, [])

  // Handle session extension (Firebase handles token refresh automatically)
  const handleExtendSession = useCallback(async () => {
    setIsExtending(true)
    try {
      // Firebase automatically refreshes tokens, just reset activity tracking
      setSessionWarning(null)
      updateActivity()
    } catch (error) {
      setSessionWarning({
        type: 'expired',
        message: 'Session extension failed. Please login again.',
        action: 'logout'
      })
    } finally {
      setIsExtending(false)
    }
  }, [updateActivity])

  // Handle logout
  const handleLogout = useCallback(async () => {
    try {
      await logout()
    } catch (error: unknown) {
      logger.error('Logout failed', { error })
    }
  }, [logout])

  // Monitor session expiry and inactivity
  useEffect(() => {
    if (!isAuthenticated || !sessionExpiry) return

    const checkSession = () => {
      const timeRemaining = getTimeRemaining()
      const timeSinceActivity = getTimeSinceActivity()

      // Check for session expiry
      if (timeRemaining <= 0) {
        setSessionWarning({
          type: 'expired',
          message: 'Your session has expired. Please login again.',
          action: 'logout'
        })
        return
      }

      // Check for impending session expiry
      if (timeRemaining <= SESSION_WARNING_TIME && !sessionWarning) {
        setSessionWarning({
          type: 'expiring',
          message: 'Your session will expire soon. Would you like to extend it?',
          timeRemaining: Math.floor(timeRemaining / 1000),
          action: 'extend'
        })
        return
      }

      // Check for inactivity
      if (timeSinceActivity >= INACTIVITY_TIMEOUT && !showInactivityDialog) {
        setShowInactivityDialog(true)
        setInactivityCountdown(60) // 60 second countdown
        return
      }

      // Clear warnings if session is healthy
      if (timeRemaining > SESSION_WARNING_TIME && sessionWarning?.type === 'expiring') {
        setSessionWarning(null)
      }
    }

    const interval = setInterval(checkSession, SESSION_REFRESH_INTERVAL)
    return () => clearInterval(interval)
  }, [
    isAuthenticated,
    sessionExpiry,
    sessionWarning,
    showInactivityDialog,
    getTimeRemaining,
    getTimeSinceActivity
  ])

  // Handle inactivity countdown
  useEffect(() => {
    if (!showInactivityDialog || inactivityCountdown <= 0) return

    const timer = setTimeout(() => {
      const newCountdown = inactivityCountdown - 1
      setInactivityCountdown(newCountdown)

      if (newCountdown <= 0) {
        setShowInactivityDialog(false)
        handleLogout()
      }
    }, 1000)

    return () => clearTimeout(timer)
  }, [showInactivityDialog, inactivityCountdown, handleLogout])

  // Track user activity
  useEffect(() => {
    const events = ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart', 'click']

    const activityHandler = () => {
      updateActivity()
    }

    events.forEach(event => {
      document.addEventListener(event, activityHandler, true)
    })

    return () => {
      events.forEach(event => {
        document.removeEventListener(event, activityHandler, true)
      })
    }
  }, [updateActivity])

  // Auto-refresh token when close to expiry (Firebase handles this automatically)
  useEffect(() => {
    if (!isAuthenticated || !sessionExpiry) return

    const timeRemaining = getTimeRemaining()
    const shouldRefresh = timeRemaining <= SESSION_WARNING_TIME && timeRemaining > 0

    if (shouldRefresh && !sessionWarning) {
      // Firebase automatically refreshes tokens
      logger.info('Session auto-refresh handled by Firebase')
    }
  }, [isAuthenticated, sessionExpiry, sessionWarning, getTimeRemaining])

  const formatTime = (milliseconds: number): string => {
    const totalSeconds = Math.floor(milliseconds / 1000)
    const minutes = Math.floor(totalSeconds / 60)
    const seconds = totalSeconds % 60
    return `${minutes}:${seconds.toString().padStart(2, '0')}`
  }

  const getSessionHealthColor = (): string => {
    const timeRemaining = getTimeRemaining()
    const percentage = (timeRemaining / (24 * 60 * 60 * 1000)) * 100 // Assuming 24h session

    if (percentage <= 10) return 'text-red-600'
    if (percentage <= 25) return 'text-yellow-600'
    return 'text-green-600'
  }

  if (!isAuthenticated) {
    return null
  }

  return (
    <>
      {/* Session Status Bar */}
      <div className={`bg-white border-b border-gray-200 px-6 py-3 ${className}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2">
              <Shield className={`h-4 w-4 ${getSessionHealthColor()}`} />
              <span className="text-sm font-medium text-gray-700">Session Status:</span>
              <Badge variant="outline" className={getSessionHealthColor()}>
                Active
              </Badge>
            </div>

            {sessionExpiry && (
              <div className="flex items-center space-x-2 text-sm text-gray-600">
                <Clock className="h-4 w-4" />
                <span>
                  Expires in: {formatTime(getTimeRemaining())}
                </span>
              </div>
            )}
          </div>

          <div className="flex items-center space-x-3">
            <Button
              variant="outline"
              size="sm"
              onClick={handleExtendSession}
              disabled={isExtending}
              className="text-xs"
            >
              {isExtending ? (
                <>
                  <RefreshCw className="h-3 w-3 mr-1 animate-spin" />
                  Extending...
                </>
              ) : (
                <>
                  <RefreshCw className="h-3 w-3 mr-1" />
                  Extend Session
                </>
              )}
            </Button>

            <Button
              variant="ghost"
              size="sm"
              onClick={handleLogout}
              className="text-xs text-gray-600 hover:text-red-600"
            >
              <LogOut className="h-3 w-3 mr-1" />
              Logout
            </Button>
          </div>
        </div>
      </div>

      {/* Session Warning Alert */}
      {sessionWarning && (
        <Alert className={`mx-6 mt-4 ${sessionWarning.type === 'expired'
            ? 'border-red-200 bg-red-50'
            : 'border-yellow-200 bg-yellow-50'
          }`}>
          <AlertTriangle className={`h-4 w-4 ${sessionWarning.type === 'expired' ? 'text-red-600' : 'text-yellow-600'
            }`} />
          <AlertDescription className={
            sessionWarning.type === 'expired' ? 'text-red-800' : 'text-yellow-800'
          }>
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">{sessionWarning.message}</p>
                {sessionWarning.timeRemaining && (
                  <p className="text-sm mt-1">
                    Time remaining: {formatTime(sessionWarning.timeRemaining * 1000)}
                  </p>
                )}
              </div>
              <div className="flex space-x-2">
                {sessionWarning.action === 'extend' && (
                  <Button
                    size="sm"
                    onClick={handleExtendSession}
                    disabled={isExtending}
                  >
                    {isExtending ? 'Extending...' : 'Extend Session'}
                  </Button>
                )}
                {sessionWarning.action === 'logout' && (
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={handleLogout}
                  >
                    Logout Now
                  </Button>
                )}
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setSessionWarning(null)}
                >
                  Dismiss
                </Button>
              </div>
            </div>
          </AlertDescription>
        </Alert>
      )}

      {/* Inactivity Warning Dialog */}
      <Dialog open={showInactivityDialog} onOpenChange={setShowInactivityDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center space-x-2">
              <AlertTriangle className="h-5 w-5 text-yellow-600" />
              <span>Inactivity Detected</span>
            </DialogTitle>
            <DialogDescription>
              You have been inactive for an extended period. Your session will be terminated
              for security reasons unless you take action.
            </DialogDescription>
          </DialogHeader>

          <div className="py-4">
            <div className="text-center space-y-4">
              <div className="text-2xl font-bold text-red-600">
                {inactivityCountdown}
              </div>
              <p className="text-sm text-gray-600">
                seconds remaining before automatic logout
              </p>
              <Progress
                value={((60 - inactivityCountdown) / 60) * 100}
                className="w-full h-2"
              />
            </div>
          </div>

          <DialogFooter className="space-x-2">
            <Button
              variant="outline"
              onClick={handleLogout}
            >
              Logout Now
            </Button>
            <Button
              onClick={() => {
                updateActivity()
                setShowInactivityDialog(false)
              }}
            >
              Stay Logged In
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}

export default AdminSessionManager