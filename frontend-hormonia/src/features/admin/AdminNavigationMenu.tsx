import React, { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard,
  Users,
  Shield,
  Settings,
  FileText,
  Activity,
  AlertTriangle,
  Database,
  Lock,
  LogOut,
  ChevronDown,
  ChevronRight,
  Folder,
  FolderOpen,
  Bell,
  Search,
  User,
  Menu,
  X,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { AdminNavItem } from '@/types/admin'
import { useAuth } from '@/app/providers/AuthContext'
import { createLogger } from '@/lib/logger'
import { apiClient } from '@/lib/api-client'

const logger = createLogger('AdminNavigationMenu')

interface AdminNavigationMenuProps {
  className?: string
}

const adminNavItems: AdminNavItem[] = [
  {
    id: 'dashboard',
    label: 'Dashboard',
    path: '/admin',
    icon: 'LayoutDashboard',
    requiredPermissions: ['admin.read'],
  },
  {
    id: 'users',
    label: 'User Management',
    path: '/admin/users',
    icon: 'Users',
    requiredPermissions: ['users.read'],
    children: [
      {
        id: 'users-list',
        label: 'All Users',
        path: '/admin/users',
        requiredPermissions: ['users.read'],
      },
      {
        id: 'users-locked',
        label: 'Locked Accounts',
        path: '/admin/users/locked',
        requiredPermissions: ['users.read'],
      },
      {
        id: 'users-roles',
        label: 'Roles & Permissions',
        path: '/admin/users/roles',
        requiredPermissions: ['users.roles.read'],
      },
    ],
  },
  {
    id: 'security',
    label: 'Security',
    path: '/admin/security',
    icon: 'Shield',
    requiredPermissions: ['security.read'],
    children: [
      {
        id: 'security-audit',
        label: 'Audit Logs',
        path: '/admin/security/audit',
        requiredPermissions: ['security.audit.read'],
      },
      {
        id: 'security-sessions',
        label: 'Active Sessions',
        path: '/admin/security/sessions',
        requiredPermissions: ['security.sessions.read'],
      },
      {
        id: 'security-blocked',
        label: 'Blocked IPs',
        path: '/admin/security/blocked-ips',
        requiredPermissions: ['security.blocked.read'],
      },
      {
        id: 'security-settings',
        label: 'Security Settings',
        path: '/admin/security/settings',
        requiredPermissions: ['security.settings.write'],
      },
    ],
  },
  {
    id: 'system',
    label: 'System',
    path: '/admin/system',
    icon: 'Database',
    requiredPermissions: ['system.read'],
    children: [
      {
        id: 'system-health',
        label: 'System Health',
        path: '/admin/system/health',
        requiredPermissions: ['system.health.read'],
      },
      {
        id: 'system-logs',
        label: 'System Logs',
        path: '/admin/system/logs',
        requiredPermissions: ['system.logs.read'],
      },
      {
        id: 'system-backup',
        label: 'Backup & Recovery',
        path: '/admin/system/backup',
        requiredPermissions: ['system.backup.read'],
      },
      {
        id: 'system-compensation',
        label: 'Compensation Failures',
        path: '/admin/system/compensation',
        requiredPermissions: ['system.compensation.read'],
      },
    ],
  },
  {
    id: 'templates',
    label: 'Construtores',
    path: '/admin/templates',
    icon: 'Folder',
    requiredPermissions: ['admin.templates.read'],
    children: [
      {
        id: 'templates-flows',
        label: 'Flow Builder',
        path: '/admin/templates/flows',
        requiredPermissions: ['admin.templates.read'],
      },
      {
        id: 'templates-quiz',
        label: 'Quiz Builder',
        path: '/admin/templates/quiz',
        requiredPermissions: ['admin.templates.read'],
      },
    ],
  },
  {
    id: 'reports',
    label: 'Reports',
    path: '/admin/reports',
    icon: 'FileText',
    requiredPermissions: ['reports.read'],
    children: [
      {
        id: 'reports-security',
        label: 'Security Reports',
        path: '/admin/reports/security',
        requiredPermissions: ['reports.security.read'],
      },
      {
        id: 'reports-users',
        label: 'User Activity Reports',
        path: '/admin/reports/users',
        requiredPermissions: ['reports.users.read'],
      },
      {
        id: 'reports-system',
        label: 'System Reports',
        path: '/admin/reports/system',
        requiredPermissions: ['reports.system.read'],
      },
    ],
  },
  {
    id: 'settings',
    label: 'Settings',
    path: '/admin/settings',
    icon: 'Settings',
    requiredPermissions: ['settings.read'],
    children: [
      {
        id: 'settings-general',
        label: 'General Settings',
        path: '/admin/settings/general',
        requiredPermissions: ['settings.general.read'],
      },
      {
        id: 'settings-notifications',
        label: 'Notifications',
        path: '/admin/settings/notifications',
        requiredPermissions: ['settings.notifications.read'],
      },
      {
        id: 'settings-integrations',
        label: 'Integrations',
        path: '/admin/settings/integrations',
        requiredPermissions: ['settings.integrations.read'],
      },
    ],
  },
]

const iconMap = {
  LayoutDashboard,
  Users,
  Shield,
  Settings,
  FileText,
  Activity,
  AlertTriangle,
  Database,
  Lock,
  Folder,
  FolderOpen,
}

export const AdminNavigationMenu: React.FC<AdminNavigationMenuProps> = ({ className }) => {
  const { user, logout, hasPermission } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set())
  const [searchQuery, setSearchQuery] = useState('')
  const [filteredNavItems, setFilteredNavItems] = useState<AdminNavItem[]>(adminNavItems)
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)
  const [criticalAlerts, _setCriticalAlerts] = useState(2) // Mock data
  const canViewCompensation = hasPermission('system.compensation.read')

  const { data: compensationFailures } = useQuery({
    queryKey: ['admin-compensation-failures-count'],
    queryFn: () => apiClient.adminV2.listCompensationFailures(1, 1),
    refetchInterval: 60000,
    enabled: !!user && canViewCompensation,
  })

  const compensationFailureCount = compensationFailures?.total ?? 0

  // Auto-expand current section
  useEffect(() => {
    const currentPath = location.pathname
    const newExpanded = new Set(expandedItems)

    adminNavItems.forEach((item) => {
      if (item.children) {
        const isChildActive = item.children.some((child) => currentPath.startsWith(child.path))
        if (isChildActive || currentPath.startsWith(item.path)) {
          newExpanded.add(item['id'])
        }
      }
    })

    setExpandedItems(newExpanded)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- expandedItems is intentionally excluded to prevent infinite loop
  }, [location.pathname])

  // Filter navigation items based on search
  useEffect(() => {
    if (!searchQuery.trim()) {
      setFilteredNavItems(adminNavItems)
      return
    }

    const query = searchQuery.toLowerCase()
    const filtered = adminNavItems.filter((item) => {
      const matchesLabel = item.label.toLowerCase().includes(query)
      const matchesChildren = item.children?.some((child) =>
        child.label.toLowerCase().includes(query)
      )
      return matchesLabel || matchesChildren
    })

    setFilteredNavItems(filtered)
  }, [searchQuery])

  const checkPermissions = (requiredPermissions?: string[]): boolean => {
    if (!requiredPermissions || !user) return true
    return requiredPermissions.some((permission) => hasPermission(permission))
  }

  const toggleExpanded = (itemId: string) => {
    const newExpanded = new Set(expandedItems)
    if (newExpanded.has(itemId)) {
      newExpanded.delete(itemId)
    } else {
      newExpanded.add(itemId)
    }
    setExpandedItems(newExpanded)
  }

  const handleLogout = async () => {
    try {
      await logout()
      navigate('/admin/login')
    } catch (error) {
      logger.error('Logout failed', { error })
    }
  }

  const isActiveRoute = (path: string): boolean => {
    if (path === '/admin') {
      return location.pathname === '/admin' || location.pathname === '/admin/'
    }
    return location.pathname.startsWith(path)
  }

  const renderNavItem = (item: AdminNavItem, depth: number = 0) => {
    if (!checkPermissions(item.requiredPermissions)) {
      return null
    }

    const isExpanded = expandedItems.has(item['id'])
    const isActive = isActiveRoute(item.path)
    const hasChildren = item.children && item.children.length > 0
    const IconComponent = item.icon ? iconMap[item.icon as keyof typeof iconMap] : null
    const paddingLeft = depth === 0 ? 'pl-6' : `pl-${6 + depth * 4}`

    const shouldShowCompensationBadge =
      item.id === 'system-compensation' && compensationFailureCount > 0

    return (
      <div key={item['id']}>
        {hasChildren ? (
          <button
            onClick={() => toggleExpanded(item['id'])}
            className={`w-full flex items-center justify-between ${paddingLeft} pr-6 py-3 text-left hover:bg-gray-100 transition-colors ${
              isActive ? 'bg-blue-50 border-r-2 border-blue-500' : ''
            }`}
          >
            <div className="flex items-center space-x-3">
              {IconComponent && (
                <IconComponent
                  className={`h-5 w-5 ${isActive ? 'text-blue-600' : 'text-gray-500'}`}
                />
              )}
              <span className={`font-medium ${isActive ? 'text-blue-600' : 'text-gray-700'}`}>
                {item.label}
              </span>
            </div>
            {isExpanded ? (
              <ChevronDown className="h-4 w-4 text-gray-400" />
            ) : (
              <ChevronRight className="h-4 w-4 text-gray-400" />
            )}
          </button>
        ) : (
          <Link
            to={item.path}
            onClick={() => setIsMobileMenuOpen(false)}
            className={`flex items-center justify-between ${paddingLeft} pr-6 py-3 hover:bg-gray-100 transition-colors ${
              isActive ? 'bg-blue-50 border-r-2 border-blue-500' : ''
            }`}
          >
            <div className="flex items-center">
              {IconComponent && (
                <IconComponent
                  className={`h-5 w-5 mr-3 ${isActive ? 'text-blue-600' : 'text-gray-500'}`}
                />
              )}
              <span className={`font-medium ${isActive ? 'text-blue-600' : 'text-gray-700'}`}>
                {item.label}
              </span>
            </div>
            {shouldShowCompensationBadge && (
              <Badge
                variant="destructive"
                className="ml-2"
                data-testid="compensation-failures-badge"
              >
                {compensationFailureCount}
              </Badge>
            )}
          </Link>
        )}

        {hasChildren && isExpanded && (
          <div className="bg-gray-50">
            {item.children?.map((child) => renderNavItem(child, depth + 1))}
          </div>
        )}
      </div>
    )
  }

  if (!user) {
    return null
  }

  return (
    <>
      {/* Mobile menu button */}
      <Button
        variant="ghost"
        size="sm"
        className="lg:hidden fixed top-4 left-4 z-50"
        onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
      >
        {isMobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
      </Button>

      {/* Sidebar */}
      <aside
        className={`
        fixed inset-y-0 left-0 z-40 w-64 bg-white border-r border-gray-200 transform transition-transform duration-300 ease-in-out
        ${isMobileMenuOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
        ${className}
      `}
      >
        <div className="flex flex-col h-full">
          {/* Header */}
          <div className="flex items-center justify-between p-6 border-b border-gray-200">
            <div className="flex items-center space-x-3">
              <Shield className="h-8 w-8 text-blue-600" />
              <div>
                <h1 className="text-lg font-bold text-gray-900">Admin Panel</h1>
                <p className="text-xs text-gray-500">
                  {user['role'] === 'admin' ? 'Administrador' : 'Médico'}
                </p>
              </div>
            </div>
          </div>

          {/* Search */}
          <div className="p-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
              <Input
                type="text"
                placeholder="Search menu..."
                value={searchQuery}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                  setSearchQuery(e.target.value)
                }
                className="pl-10"
              />
            </div>
          </div>

          {/* Critical Alerts */}
          {criticalAlerts > 0 && (
            <div className="mx-4 mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
              <div className="flex items-center space-x-2">
                <AlertTriangle className="h-4 w-4 text-red-600" />
                <span className="text-sm font-medium text-red-800">
                  {criticalAlerts} Critical Alert{criticalAlerts !== 1 ? 's' : ''}
                </span>
              </div>
              <Link
                to="/admin/security/audit"
                className="text-xs text-red-600 hover:text-red-700 underline"
              >
                View Details
              </Link>
            </div>
          )}

          {/* Navigation */}
          <nav className="flex-1 overflow-y-auto">
            <div className="space-y-1">{filteredNavItems.map((item) => renderNavItem(item))}</div>
          </nav>

          {/* User Profile & Settings */}
          <div className="border-t border-gray-200 p-4">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" className="w-full justify-start p-2">
                  <div className="flex items-center space-x-3">
                    <Avatar className="h-8 w-8">
                      <AvatarImage src="" alt={user['full_name']} />
                      <AvatarFallback>
                        {typeof user['full_name'] === 'string'
                          ? user['full_name']
                              .split(' ')
                              .map((n: string) => n[0])
                              .join('')
                              .toUpperCase()
                          : ''}
                      </AvatarFallback>
                    </Avatar>
                    <div className="flex-1 text-left">
                      <p className="text-sm font-medium text-gray-700">{user['full_name']}</p>
                      <p className="text-xs text-gray-500">{user['email']}</p>
                    </div>
                  </div>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuLabel>My Account</DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem asChild>
                  <Link to="/admin/profile" className="flex items-center">
                    <User className="mr-2 h-4 w-4" />
                    Profile Settings
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <Link to="/admin/security/my-sessions" className="flex items-center">
                    <Lock className="mr-2 h-4 w-4" />
                    My Sessions
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <Link to="/admin/notifications" className="flex items-center">
                    <Bell className="mr-2 h-4 w-4" />
                    Notifications
                    {criticalAlerts > 0 && (
                      <Badge variant="destructive" className="ml-auto">
                        {criticalAlerts}
                      </Badge>
                    )}
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={handleLogout} className="text-red-600">
                  <LogOut className="mr-2 h-4 w-4" />
                  Sign Out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </aside>

      {/* Mobile overlay */}
      {isMobileMenuOpen && (
        <div
          className="fixed inset-0 z-30 bg-black bg-opacity-50 lg:hidden"
          onClick={() => setIsMobileMenuOpen(false)}
        />
      )}
    </>
  )
}

export default AdminNavigationMenu
