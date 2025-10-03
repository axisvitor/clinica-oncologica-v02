import React from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import {
  LayoutDashboard,
  Users,
  MessageSquare,
  FileText,
  AlertTriangle,
  Settings,
  BarChart3,
  ClipboardList,
  Shield,
  Calendar
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuth } from '@/contexts/AuthContext'

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

export function Sidebar() {
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
    <div className="flex flex-col w-64 bg-white border-r border-gray-200">
      {/* Logo */}
      <div className="flex items-center h-16 px-6 border-b border-gray-200">
        <div className="flex items-center space-x-3">
          <img
            src="/images/sistema-logo.webp"
            alt="Neoplasias Litoral Logo"
            className="h-10 w-auto"
          />
          <div>
            <h1 className="text-lg font-semibold text-gray-900">Neoplasias Litoral</h1>
            <p className="text-xs text-gray-500">Clínica de Oncologia</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-4 py-6 space-y-1">
        {allNavigation.map((item) => {
          const isActive = location.pathname === item.href ||
                          (item.href !== '/dashboard' && location.pathname.startsWith(item.href))

          return (
            <NavLink
              key={item['name']}
              to={item.href}
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
      <div className="p-4 border-t border-gray-200">
        <div className="text-xs text-gray-500 text-center">
          <p>Neoplasias Litoral</p>
          <p>v1.0.0</p>
          {user && (
            <p className="mt-1 text-xs text-blue-600">
              {user['full_name']} ({user['role']})
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
