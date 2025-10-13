import React from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../ui/card'
import { Badge } from '../../ui/badge'
import { Button } from '../../ui/button'
import {
  Activity,
  Eye,
  Calendar,
  User,
  Clock,
  AlertTriangle,
  CheckCircle,
  XCircle
} from 'lucide-react'
import { AdminDashboardStats, AuditLogEntry } from '../../../types/admin'

interface RecentActivityListProps {
  stats: AdminDashboardStats
  className?: string
}

// Mock recent activities - in real app this would come from props or API
const mockRecentActivities: AuditLogEntry[] = [
  {
    id: '1',
    user_id: 'user-1',
    user_email: 'admin@example.com',
    action: 'user_login',
    resource: 'auth',
    details: { ip_address: '192.168.1.100', user_agent: 'Chrome/91.0' },
    timestamp: new Date(Date.now() - 5 * 60 * 1000).toISOString(), // 5 min ago
    ip_address: '192.168.1.100',
    user_agent: 'Chrome/91.0',
    session_id: 'session-1'
  },
  {
    id: '2',
    user_id: 'user-2',
    user_email: 'doctor@example.com',
    action: 'patient_access',
    resource: 'patients',
    details: { patient_id: 'patient-123', action: 'view_profile' },
    timestamp: new Date(Date.now() - 15 * 60 * 1000).toISOString(), // 15 min ago
    ip_address: '192.168.1.101',
    user_agent: 'Firefox/89.0',
    session_id: 'session-2'
  },
  {
    id: '3',
    user_id: 'user-3',
    user_email: 'nurse@example.com',
    action: 'failed_login',
    resource: 'auth',
    details: { reason: 'invalid_password', attempts: 3 },
    timestamp: new Date(Date.now() - 30 * 60 * 1000).toISOString(), // 30 min ago
    ip_address: '192.168.1.102',
    user_agent: 'Safari/14.0',
    session_id: null
  },
  {
    id: '4',
    user_id: 'user-1',
    user_email: 'admin@example.com',
    action: 'user_created',
    resource: 'users',
    details: { new_user_id: 'user-4', role: 'medico' },
    timestamp: new Date(Date.now() - 45 * 60 * 1000).toISOString(), // 45 min ago
    ip_address: '192.168.1.100',
    user_agent: 'Chrome/91.0',
    session_id: 'session-1'
  },
  {
    id: '5',
    user_id: 'user-2',
    user_email: 'doctor@example.com',
    action: 'template_updated',
    resource: 'templates',
    details: { template_id: 'template-1', template_type: 'flow' },
    timestamp: new Date(Date.now() - 60 * 60 * 1000).toISOString(), // 1 hour ago
    ip_address: '192.168.1.101',
    user_agent: 'Firefox/89.0',
    session_id: 'session-2'
  }
]

export const RecentActivityList: React.FC<RecentActivityListProps> = ({ 
  stats, 
  className = '' 
}) => {
  const formatTimeAgo = (timestamp: string): string => {
    const now = new Date()
    const time = new Date(timestamp)
    const diffInMinutes = Math.floor((now.getTime() - time.getTime()) / (1000 * 60))
    
    if (diffInMinutes < 1) return 'Just now'
    if (diffInMinutes < 60) return `${diffInMinutes}m ago`
    
    const diffInHours = Math.floor(diffInMinutes / 60)
    if (diffInHours < 24) return `${diffInHours}h ago`
    
    const diffInDays = Math.floor(diffInHours / 24)
    return `${diffInDays}d ago`
  }

  const getActionIcon = (action: string) => {
    switch (action) {
      case 'user_login': return CheckCircle
      case 'failed_login': return XCircle
      case 'user_created': return User
      case 'patient_access': return Eye
      case 'template_updated': return Activity
      default: return Activity
    }
  }

  const getActionColor = (action: string) => {
    switch (action) {
      case 'user_login': return 'text-green-600'
      case 'failed_login': return 'text-red-600'
      case 'user_created': return 'text-blue-600'
      case 'patient_access': return 'text-purple-600'
      case 'template_updated': return 'text-orange-600'
      default: return 'text-gray-600'
    }
  }

  const getActionBadge = (action: string) => {
    switch (action) {
      case 'user_login': return { variant: 'default', label: 'Login' }
      case 'failed_login': return { variant: 'destructive', label: 'Failed Login' }
      case 'user_created': return { variant: 'secondary', label: 'User Created' }
      case 'patient_access': return { variant: 'outline', label: 'Patient Access' }
      case 'template_updated': return { variant: 'secondary', label: 'Template Updated' }
      default: return { variant: 'outline', label: 'Activity' }
    }
  }

  const getActionDescription = (activity: AuditLogEntry): string => {
    switch (activity.action) {
      case 'user_login':
        return `Logged in from ${activity.ip_address}`
      case 'failed_login':
        return `Failed login attempt (${activity.details?.attempts || 1} attempts)`
      case 'user_created':
        return `Created new ${activity.details?.role || 'user'} account`
      case 'patient_access':
        return `Accessed patient profile (${activity.details?.action || 'view'})`
      case 'template_updated':
        return `Updated ${activity.details?.template_type || 'template'}`
      default:
        return 'Performed an action'
    }
  }

  return (
    <div className={className}>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Recent Activity
          </CardTitle>
          <CardDescription>
            Latest user actions and system events
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {mockRecentActivities.map((activity) => {
              const IconComponent = getActionIcon(activity.action)
              const iconColor = getActionColor(activity.action)
              const badge = getActionBadge(activity.action)
              
              return (
                <div key={activity.id} className="flex items-start space-x-4 p-3 rounded-lg border bg-card hover:bg-accent/50 transition-colors">
                  <div className={`mt-1 ${iconColor}`}>
                    <IconComponent className="h-4 w-4" />
                  </div>
                  
                  <div className="flex-1 space-y-1">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">
                          {activity.user_email}
                        </span>
                        <Badge variant={badge.variant as any} className="text-xs">
                          {badge.label}
                        </Badge>
                      </div>
                      <div className="flex items-center gap-1 text-xs text-muted-foreground">
                        <Clock className="h-3 w-3" />
                        {formatTimeAgo(activity.timestamp)}
                      </div>
                    </div>
                    
                    <p className="text-sm text-muted-foreground">
                      {getActionDescription(activity)}
                    </p>
                    
                    {activity.details && Object.keys(activity.details).length > 0 && (
                      <div className="text-xs text-muted-foreground">
                        <span className="font-medium">Details:</span>{' '}
                        {Object.entries(activity.details)
                          .map(([key, value]) => `${key}: ${value}`)
                          .join(', ')}
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
          
          <div className="mt-6 pt-4 border-t">
            <div className="flex items-center justify-between">
              <div className="text-sm text-muted-foreground">
                Showing {mockRecentActivities.length} recent activities
              </div>
              <Button variant="outline" size="sm">
                <Eye className="h-4 w-4 mr-2" />
                View All Activity
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Activity Summary */}
      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Calendar className="h-5 w-5" />
            Activity Summary
          </CardTitle>
          <CardDescription>
            Today's activity overview
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">
                {mockRecentActivities.filter(a => a.action === 'user_login').length}
              </div>
              <div className="text-xs text-muted-foreground">Successful Logins</div>
            </div>
            
            <div className="text-center">
              <div className="text-2xl font-bold text-red-600">
                {mockRecentActivities.filter(a => a.action === 'failed_login').length}
              </div>
              <div className="text-xs text-muted-foreground">Failed Logins</div>
            </div>
            
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600">
                {mockRecentActivities.filter(a => a.action === 'user_created').length}
              </div>
              <div className="text-xs text-muted-foreground">Users Created</div>
            </div>
            
            <div className="text-center">
              <div className="text-2xl font-bold text-purple-600">
                {mockRecentActivities.filter(a => a.action === 'patient_access').length}
              </div>
              <div className="text-xs text-muted-foreground">Patient Access</div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export default RecentActivityList