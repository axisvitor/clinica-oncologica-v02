import React, { useState, useEffect, useCallback } from 'react'
import { format } from 'date-fns'
import {
  Eye,
  Lock,
  UserX,
  Shield,
  RefreshCw,
  Filter,
  Download,
  Search,
  Calendar,
  MapPin,
  Monitor,
  AlertTriangle,
  CheckCircle,
  XCircle
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card'
import { Button } from '../ui/button'
import { Input } from '../ui/input'
import { Badge } from '../ui/badge'
import { Label } from '../ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../ui/select'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '../ui/dialog'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../ui/table'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '../ui/dropdown-menu'
import { DatePickerWithRange } from '../ui/date-range-picker'
import { Pagination } from '../ui/pagination'
import {
  AdminUserActivity,
  AdminActivityFilter,
  AdminPaginatedResponse
} from '../../types/admin'
import { createLogger } from '../../lib/logger'

const logger = createLogger({ component: 'AdminUserActivityMonitor' })

interface AdminUserActivityMonitorProps {
  className?: string
}

// Mock data for demonstration
const mockActivityData: AdminUserActivity[] = [
  {
    id: '1',
    user_id: 'user1',
    user_email: 'admin@example.com',
    action: 'login',
    resource: 'admin_panel',
    details: {
      ip: '192.168.1.100',
      browser: 'Chrome 120.0',
      location: 'São Paulo, BR'
    },
    timestamp: '2024-01-15T14:30:00Z',
    ip_address: '192.168.1.100',
    user_agent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    session_id: 'sess1'
  },
  {
    id: '2',
    user_id: 'user2',
    user_email: 'doctor@example.com',
    action: 'password_reset',
    resource: 'user_account',
    details: {
      target_user: 'patient123',
      reason: 'Forgot password',
      ip: '192.168.1.101'
    },
    timestamp: '2024-01-15T14:25:00Z',
    ip_address: '192.168.1.101',
    user_agent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
    session_id: 'sess2'
  },
  {
    id: '3',
    user_id: 'user1',
    user_email: 'admin@example.com',
    action: 'user_view',
    resource: 'patient_record',
    details: {
      patient_id: 'pt456',
      view_type: 'medical_history',
      duration: 120
    },
    timestamp: '2024-01-15T14:20:00Z',
    ip_address: '192.168.1.100',
    user_agent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    session_id: 'sess1'
  },
  {
    id: '4',
    user_id: 'user3',
    user_email: 'nurse@example.com',
    action: 'failed_login',
    resource: 'admin_panel',
    details: {
      failure_reason: 'Invalid password',
      attempt_number: 3,
      ip: '203.0.113.45'
    },
    timestamp: '2024-01-15T14:15:00Z',
    ip_address: '203.0.113.45',
    user_agent: 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
    session_id: 'failed_sess'
  },
  {
    id: '5',
    user_id: 'user2',
    user_email: 'doctor@example.com',
    action: 'settings_update',
    resource: 'system_settings',
    details: {
      setting: 'session_timeout',
      old_value: '30',
      new_value: '60'
    },
    timestamp: '2024-01-15T14:10:00Z',
    ip_address: '192.168.1.101',
    user_agent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
    session_id: 'sess2'
  }
]

const actionIcons = {
  login: { icon: Eye, color: 'text-green-600', bgColor: 'bg-green-100' },
  logout: { icon: UserX, color: 'text-gray-600', bgColor: 'bg-gray-100' },
  failed_login: { icon: XCircle, color: 'text-red-600', bgColor: 'bg-red-100' },
  password_reset: { icon: Lock, color: 'text-yellow-600', bgColor: 'bg-yellow-100' },
  user_view: { icon: Eye, color: 'text-blue-600', bgColor: 'bg-blue-100' },
  settings_update: { icon: Shield, color: 'text-purple-600', bgColor: 'bg-purple-100' },
  data_export: { icon: Download, color: 'text-indigo-600', bgColor: 'bg-indigo-100' },
  default: { icon: CheckCircle, color: 'text-gray-600', bgColor: 'bg-gray-100' }
}

export const AdminUserActivityMonitor: React.FC<AdminUserActivityMonitorProps> = ({ className }) => {
  const [activities, setActivities] = useState<AdminUserActivity[]>(mockActivityData)
  const [filteredActivities, setFilteredActivities] = useState<AdminUserActivity[]>(mockActivityData)
  const [filters, setFilters] = useState<AdminActivityFilter>({})
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedActivity, setSelectedActivity] = useState<AdminUserActivity | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [currentPage, setCurrentPage] = useState(1)
  const [itemsPerPage] = useState(10)
  const [dateRange, setDateRange] = useState<{ from?: Date; to?: Date }>({})

  // Load activities from API
  const loadActivities = useCallback(async () => {
    setIsLoading(true)
    try {
      // TODO: Replace with actual API call
      await new Promise(resolve => setTimeout(resolve, 1000))
      setActivities(mockActivityData)
    } catch (error) {
      logger.error('Failed to load activities', { error })
    } finally {
      setIsLoading(false)
    }
  }, [])

  // Apply filters to activities
  useEffect(() => {
    let filtered = [...activities]

    // Text search
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase()
      filtered = filtered.filter(activity =>
        activity.action.toLowerCase().includes(query) ||
        activity.resource.toLowerCase().includes(query) ||
        activity.ip_address.includes(query) ||
        activity.user_id.toLowerCase().includes(query) ||
        JSON.stringify(activity.details).toLowerCase().includes(query)
      )
    }

    // Filter by user ID
    if (filters.userId) {
      filtered = filtered.filter(activity => activity.user_id === filters.userId)
    }

    // Filter by action
    if (filters.action) {
      filtered = filtered.filter(activity => activity.action === filters.action)
    }

    // Filter by resource
    if (filters.resource) {
      filtered = filtered.filter(activity => activity.resource === filters.resource)
    }

    // Filter by IP address
    if (filters.ipAddress) {
      filtered = filtered.filter(activity => activity.ip_address.includes(filters.ipAddress!))
    }

    // Filter by date range
    if (dateRange.from || dateRange.to) {
      filtered = filtered.filter(activity => {
        const activityDate = new Date(activity.timestamp)
        if (dateRange.from && activityDate < dateRange.from) return false
        if (dateRange.to && activityDate > dateRange.to) return false
        return true
      })
    }

    setFilteredActivities(filtered)
    setCurrentPage(1)
  }, [activities, filters, searchQuery, dateRange])

  // Get paginated activities
  const paginatedActivities = filteredActivities.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  )

  const totalPages = Math.ceil(filteredActivities.length / itemsPerPage)

  // Export activities to CSV
  const exportToCSV = () => {
    const headers = [
      'Timestamp',
      'User ID',
      'Action',
      'Resource',
      'IP Address',
      'User Agent',
      'Details'
    ]

    const csvData = filteredActivities.map(activity => [
      format(new Date(activity.timestamp), 'yyyy-MM-dd HH:mm:ss'),
      activity.user_id,
      activity.action,
      activity.resource,
      activity.ip_address,
      activity.user_agent,
      JSON.stringify(activity.details)
    ])

    const csvContent = [headers, ...csvData]
      .map(row => row.map(cell => `"${cell}"`).join(','))
      .join('\n')

    const blob = new Blob([csvContent], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `admin-activity-${format(new Date(), 'yyyy-MM-dd')}.csv`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }

  const getActionDisplay = (action: string) => {
    const config = actionIcons[action as keyof typeof actionIcons] || actionIcons.default
    const Icon = config.icon

    return {
      icon: <Icon className={`h-4 w-4 ${config.color}`} />,
      badge: (
        <Badge variant="outline" className={`${config.color} ${config.bgColor} border-current`}>
          {action.replace('_', ' ')}
        </Badge>
      )
    }
  }

  const formatUserAgent = (userAgent: string): string => {
    // Simple user agent parsing for display
    if (userAgent.includes('Chrome')) return 'Chrome'
    if (userAgent.includes('Firefox')) return 'Firefox'
    if (userAgent.includes('Safari') && !userAgent.includes('Chrome')) return 'Safari'
    if (userAgent.includes('Edge')) return 'Edge'
    return 'Other'
  }

  const getRiskLevel = (activity: AdminUserActivity): 'low' | 'medium' | 'high' => {
    if (activity.action === 'failed_login') return 'high'
    if (activity.action === 'password_reset' || activity.action === 'settings_update') return 'medium'
    return 'low'
  }

  const clearFilters = () => {
    setFilters({})
    setSearchQuery('')
    setDateRange({})
  }

  useEffect(() => {
    loadActivities()
  }, [loadActivities])

  return (
    <div className={`space-y-6 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">User Activity Monitor</h2>
          <p className="text-gray-600">Track and monitor all administrative actions</p>
        </div>
        <div className="flex items-center space-x-3">
          <Button variant="outline" onClick={exportToCSV}>
            <Download className="h-4 w-4 mr-2" />
            Export CSV
          </Button>
          <Button onClick={loadActivities} disabled={isLoading}>
            <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Filters</CardTitle>
          <CardDescription>Filter activities by various criteria</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Search */}
            <div className="space-y-2">
              <Label htmlFor="search">Search</Label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <Input
                  id="search"
                  placeholder="Search activities..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>

            {/* Action Filter */}
            <div className="space-y-2">
              <Label>Action</Label>
              <Select
                value={filters.action || ''}
                onValueChange={(value: string) => {
                  const newFilters: AdminActivityFilter = { ...filters }
                  if (value) {
                    newFilters.action = value
                  } else {
                    delete newFilters.action
                  }
                  setFilters(newFilters)
                }}
              >
                <SelectTrigger>
                  <SelectValue placeholder="All actions" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">All actions</SelectItem>
                  <SelectItem value="login">Login</SelectItem>
                  <SelectItem value="logout">Logout</SelectItem>
                  <SelectItem value="failed_login">Failed Login</SelectItem>
                  <SelectItem value="password_reset">Password Reset</SelectItem>
                  <SelectItem value="user_view">User View</SelectItem>
                  <SelectItem value="settings_update">Settings Update</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Resource Filter */}
            <div className="space-y-2">
              <Label>Resource</Label>
              <Select
                value={filters.resource || ''}
                onValueChange={(value: string) => {
                  const newFilters: AdminActivityFilter = { ...filters }
                  if (value) {
                    newFilters.resource = value
                  } else {
                    delete newFilters.resource
                  }
                  setFilters(newFilters)
                }}
              >
                <SelectTrigger>
                  <SelectValue placeholder="All resources" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">All resources</SelectItem>
                  <SelectItem value="admin_panel">Admin Panel</SelectItem>
                  <SelectItem value="user_account">User Account</SelectItem>
                  <SelectItem value="patient_record">Patient Record</SelectItem>
                  <SelectItem value="system_settings">System Settings</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* IP Address Filter */}
            <div className="space-y-2">
              <Label htmlFor="ip">IP Address</Label>
              <Input
                id="ip"
                placeholder="192.168.1.1"
                value={filters.ipAddress || ''}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => {
                  const newFilters: AdminActivityFilter = { ...filters }
                  if (e.target.value) {
                    newFilters.ipAddress = e.target.value
                  } else {
                    delete newFilters.ipAddress
                  }
                  setFilters(newFilters)
                }}
              />
            </div>
          </div>

          <div className="flex items-center justify-between mt-4">
            <div className="flex items-center space-x-2">
              <Calendar className="h-4 w-4 text-gray-500" />
              <DatePickerWithRange
                {...(dateRange.from ? { from: dateRange.from } : {})}
                {...(dateRange.to ? { to: dateRange.to } : {})}
                onSelect={(range) => {
                  if (range) {
                    const newRange: { from?: Date; to?: Date } = {}
                    if (range.from) newRange.from = range.from
                    if (range.to) newRange.to = range.to
                    setDateRange(newRange)
                  } else {
                    setDateRange({})
                  }
                }}
              />
            </div>
            <Button variant="outline" onClick={clearFilters}>
              Clear Filters
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Results Summary */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            <div className="text-sm text-gray-600">
              Showing {paginatedActivities.length} of {filteredActivities.length} activities
              {filteredActivities.length !== activities.length && (
                <span> (filtered from {activities.length} total)</span>
              )}
            </div>
            <div className="flex items-center space-x-4 text-sm">
              <div className="flex items-center space-x-1">
                <div className="w-3 h-3 bg-red-100 rounded-full border border-red-600"></div>
                <span className="text-gray-600">High Risk</span>
              </div>
              <div className="flex items-center space-x-1">
                <div className="w-3 h-3 bg-yellow-100 rounded-full border border-yellow-600"></div>
                <span className="text-gray-600">Medium Risk</span>
              </div>
              <div className="flex items-center space-x-1">
                <div className="w-3 h-3 bg-green-100 rounded-full border border-green-600"></div>
                <span className="text-gray-600">Low Risk</span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Activities Table */}
      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Activity</TableHead>
                <TableHead>User</TableHead>
                <TableHead>Resource</TableHead>
                <TableHead>Location</TableHead>
                <TableHead>Risk</TableHead>
                <TableHead>Timestamp</TableHead>
                <TableHead className="w-[50px]"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center py-8">
                    <div className="flex items-center justify-center">
                      <RefreshCw className="h-4 w-4 animate-spin mr-2" />
                      Loading activities...
                    </div>
                  </TableCell>
                </TableRow>
              ) : paginatedActivities.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center py-8 text-gray-500">
                    No activities found matching your criteria
                  </TableCell>
                </TableRow>
              ) : (
                paginatedActivities.map((activity) => {
                  const actionDisplay = getActionDisplay(activity.action)
                  const riskLevel = getRiskLevel(activity)

                  return (
                    <TableRow key={activity.id} className="hover:bg-gray-50">
                      <TableCell>
                        <div className="flex items-center space-x-3">
                          {actionDisplay.icon}
                          <div>
                            {actionDisplay.badge}
                            <p className="text-xs text-gray-500 mt-1">
                              Session: {activity.session_id.substring(0, 8)}...
                            </p>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center space-x-2">
                          <Badge variant="secondary">{activity.user_id}</Badge>
                        </div>
                      </TableCell>
                      <TableCell>
                        <span className="font-medium">{activity.resource}</span>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center space-x-2">
                          <MapPin className="h-3 w-3 text-gray-400" />
                          <span className="text-sm">{activity.ip_address}</span>
                        </div>
                        <div className="flex items-center space-x-2 mt-1">
                          <Monitor className="h-3 w-3 text-gray-400" />
                          <span className="text-xs text-gray-500">
                            {formatUserAgent(activity.user_agent)}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={riskLevel === 'high' ? 'destructive' :
                                  riskLevel === 'medium' ? 'outline' : 'secondary'}
                          className={
                            riskLevel === 'medium' ? 'border-yellow-500 text-yellow-700' : ''
                          }
                        >
                          {riskLevel} risk
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="text-sm">
                          {format(new Date(activity.timestamp), 'MMM dd, HH:mm')}
                        </div>
                        <div className="text-xs text-gray-500">
                          {format(new Date(activity.timestamp), 'yyyy')}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Dialog>
                          <DialogTrigger asChild>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setSelectedActivity(activity)}
                            >
                              <Eye className="h-4 w-4" />
                            </Button>
                          </DialogTrigger>
                          <DialogContent className="max-w-2xl">
                            <DialogHeader>
                              <DialogTitle>Activity Details</DialogTitle>
                              <DialogDescription>
                                Detailed information about this activity
                              </DialogDescription>
                            </DialogHeader>
                            {selectedActivity && (
                              <div className="space-y-4">
                                <div className="grid grid-cols-2 gap-4">
                                  <div>
                                    <Label className="text-sm font-medium">Action</Label>
                                    <p className="text-sm">{selectedActivity.action}</p>
                                  </div>
                                  <div>
                                    <Label className="text-sm font-medium">Resource</Label>
                                    <p className="text-sm">{selectedActivity.resource}</p>
                                  </div>
                                  <div>
                                    <Label className="text-sm font-medium">User ID</Label>
                                    <p className="text-sm">{selectedActivity.user_id}</p>
                                  </div>
                                  <div>
                                    <Label className="text-sm font-medium">Session ID</Label>
                                    <p className="text-sm">{selectedActivity.session_id}</p>
                                  </div>
                                  <div>
                                    <Label className="text-sm font-medium">IP Address</Label>
                                    <p className="text-sm">{selectedActivity.ip_address}</p>
                                  </div>
                                  <div>
                                    <Label className="text-sm font-medium">Timestamp</Label>
                                    <p className="text-sm">
                                      {format(new Date(selectedActivity.timestamp), 'PPpp')}
                                    </p>
                                  </div>
                                </div>
                                <div>
                                  <Label className="text-sm font-medium">User Agent</Label>
                                  <p className="text-sm bg-gray-50 p-2 rounded">
                                    {selectedActivity.user_agent}
                                  </p>
                                </div>
                                <div>
                                  <Label className="text-sm font-medium">Details</Label>
                                  <pre className="text-sm bg-gray-50 p-2 rounded overflow-auto">
                                    {JSON.stringify(selectedActivity.details, null, 2)}
                                  </pre>
                                </div>
                              </div>
                            )}
                          </DialogContent>
                        </Dialog>
                      </TableCell>
                    </TableRow>
                  )
                })
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center">
          <Pagination
            currentPage={currentPage}
            totalPages={totalPages}
            onPageChange={setCurrentPage}
          />
        </div>
      )}
    </div>
  )
}

export default AdminUserActivityMonitor