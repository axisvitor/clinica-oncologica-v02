import React from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { LayoutDashboard, Users, MessageSquare, FileText, TriangleAlert as AlertTriangle, Settings, ChartBar as BarChart3, ClipboardList, Shield, Calendar, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuth } from '@/contexts/AuthContext'
import { Button } from '@/components/ui/button'

const navigation = [
  { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { name: 'Pacientes', href: '/patients', icon: Users },
  { name: 'Mensagens', href: '/messages', icon: MessageSquare },
  { name: 'Questionários', href: '/quiz', icon: ClipboardList },
  { name: 'Quiz Mensal', href: '/monthly-quiz', icon: Calendar },
  { name: 'Relatórios', href: '/reports', icon: FileText },
  { name: 'Alertas', href: '/alerts', icon: AlertTriangle },
  { name: 'Analytics', href: '/analytics', icon: BarChart3 },
  { name: 'Configurações', href: '/settings', icon: Settings }
]

const adminNavigation = [
  { name: 'Administração', href: '/admin', icon: Shield, requiredRole: 'admin' }
]

interface SidebarProps {
  isOpen: boolean
  onClose: () => void
}

export function Sidebar({ isOpen, onClose }: SidebarProps) {
  const location = useLocation()
  const { user, hasRole } = useAuth()

  // Combine regular navigation with admin navigation (filtered by role)
  const allNavigation = [
    ...navigation,
    ...adminNavigation.filter(item =>
      !item.requiredRole || hasRole(item.requiredRole)
    )
  ]

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <div
        className={cn(
          "flex flex-col w-64 bg-white border-r border-gray-200 fixed lg:static inset-y-0 left-0 z-50 transform transition-transform duration-300 ease-in-out",
          isOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        )}
      >
        {/* Logo */}
        <div className="flex items-center justify-between h-16 px-4 md:px-6 border-b border-gray-200">
          <div className="flex-1" />
          <img
            src="/images/logo_system.svg"
            alt="Neoplasias Litoral Logo"
            className="h-14 w-auto"
          />
          <div className="flex-1 flex justify-end">
            {/* Close button (mobile only) */}
            <Button
              variant="ghost"
              size="sm"
              className="lg:hidden"
              onClick={onClose}
            >
              <X className="h-5 w-5" />
            </Button>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 md:px-4 py-4 md:py-6 space-y-1 overflow-y-auto">
          {allNavigation.map((item) => {
            const isActive = location.pathname === item.href ||
                            (item.href !== '/dashboard' && location.pathname.startsWith(item.href))

            return (
              <NavLink
                key={item['name']}
                to={item.href}
                onClick={() => onClose()}
                className={cn(
                  'flex items-center px-3 py-2 text-sm font-medium rounded-lg transition-colors',
                  isActive
                    ? 'bg-blue-50 text-blue-700 border-r-2 border-blue-700'
                    : 'text-gray-700 hover:bg-gray-50 hover:text-gray-900'
                )}
              >
                <item.icon className={cn(
                  'mr-3 h-5 w-5',
                  isActive ? 'text-blue-700' : 'text-gray-400'
                )} />
                {item['name']}
              </NavLink>
            )
          })}
        </nav>

        {/* Footer */}
        <div className="p-3 md:p-4 border-t border-gray-200">
          <div className="text-xs text-gray-500 text-center">
            <p>Neoplasias Litoral</p>
            <p>v1.0.0</p>
            {user && (
              <p className="mt-1 text-xs text-blue-600 truncate px-2">
                {user['full_name']} ({user['role']})
              </p>
            )}
          </div>
        </div>
      </div>
    </>
  )
}
