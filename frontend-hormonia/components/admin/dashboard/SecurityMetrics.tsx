import React from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../ui/card'
import { Badge } from '../../ui/badge'
import { Alert, AlertDescription } from '../../ui/alert'
import {
  Shield,
  Users,
  AlertTriangle,
  Eye,
  Lock,
  UserX,
  Wifi
} from 'lucide-react'
import { AdminDashboardStats } from '../../../types/admin'

interface SecurityMetricsProps {
  stats: AdminDashboardStats
  className?: string
}

export const SecurityMetrics: React.FC<SecurityMetricsProps> = ({ 
  stats, 
  className = '' 
}) => {
  const securityMetrics = [
    {
      title: 'Active Users',
      value: stats.activeUsers,
      total: stats.totalUsers,
      icon: Users,
      description: 'Currently active users',
      status: 'normal',
      percentage: ((stats.activeUsers / stats.totalUsers) * 100).toFixed(1)
    },
    {
      title: 'Failed Logins',
      value: stats.failedLogins,
      icon: Lock,
      description: 'Failed login attempts today',
      status: stats.failedLogins > 10 ? 'warning' : 'normal'
    },
    {
      title: 'Active Sessions',
      value: stats.activeSessions,
      icon: Wifi,
      description: 'Current user sessions',
      status: 'normal'
    },
    {
      title: 'Blocked IPs',
      value: stats.blockedIPs,
      icon: Shield,
      description: 'IP addresses blocked',
      status: stats.blockedIPs > 0 ? 'warning' : 'normal'
    },
    {
      title: 'Locked Users',
      value: stats.lockedUsers,
      icon: UserX,
      description: 'Accounts currently locked',
      status: stats.lockedUsers > 0 ? 'critical' : 'normal'
    },
    {
      title: 'Critical Events',
      value: stats.criticalEvents,
      icon: AlertTriangle,
      description: 'Critical security events',
      status: stats.criticalEvents > 0 ? 'critical' : 'normal'
    }
  ]

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'critical': return 'text-red-600'
      case 'warning': return 'text-yellow-600'
      default: return 'text-green-600'
    }
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'critical': return 'destructive'
      case 'warning': return 'secondary'
      default: return 'default'
    }
  }

  const criticalAlerts = securityMetrics.filter(metric => metric.status === 'critical')
  const warningAlerts = securityMetrics.filter(metric => metric.status === 'warning')

  return (
    <div className={className}>
      {/* Security Alerts */}
      {(criticalAlerts.length > 0 || warningAlerts.length > 0) && (
        <div className="mb-6 space-y-4">
          {criticalAlerts.map((alert, index) => (
            <Alert key={`critical-${index}`} variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>
                <strong>Critical:</strong> {alert.value} {alert.description.toLowerCase()}
              </AlertDescription>
            </Alert>
          ))}
          
          {warningAlerts.map((alert, index) => (
            <Alert key={`warning-${index}`}>
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>
                <strong>Warning:</strong> {alert.value} {alert.description.toLowerCase()}
              </AlertDescription>
            </Alert>
          ))}
        </div>
      )}

      {/* Security Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {securityMetrics.map((metric, index) => {
          const IconComponent = metric.icon
          const statusColor = getStatusColor(metric.status)
          
          return (
            <Card key={index} className="relative overflow-hidden">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">
                  {metric.title}
                </CardTitle>
                <IconComponent className={`h-4 w-4 ${statusColor}`} />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold mb-1">
                  {metric.value}
                  {metric.total && (
                    <span className="text-sm font-normal text-muted-foreground ml-1">
                      / {metric.total}
                    </span>
                  )}
                </div>
                
                <p className="text-xs text-muted-foreground mb-2">
                  {metric.description}
                </p>
                
                {metric.percentage && (
                  <p className="text-xs text-muted-foreground mb-2">
                    {metric.percentage}% of total users
                  </p>
                )}
                
                <Badge variant={getStatusBadge(metric.status) as any}>
                  {metric.status === 'critical' ? 'Critical' : 
                   metric.status === 'warning' ? 'Warning' : 'Normal'}
                </Badge>
              </CardContent>
            </Card>
          )
        })}
      </div>

      {/* Security Summary */}
      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5" />
            Security Summary
          </CardTitle>
          <CardDescription>
            Overall security status and recommendations
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Security Score</span>
              <Badge variant={
                criticalAlerts.length > 0 ? 'destructive' :
                warningAlerts.length > 0 ? 'secondary' : 'default'
              }>
                {criticalAlerts.length > 0 ? 'Critical Issues' :
                 warningAlerts.length > 0 ? 'Needs Attention' : 'Good'}
              </Badge>
            </div>
            
            <div className="text-sm text-muted-foreground">
              {criticalAlerts.length === 0 && warningAlerts.length === 0 ? (
                'All security metrics are within normal parameters.'
              ) : (
                `${criticalAlerts.length} critical and ${warningAlerts.length} warning issues detected.`
              )}
            </div>
            
            {(criticalAlerts.length > 0 || warningAlerts.length > 0) && (
              <div className="pt-2">
                <p className="text-sm font-medium mb-2">Recommendations:</p>
                <ul className="text-sm text-muted-foreground space-y-1">
                  {stats.lockedUsers > 0 && (
                    <li>• Review and unlock legitimate user accounts</li>
                  )}
                  {stats.failedLogins > 10 && (
                    <li>• Investigate suspicious login attempts</li>
                  )}
                  {stats.blockedIPs > 0 && (
                    <li>• Review blocked IP addresses for false positives</li>
                  )}
                  {stats.criticalEvents > 0 && (
                    <li>• Investigate critical security events immediately</li>
                  )}
                </ul>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export default SecurityMetrics