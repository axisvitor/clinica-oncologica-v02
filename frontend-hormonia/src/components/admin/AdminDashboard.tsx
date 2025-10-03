import React, { useState, useEffect } from 'react'
import { Outlet, Navigate, useLocation } from 'react-router-dom'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line,
  Area,
  AreaChart
} from 'recharts'
import {
  Shield,
  Users,
  Activity,
  AlertTriangle,
  Clock,
  Database,
  Cpu,
  HardDrive,
  Wifi,
  Eye,
  Lock,
  UserX,
  Calendar
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs'
import { Alert, AlertDescription } from '../ui/alert'
import { Button } from '../ui/button'
import { Badge } from '../ui/badge'
import { Progress } from '../ui/progress'
import {
  AdminDashboardStats,
  AdminUserActivity,
  SecurityMetrics,
  AuditLogEntry,
  AdminUser
} from '../../types/admin'
import { useAuth } from '../../contexts/AuthContext'
import AdminNavigationMenu from './AdminNavigationMenu'
import AdminSessionManager from './AdminSessionManager'
import AdminUserActivityMonitor from './AdminUserActivityMonitor'

interface AdminDashboardProps {
  children?: React.ReactNode
}

// Mock data for demonstration
const mockDashboardStats: AdminDashboardStats = {
  users: {
    total: 1247,
    active: 892,
    locked: 15,
    new_today: 23
  },
  security: {
    failed_logins: 47,
    active_sessions: 156,
    blocked_ips: 8
  },
  system: {
    uptime: 99.7,
    memory_usage: 68,
    cpu_usage: 45,
    disk_usage: 72
  },
  audit: {
    total_logs: 15420,
    critical_events: 3,
    warnings: 28
  }
}

const mockSecurityMetrics: SecurityMetrics = {
  total_users: 1247,
  active_sessions: 156,
  failed_logins_24h: 47,
  blocked_ips: 8,
  last_backup: '2024-01-15T10:30:00Z',
  system_uptime: 99.7
}

const mockRecentActivity: AdminUserActivity[] = [
  {
    id: '1',
    user_id: 'user1',
    user_email: 'admin@example.com',
    action: 'login',
    resource: 'admin_panel',
    details: { ip: '192.168.1.100' },
    timestamp: '2024-01-15T14:30:00Z',
    ip_address: '192.168.1.100',
    user_agent: 'Mozilla/5.0...',
    session_id: 'sess1'
  },
  {
    id: '2',
    user_id: 'user2',
    user_email: 'doctor@example.com',
    action: 'password_reset',
    resource: 'user_account',
    details: { target_user: 'patient123' },
    timestamp: '2024-01-15T14:25:00Z',
    ip_address: '192.168.1.101',
    user_agent: 'Mozilla/5.0...',
    session_id: 'sess2'
  }
]

const systemHealthData = [
  { name: 'CPU', value: 45, color: '#10B981' },
  { name: 'Memory', value: 68, color: '#F59E0B' },
  { name: 'Disk', value: 72, color: '#EF4444' },
  { name: 'Network', value: 23, color: '#3B82F6' }
]

const securityTrendData = [
  { date: '2024-01-10', failed_logins: 32, blocked_ips: 5 },
  { date: '2024-01-11', failed_logins: 28, blocked_ips: 3 },
  { date: '2024-01-12', failed_logins: 45, blocked_ips: 7 },
  { date: '2024-01-13', failed_logins: 38, blocked_ips: 4 },
  { date: '2024-01-14', failed_logins: 52, blocked_ips: 9 },
  { date: '2024-01-15', failed_logins: 47, blocked_ips: 8 }
]

const COLORS = ['#10B981', '#F59E0B', '#EF4444', '#3B82F6']

export const AdminDashboard: React.FC<AdminDashboardProps> = ({ children }) => {
  const { user, isAuthenticated, isLoading: authLoading } = useAuth()
  const location = useLocation()
  const [dashboardStats, setDashboardStats] = useState<AdminDashboardStats>(mockDashboardStats)
  const [securityMetrics, setSecurityMetrics] = useState<SecurityMetrics>(mockSecurityMetrics)
  const [recentActivity, setRecentActivity] = useState<AdminUserActivity[]>(mockRecentActivity)
  const [isLoading, setIsLoading] = useState(true)

  // Redirect to login if not authenticated
  if (!isAuthenticated) {
    return <Navigate to="/admin/login" state={{ from: location }} replace />
  }

  // Load dashboard data
  useEffect(() => {
    const loadDashboardData = async () => {
      try {
        setIsLoading(true)
        // TODO: Replace with actual API calls
        await new Promise(resolve => setTimeout(resolve, 1000))
        setDashboardStats(mockDashboardStats)
        setSecurityMetrics(mockSecurityMetrics)
        setRecentActivity(mockRecentActivity)
      } catch (error) {
        console.error('Failed to load dashboard data:', error)
      } finally {
        setIsLoading(false)
      }
    }

    loadDashboardData()
  }, [])

  const formatUptime = (uptime: number): string => {
    return `${uptime.toFixed(1)}%`
  }

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const getSecurityStatusColor = (failedLogins: number): string => {
    if (failedLogins > 50) return 'text-red-600'
    if (failedLogins > 30) return 'text-yellow-600'
    return 'text-green-600'
  }

  // Show only dashboard overview if we're at the root admin path
  const showDashboardOverview = location.pathname === '/admin' || location.pathname === '/admin/'

  if (!showDashboardOverview) {
    return (
      <div className="min-h-screen bg-gray-50">
        <AdminNavigationMenu />
        <main className="ml-64 p-6">
          <AdminSessionManager />
          <Outlet />
        </main>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <AdminNavigationMenu />

      <main className="ml-64 p-6">
        <AdminSessionManager />

        <div className="space-y-6">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Admin Dashboard</h1>
              <p className="text-gray-600">Welcome back, {user?.full_name}</p>
            </div>
            <div className="flex items-center space-x-4">
              <Badge variant="outline" className="flex items-center space-x-1">
                <Clock className="h-3 w-3" />
                <span>Uptime: {formatUptime(securityMetrics.system_uptime)}</span>
              </Badge>
              {user?.role === 'admin' && (
                <Badge variant="secondary">Administrador</Badge>
              )}
            </div>
          </div>

          {/* Critical Alerts */}
          {dashboardStats.audit.critical_events > 0 && (
            <Alert className="border-red-200 bg-red-50">
              <AlertTriangle className="h-4 w-4 text-red-600" />
              <AlertDescription className="text-red-800">
                {dashboardStats.audit.critical_events} critical security event(s) require immediate attention.
                <Button variant="link" className="p-0 h-auto ml-2 text-red-600">
                  View Details
                </Button>
              </AlertDescription>
            </Alert>
          )}

          {/* Key Metrics */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Total Users</CardTitle>
                <Users className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{dashboardStats.users.total.toLocaleString()}</div>
                <p className="text-xs text-muted-foreground">
                  +{dashboardStats.users.new_today} new today
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Active Sessions</CardTitle>
                <Activity className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{dashboardStats.security.active_sessions}</div>
                <p className="text-xs text-muted-foreground">
                  {dashboardStats.users.active} active users
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Security Events</CardTitle>
                <Shield className={`h-4 w-4 ${getSecurityStatusColor(dashboardStats.security.failed_logins)}`} />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{dashboardStats.security.failed_logins}</div>
                <p className="text-xs text-muted-foreground">
                  Failed logins (24h)
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">System Health</CardTitle>
                <Database className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{formatUptime(dashboardStats.system.uptime)}</div>
                <p className="text-xs text-muted-foreground">
                  System uptime
                </p>
              </CardContent>
            </Card>
          </div>

          <Tabs defaultValue="overview" className="space-y-4">
            <TabsList>
              <TabsTrigger value="overview">Overview</TabsTrigger>
              <TabsTrigger value="security">Security</TabsTrigger>
              <TabsTrigger value="system">System Health</TabsTrigger>
              <TabsTrigger value="activity">Recent Activity</TabsTrigger>
            </TabsList>

            <TabsContent value="overview" className="space-y-4">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* User Statistics */}
                <Card>
                  <CardHeader>
                    <CardTitle>User Statistics</CardTitle>
                    <CardDescription>Current user status breakdown</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          <div className="w-3 h-3 bg-green-500 rounded-full"></div>
                          <span className="text-sm">Active Users</span>
                        </div>
                        <span className="font-medium">{dashboardStats.users.active}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          <div className="w-3 h-3 bg-red-500 rounded-full"></div>
                          <span className="text-sm">Locked Accounts</span>
                        </div>
                        <span className="font-medium">{dashboardStats.users.locked}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          <div className="w-3 h-3 bg-blue-500 rounded-full"></div>
                          <span className="text-sm">New Today</span>
                        </div>
                        <span className="font-medium">{dashboardStats.users.new_today}</span>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Security Trends */}
                <Card>
                  <CardHeader>
                    <CardTitle>Security Trends</CardTitle>
                    <CardDescription>Failed logins and blocked IPs over time</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <ResponsiveContainer width="100%" height={200}>
                      <LineChart data={securityTrendData}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis
                          dataKey="date"
                          tickFormatter={(date) => new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                        />
                        <YAxis />
                        <Tooltip
                          labelFormatter={(date) => new Date(date).toLocaleDateString()}
                        />
                        <Line
                          type="monotone"
                          dataKey="failed_logins"
                          stroke="#EF4444"
                          strokeWidth={2}
                          name="Failed Logins"
                        />
                        <Line
                          type="monotone"
                          dataKey="blocked_ips"
                          stroke="#F59E0B"
                          strokeWidth={2}
                          name="Blocked IPs"
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </CardContent>
                </Card>
              </div>
            </TabsContent>

            <TabsContent value="security" className="space-y-4">
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <Card className="lg:col-span-2">
                  <CardHeader>
                    <CardTitle>Security Events</CardTitle>
                    <CardDescription>Recent security-related activities</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-4">
                      {recentActivity.map((activity) => (
                        <div key={activity.id} className="flex items-center justify-between py-2 border-b last:border-0">
                          <div className="flex items-center space-x-3">
                            {activity.action === 'login' ? (
                              <Eye className="h-4 w-4 text-green-600" />
                            ) : activity.action === 'password_reset' ? (
                              <Lock className="h-4 w-4 text-yellow-600" />
                            ) : (
                              <UserX className="h-4 w-4 text-red-600" />
                            )}
                            <div>
                              <p className="text-sm font-medium">{activity.action.replace('_', ' ')}</p>
                              <p className="text-xs text-gray-500">{activity.ip_address}</p>
                            </div>
                          </div>
                          <span className="text-xs text-gray-500">
                            {formatDate(activity.timestamp)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Security Summary</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="text-center">
                      <div className="text-2xl font-bold text-green-600 mb-1">
                        {dashboardStats.security.blocked_ips}
                      </div>
                      <p className="text-sm text-gray-600">Blocked IPs</p>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-yellow-600 mb-1">
                        {dashboardStats.security.failed_logins}
                      </div>
                      <p className="text-sm text-gray-600">Failed Logins (24h)</p>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-blue-600 mb-1">
                        {dashboardStats.users.locked}
                      </div>
                      <p className="text-sm text-gray-600">Locked Accounts</p>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </TabsContent>

            <TabsContent value="system" className="space-y-4">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <Card>
                  <CardHeader>
                    <CardTitle>System Resources</CardTitle>
                    <CardDescription>Current system utilization</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <ResponsiveContainer width="100%" height={250}>
                      <PieChart>
                        <Pie
                          data={systemHealthData}
                          cx="50%"
                          cy="50%"
                          innerRadius={60}
                          outerRadius={80}
                          dataKey="value"
                        >
                          {systemHealthData.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={entry.color} />
                          ))}
                        </Pie>
                        <Tooltip formatter={(value) => `${value}%`} />
                      </PieChart>
                    </ResponsiveContainer>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Resource Details</CardTitle>
                    <CardDescription>Detailed system metrics</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          <Cpu className="h-4 w-4" />
                          <span className="text-sm">CPU Usage</span>
                        </div>
                        <span className="text-sm font-medium">{dashboardStats.system.cpu_usage}%</span>
                      </div>
                      <Progress value={dashboardStats.system.cpu_usage} className="h-2" />
                    </div>

                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          <Database className="h-4 w-4" />
                          <span className="text-sm">Memory Usage</span>
                        </div>
                        <span className="text-sm font-medium">{dashboardStats.system.memory_usage}%</span>
                      </div>
                      <Progress value={dashboardStats.system.memory_usage} className="h-2" />
                    </div>

                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          <HardDrive className="h-4 w-4" />
                          <span className="text-sm">Disk Usage</span>
                        </div>
                        <span className="text-sm font-medium">{dashboardStats.system.disk_usage}%</span>
                      </div>
                      <Progress value={dashboardStats.system.disk_usage} className="h-2" />
                    </div>
                  </CardContent>
                </Card>
              </div>
            </TabsContent>

            <TabsContent value="activity">
              <AdminUserActivityMonitor />
            </TabsContent>
          </Tabs>
        </div>
      </main>
    </div>
  )
}

export default AdminDashboard