import React, { memo } from 'react'
import { WifiOff, Wifi, AlertTriangle } from 'lucide-react'
import { Alert, AlertDescription } from '../ui/alert'
import { Badge } from '../ui/badge'
import { useConnectionStatus } from '../../hooks/useConnectionStatus'

export const ConnectionMonitor = memo(() => {
  const { isOnline, isSlowConnection, connectionType, estimatedBandwidth } = useConnectionStatus()

  if (isOnline && !isSlowConnection) {
    return null // Don't show anything when connection is good
  }

  return (
    <div className="fixed top-4 right-4 z-50 max-w-sm">
      {!isOnline && (
        <Alert className="border-red-500 bg-red-50">
          <WifiOff className="h-4 w-4 text-red-600" />
          <AlertDescription className="text-red-800">
            <div className="space-y-1">
              <p className="font-medium">Sem conexão com a internet</p>
              <p className="text-sm">Algumas funcionalidades podem estar indisponíveis.</p>
            </div>
          </AlertDescription>
        </Alert>
      )}

      {isOnline && isSlowConnection && (
        <Alert className="border-yellow-500 bg-yellow-50">
          <AlertTriangle className="h-4 w-4 text-yellow-600" />
          <AlertDescription className="text-yellow-800">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Conexão lenta detectada</p>
                <p className="text-sm">Dados podem demorar para carregar.</p>
              </div>
              <div className="flex flex-col items-end space-y-1">
                <Badge variant="outline" className="text-xs">
                  {connectionType.toUpperCase()}
                </Badge>
                {estimatedBandwidth && (
                  <span className="text-xs">
                    {estimatedBandwidth.toFixed(1)} Mbps
                  </span>
                )}
              </div>
            </div>
          </AlertDescription>
        </Alert>
      )}
    </div>
  )
})

ConnectionMonitor.displayName = 'ConnectionMonitor'

export default ConnectionMonitor