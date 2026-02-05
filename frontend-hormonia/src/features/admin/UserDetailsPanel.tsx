import React, { useState } from 'react'
import { formatDistanceToNow } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import { useQuery } from '@tanstack/react-query'
import {
  X,
  Edit,
  Shield,
  Activity,
  Lock,
  Unlock,
  AlertTriangle,
  CheckCircle,
  XCircle,
  FileText
} from 'lucide-react'
import { apiClient } from '@/lib/api-client'
import { AdminUser, AdminUserActivity } from '@/types/admin'
import { getRoleLabel, getRoleColor } from '@/types/shared'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Separator } from '@/components/ui/separator'
import { ScrollArea } from '@/components/ui/scroll-area'
import { LoadingSpinner } from '@/components/ui/loading-spinner'
import { PermissionGuard } from './PermissionGuard'

interface UserDetailsPanelProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  user: AdminUser | null
  onEdit?: (user: AdminUser) => void
  onAssignRole?: (user: AdminUser) => void
}

export function UserDetailsPanel({
  open,
  onOpenChange,
  user,
  onEdit,
  onAssignRole
}: UserDetailsPanelProps) {
  const [selectedTab, setSelectedTab] = useState('overview')

  // Fetch user activity
  const { data: userActivity, isLoading: activityLoading } = useQuery({
    queryKey: ['admin-user-activity', user?.id],
    queryFn: () => user ? apiClient.adminUsers.getActivity(user['id'], { page: 1, size: 50 }) : null,
    enabled: !!user && open,
  })

  if (!user) return null

  const getInitials = (name: string) => {
    return name
      .split(' ')
      .map(n => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2)
  }

  const getRoleBadge = (role: string) => {
    const colorClasses = getRoleColor(role)
    const label = getRoleLabel(role)
    return <Badge className={colorClasses}>{label}</Badge>
  }

  const getStatusBadge = (user: AdminUser) => {
    if (user.locked_until && new Date(user.locked_until) > new Date()) {
      return <Badge variant="destructive">Bloqueado</Badge>
    }
    if (!user.is_active) {
      return <Badge variant="secondary">Inativo</Badge>
    }
    return <Badge className="bg-green-100 text-green-800">Ativo</Badge>
  }

  const formatDate = (dateString: string) => {
    try {
      return new Date(dateString).toLocaleString('pt-BR')
    } catch {
      return 'Data inválida'
    }
  }

  const formatRelativeTime = (dateString?: string | null) => {
    if (!dateString) return 'Nunca'

    try {
      return formatDistanceToNow(new Date(dateString), {
        addSuffix: true,
        locale: ptBR
      })
    } catch {
      return 'Data inválida'
    }
  }

  const getActivityIcon = (action: string) => {
    const iconProps = { className: "h-4 w-4" }

    switch (action.toLowerCase()) {
      case 'login':
        return <CheckCircle {...iconProps} className="h-4 w-4 text-green-600" />
      case 'logout':
        return <XCircle {...iconProps} className="h-4 w-4 text-gray-600" />
      case 'failed_login':
        return <AlertTriangle {...iconProps} className="h-4 w-4 text-red-600" />
      case 'password_change':
        return <Lock {...iconProps} className="h-4 w-4 text-blue-600" />
      case 'permission_change':
        return <Shield {...iconProps} className="h-4 w-4 text-purple-600" />
      default:
        return <Activity {...iconProps} />
    }
  }

  const getActivityDescription = (activity: AdminUserActivity) => {
    switch (activity.action.toLowerCase()) {
      case 'login':
        return 'Login realizado com sucesso'
      case 'logout':
        return 'Logout realizado'
      case 'failed_login':
        return 'Tentativa de login falhada'
      case 'password_change':
        return 'Senha alterada'
      case 'permission_change':
        return 'Permissões alteradas'
      case 'create_user':
        return 'Usuário criado'
      case 'update_user':
        return 'Usuário atualizado'
      case 'delete_user':
        return 'Usuário excluído'
      case 'create_patient':
        return 'Paciente criado'
      case 'update_patient':
        return 'Paciente atualizado'
      default:
        return activity.action.replace('_', ' ')
    }
  }

  const isUserLocked = user.locked_until && new Date(user.locked_until) > new Date()

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-[600px] sm:w-[700px] overflow-hidden">
        <SheetHeader className="space-y-4">
          <div className="flex items-center justify-between">
            <SheetTitle>Detalhes do Usuário</SheetTitle>
            <Button variant="ghost" size="sm" onClick={() => onOpenChange(false)}>
              <X className="h-4 w-4" />
            </Button>
          </div>
          <SheetDescription>
            Informações completas e histórico de atividades
          </SheetDescription>
        </SheetHeader>

        <div className="mt-6 space-y-6">
          {/* User Header */}
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-start justify-between">
                <div className="flex items-center space-x-4">
                  <Avatar className="h-16 w-16">
                    <AvatarFallback className="bg-blue-600 text-white text-lg">
                      {getInitials(user['full_name'] || '')}
                    </AvatarFallback>
                  </Avatar>
                  <div className="space-y-2">
                    <h3 className="text-xl font-semibold">{user['full_name']}</h3>
                    <p className="text-gray-600">{user['email']}</p>
                    <div className="flex items-center gap-2">
                      {getRoleBadge(user['role'])}
                      {getStatusBadge(user)}
                      {user.two_factor_enabled && (
                        <Badge className="bg-green-100 text-green-800">
                          <Shield className="h-3 w-3 mr-1" />
                          2FA
                        </Badge>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex gap-2">
                  <PermissionGuard permissions={['admin.users.update']}>
                    <Button variant="outline" size="sm" onClick={() => onEdit?.(user)}>
                      <Edit className="h-4 w-4 mr-2" />
                      Editar
                    </Button>
                  </PermissionGuard>
                  <PermissionGuard permissions={['admin.users.permissions']}>
                    <Button variant="outline" size="sm" onClick={() => onAssignRole?.(user)}>
                      <Shield className="h-4 w-4 mr-2" />
                      Permissões
                    </Button>
                  </PermissionGuard>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Status Alerts */}
          {isUserLocked && (
            <Card className="border-red-200 bg-red-50">
              <CardContent className="pt-6">
                <div className="flex items-center gap-2 text-red-800">
                  <AlertTriangle className="h-5 w-5" />
                  <span className="font-medium">Usuário Bloqueado</span>
                </div>
                <p className="text-sm text-red-600 mt-1">
                  Este usuário está temporariamente bloqueado até {formatDate(user.locked_until!)}
                </p>
              </CardContent>
            </Card>
          )}

          {user.failed_login_attempts > 0 && (
            <Card className="border-orange-200 bg-orange-50">
              <CardContent className="pt-6">
                <div className="flex items-center gap-2 text-orange-800">
                  <AlertTriangle className="h-5 w-5" />
                  <span className="font-medium">Tentativas de Login Falhadas</span>
                </div>
                <p className="text-sm text-orange-600 mt-1">
                  {user.failed_login_attempts} tentativa(s) de login falhada(s) recente(s)
                </p>
              </CardContent>
            </Card>
          )}

          {/* Tabs */}
          <Tabs value={selectedTab} onValueChange={setSelectedTab} className="space-y-4">
            <TabsList className="grid w-full grid-cols-4">
              <TabsTrigger value="overview">Visão Geral</TabsTrigger>
              <TabsTrigger value="permissions">Permissões</TabsTrigger>
              <TabsTrigger value="activity">Atividade</TabsTrigger>
              <TabsTrigger value="security">Segurança</TabsTrigger>
            </TabsList>

            <ScrollArea className="h-[500px] pr-4">
              <TabsContent value="overview" className="space-y-4">
                {/* Basic Information */}
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Informações Básicas</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <p className="text-sm text-gray-600">ID do Usuário</p>
                        <p className="font-mono text-sm">{user['id']}</p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-600">Email</p>
                        <p className="text-sm">{user['email']}</p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-600">Nome Completo</p>
                        <p className="text-sm">{user['full_name']}</p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-600">Função</p>
                        {getRoleBadge(user['role'])}
                      </div>
                      <div>
                        <p className="text-sm text-gray-600">Data de Criação</p>
                        <p className="text-sm">{formatDate(user.created_at)}</p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-600">Último Login</p>
                        <p className="text-sm">{formatRelativeTime(user.last_login)}</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Quick Stats */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <Card>
                    <CardContent className="pt-6">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-sm text-gray-600">Status</p>
                          {getStatusBadge(user)}
                        </div>
                        <div className="h-8 w-8 bg-blue-100 rounded-full flex items-center justify-center">
                          {user.is_active ? (
                            <CheckCircle className="h-4 w-4 text-green-600" />
                          ) : (
                            <XCircle className="h-4 w-4 text-gray-600" />
                          )}
                        </div>
                      </div>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardContent className="pt-6">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-sm text-gray-600">2FA</p>
                          <Badge variant={user.two_factor_enabled ? "default" : "secondary"}>
                            {user.two_factor_enabled ? 'Ativo' : 'Inativo'}
                          </Badge>
                        </div>
                        <div className="h-8 w-8 bg-purple-100 rounded-full flex items-center justify-center">
                          <Shield className="h-4 w-4 text-purple-600" />
                        </div>
                      </div>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardContent className="pt-6">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-sm text-gray-600">Permissões</p>
                          <Badge variant="outline">
                            {user.permissions.length}
                          </Badge>
                        </div>
                        <div className="h-8 w-8 bg-green-100 rounded-full flex items-center justify-center">
                          <FileText className="h-4 w-4 text-green-600" />
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </TabsContent>

              <TabsContent value="permissions" className="space-y-4">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Permissões Atribuídas</CardTitle>
                    <CardDescription>
                      Lista de todas as permissões específicas do usuário
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {user.permissions.length > 0 ? (
                      <div className="flex flex-wrap gap-2">
                        {user.permissions.map((permission) => (
                          <Badge key={permission} variant="outline" className="text-xs">
                            {permission}
                          </Badge>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-gray-500">
                        Nenhuma permissão específica atribuída. As permissões são herdadas da função do usuário.
                      </p>
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Função e Nível de Acesso</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">Função Atual:</span>
                      {getRoleBadge(user['role'])}
                    </div>

                    <Separator />

                    <div className="space-y-2">
                      <p className="text-sm font-medium">Descrição da Função:</p>
                      <p className="text-sm text-gray-600">
                        {user['role'] === 'admin' && 'Acesso administrativo completo ao sistema, incluindo gerenciamento de usuários e configurações.'}
                        {user['role'] === 'doctor' && 'Acesso a dados de pacientes, histórico médico e funcionalidades clínicas.'}
                      </p>
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="activity" className="space-y-4">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Histórico de Atividades</CardTitle>
                    <CardDescription>
                      Últimas ações realizadas pelo usuário
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {activityLoading ? (
                      <div className="flex items-center justify-center py-8">
                        <LoadingSpinner size="lg" />
                      </div>
                    ) : userActivity?.items && userActivity.items.length > 0 ? (
                      <div className="space-y-4">
                        {userActivity.items.map((activity: AdminUserActivity) => (
                          <div key={activity.id} className="flex items-start space-x-3 p-3 border rounded-lg">
                            <div className="mt-1">
                              {getActivityIcon(activity.action)}
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center justify-between">
                                <p className="text-sm font-medium text-gray-900">
                                  {getActivityDescription(activity)}
                                </p>
                                <p className="text-xs text-gray-500">
                                  {formatRelativeTime(activity.timestamp)}
                                </p>
                              </div>
                              <p className="text-xs text-gray-600 mt-1">
                                {activity.resource && `Recurso: ${activity.resource}`}
                                {activity.ip_address && ` • IP: ${activity.ip_address}`}
                              </p>
                              {activity.details && Object.keys(activity.details).length > 0 && (
                                <details className="mt-2">
                                  <summary className="text-xs text-blue-600 cursor-pointer">
                                    Ver detalhes
                                  </summary>
                                  <pre className="text-xs text-gray-600 mt-1 bg-gray-50 p-2 rounded overflow-x-auto">
                                    {JSON.stringify(activity.details, null, 2)}
                                  </pre>
                                </details>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-gray-500 text-center py-8">
                        Nenhuma atividade registrada
                      </p>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="security" className="space-y-4">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Informações de Segurança</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <p className="text-sm font-medium">Autenticação de Dois Fatores</p>
                        <Badge variant={user.two_factor_enabled ? "default" : "secondary"}>
                          <Shield className="h-3 w-3 mr-1" />
                          {user.two_factor_enabled ? 'Ativo' : 'Inativo'}
                        </Badge>
                      </div>

                      <div className="space-y-2">
                        <p className="text-sm font-medium">Tentativas de Login Falhadas</p>
                        <Badge variant={user.failed_login_attempts > 0 ? "destructive" : "secondary"}>
                          {user.failed_login_attempts} tentativa(s)
                        </Badge>
                      </div>

                      <div className="space-y-2">
                        <p className="text-sm font-medium">Status da Conta</p>
                        {isUserLocked ? (
                          <Badge variant="destructive">
                            <Lock className="h-3 w-3 mr-1" />
                            Bloqueada
                          </Badge>
                        ) : (
                          <Badge variant="default">
                            <Unlock className="h-3 w-3 mr-1" />
                            Desbloqueada
                          </Badge>
                        )}
                      </div>

                      <div className="space-y-2">
                        <p className="text-sm font-medium">Último Login</p>
                        <p className="text-sm text-gray-600">
                          {formatRelativeTime(user.last_login)}
                        </p>
                      </div>
                    </div>

                    {isUserLocked && (
                      <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
                        <div className="flex items-center gap-2 text-red-800 mb-2">
                          <AlertTriangle className="h-4 w-4" />
                          <span className="font-medium">Conta Bloqueada</span>
                        </div>
                        <p className="text-sm text-red-600">
                          Esta conta está bloqueada até {formatDate(user.locked_until!)} devido a múltiplas tentativas de login falhadas.
                        </p>
                      </div>
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Configurações de Segurança</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="flex justify-between items-center">
                      <span className="text-sm">Conta Ativa</span>
                      <Badge variant={user.is_active ? "default" : "secondary"}>
                        {user.is_active ? 'Sim' : 'Não'}
                      </Badge>
                    </div>

                    <div className="flex justify-between items-center">
                      <span className="text-sm">2FA Habilitado</span>
                      <Badge variant={user.two_factor_enabled ? "default" : "secondary"}>
                        {user.two_factor_enabled ? 'Sim' : 'Não'}
                      </Badge>
                    </div>

                    <div className="flex justify-between items-center">
                      <span className="text-sm">Nível de Permissão</span>
                      {getRoleBadge(user['role'])}
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>
            </ScrollArea>
          </Tabs>
        </div>
      </SheetContent>
    </Sheet>
  )
}
