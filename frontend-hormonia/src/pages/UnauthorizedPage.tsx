import React from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { AlertTriangle, Home, ArrowLeft, Shield } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { useAuth } from '@/app/providers/AuthContext'
import { getRoleLabel, getRolePermissions } from '@/types/shared'

/**
 * Unauthorized Page
 *
 * Shown when user tries to access a route they don't have permission for
 */
export default function UnauthorizedPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, logout } = useAuth()

  const userRole = user?.role || ''
  const permissions = getRolePermissions(userRole)
  const roleLabel = getRoleLabel(userRole)

  // Get attempted route from state (if available)
  const attemptedRoute = location.state?.from?.pathname || 'página solicitada'

  const handleGoBack = () => {
    navigate(-1)
  }

  const handleGoHome = () => {
    navigate('/dashboard')
  }

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800 flex items-center justify-center p-4">
      <Card className="max-w-2xl w-full shadow-lg">
        <CardHeader className="text-center space-y-4">
          <div className="mx-auto w-16 h-16 bg-red-100 dark:bg-red-900/20 rounded-full flex items-center justify-center">
            <Shield className="w-8 h-8 text-red-600 dark:text-red-400" />
          </div>

          <CardTitle className="text-3xl font-bold">Acesso Negado</CardTitle>

          <CardDescription className="text-base">
            Você não tem permissão para acessar {attemptedRoute}
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-6">
          {/* Alert with user info */}
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>Permissão Insuficiente</AlertTitle>
            <AlertDescription>
              Sua role atual (<strong>{roleLabel}</strong>) não tem acesso a este recurso.
              {user && (
                <span className="block mt-2 text-sm">
                  Entre em contato com um administrador para solicitar acesso.
                </span>
              )}
            </AlertDescription>
          </Alert>

          {/* User permissions info */}
          {user && (
            <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-4 space-y-3">
              <h3 className="font-semibold text-sm text-gray-700 dark:text-gray-300">
                Suas Permissões Atuais:
              </h3>

              <div className="grid grid-cols-1 gap-2 text-sm">
                <PermissionItem label="Gerenciar Usuários" allowed={permissions.canManageUsers} />
                <PermissionItem
                  label="Gerenciar Pacientes"
                  allowed={permissions.canManagePatients}
                />
                <PermissionItem
                  label="Visualizar Relatórios"
                  allowed={permissions.canViewReports}
                />
                <PermissionItem label="Configurar Flows" allowed={permissions.canManageFlows} />
                <PermissionItem
                  label="Painel Administrativo"
                  allowed={permissions.canAccessAdmin}
                />
                <PermissionItem
                  label="Configurações do Sistema"
                  allowed={permissions.canManageSettings}
                />
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex flex-col sm:flex-row gap-3 pt-4">
            <Button variant="outline" className="flex-1" onClick={handleGoBack}>
              <ArrowLeft className="w-4 h-4 mr-2" />
              Voltar
            </Button>

            <Button variant="default" className="flex-1" onClick={handleGoHome}>
              <Home className="w-4 h-4 mr-2" />
              Ir para Dashboard
            </Button>
          </div>

          {/* Logout option */}
          <div className="text-center pt-4 border-t">
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
              Precisa acessar com uma conta diferente?
            </p>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleLogout}
              className="text-red-600 hover:text-red-700 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-900/20"
            >
              Fazer Logout
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

/**
 * Permission item component for displaying permission status
 */
function PermissionItem({ label, allowed }: { label: string; allowed: boolean }) {
  return (
    <div className="flex items-center justify-between py-1 px-2 rounded bg-white dark:bg-gray-700/50">
      <span className="text-gray-700 dark:text-gray-300">{label}</span>
      <span
        className={`text-xs font-medium px-2 py-1 rounded ${
          allowed
            ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
            : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
        }`}
      >
        {allowed ? '✓ Permitido' : '✗ Negado'}
      </span>
    </div>
  )
}
