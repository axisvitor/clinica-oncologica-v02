import React from 'react'
import { formatDistanceToNow } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import {
  Activity,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Lock,
  Shield,
  User,
  FileText,
  Settings,
  Eye,
  Edit,
  Trash2,
  LogIn,
  LogOut,
  Clock
} from 'lucide-react'
import { AdminUserActivity } from '@/types/admin'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'

interface UserActivityTimelineProps {
  activities: AdminUserActivity[]
  isLoading?: boolean
  showUserInfo?: boolean
  maxHeight?: string
  compact?: boolean
}

export function UserActivityTimeline({
  activities,
  isLoading = false,
  showUserInfo = false,
  maxHeight = "400px",
  compact = false
}: UserActivityTimelineProps) {
  const getActivityIcon = (action: string) => {
    const iconProps = { className: "h-4 w-4" }

    switch (action.toLowerCase()) {
      case 'login':
      case 'signin':
        return <LogIn {...iconProps} className="h-4 w-4 text-green-600" />
      case 'logout':
      case 'signout':
        return <LogOut {...iconProps} className="h-4 w-4 text-gray-600" />
      case 'failed_login':
      case 'login_failed':
        return <AlertTriangle {...iconProps} className="h-4 w-4 text-red-600" />
      case 'password_change':
      case 'password_reset':
        return <Lock {...iconProps} className="h-4 w-4 text-blue-600" />
      case 'permission_change':
      case 'role_change':
        return <Shield {...iconProps} className="h-4 w-4 text-purple-600" />
      case 'create_user':
      case 'user_created':
        return <User {...iconProps} className="h-4 w-4 text-green-600" />
      case 'update_user':
      case 'user_updated':
        return <Edit {...iconProps} className="h-4 w-4 text-blue-600" />
      case 'delete_user':
      case 'user_deleted':
        return <Trash2 {...iconProps} className="h-4 w-4 text-red-600" />
      case 'view_patient':
      case 'access_patient':
        return <Eye {...iconProps} className="h-4 w-4 text-gray-600" />
      case 'create_patient':
      case 'patient_created':
        return <User {...iconProps} className="h-4 w-4 text-green-600" />
      case 'update_patient':
      case 'patient_updated':
        return <Edit {...iconProps} className="h-4 w-4 text-blue-600" />
      case 'delete_patient':
      case 'patient_deleted':
        return <Trash2 {...iconProps} className="h-4 w-4 text-red-600" />
      case 'settings_change':
      case 'config_update':
        return <Settings {...iconProps} className="h-4 w-4 text-orange-600" />
      case 'report_generated':
      case 'export_data':
        return <FileText {...iconProps} className="h-4 w-4 text-blue-600" />
      case 'audit_access':
      case 'security_event':
        return <Shield {...iconProps} className="h-4 w-4 text-red-600" />
      default:
        return <Activity {...iconProps} className="h-4 w-4 text-gray-600" />
    }
  }

  const getActivityColor = (action: string) => {
    switch (action.toLowerCase()) {
      case 'login':
      case 'signin':
      case 'create_user':
      case 'create_patient':
      case 'user_created':
      case 'patient_created':
        return 'bg-green-100 border-green-200'
      case 'failed_login':
      case 'login_failed':
      case 'delete_user':
      case 'delete_patient':
      case 'user_deleted':
      case 'patient_deleted':
      case 'audit_access':
      case 'security_event':
        return 'bg-red-100 border-red-200'
      case 'password_change':
      case 'password_reset':
      case 'update_user':
      case 'update_patient':
      case 'user_updated':
      case 'patient_updated':
      case 'report_generated':
      case 'export_data':
        return 'bg-blue-100 border-blue-200'
      case 'permission_change':
      case 'role_change':
        return 'bg-purple-100 border-purple-200'
      case 'settings_change':
      case 'config_update':
        return 'bg-orange-100 border-orange-200'
      default:
        return 'bg-gray-100 border-gray-200'
    }
  }

  const getActivityDescription = (activity: AdminUserActivity) => {
    const baseDescription = (() => {
      switch (activity.action.toLowerCase()) {
        case 'login':
        case 'signin':
          return 'Fez login no sistema'
        case 'logout':
        case 'signout':
          return 'Fez logout do sistema'
        case 'failed_login':
        case 'login_failed':
          return 'Tentativa de login falhada'
        case 'password_change':
          return 'Alterou a senha'
        case 'password_reset':
          return 'Redefiniu a senha'
        case 'permission_change':
          return 'Permissões foram alteradas'
        case 'role_change':
          return 'Função foi alterada'
        case 'create_user':
        case 'user_created':
          return 'Criou um novo usuário'
        case 'update_user':
        case 'user_updated':
          return 'Atualizou informações de usuário'
        case 'delete_user':
        case 'user_deleted':
          return 'Excluiu um usuário'
        case 'view_patient':
        case 'access_patient':
          return 'Acessou dados de paciente'
        case 'create_patient':
        case 'patient_created':
          return 'Criou um novo paciente'
        case 'update_patient':
        case 'patient_updated':
          return 'Atualizou informações de paciente'
        case 'delete_patient':
        case 'patient_deleted':
          return 'Excluiu um paciente'
        case 'settings_change':
        case 'config_update':
          return 'Modificou configurações do sistema'
        case 'report_generated':
          return 'Gerou um relatório'
        case 'export_data':
          return 'Exportou dados'
        case 'audit_access':
          return 'Acessou logs de auditoria'
        case 'security_event':
          return 'Evento de segurança registrado'
        default:
          return activity.action.replace('_', ' ')
      }
    })()

    // Add resource context if available
    if (activity.resource_id && activity.resource) {
      return `${baseDescription} (${activity.resource}: ${activity.resource_id})`
    } else if (activity.resource) {
      return `${baseDescription} - ${activity.resource}`
    }

    return baseDescription
  }

  const getSeverityBadge = (action: string) => {
    switch (action.toLowerCase()) {
      case 'failed_login':
      case 'login_failed':
      case 'delete_user':
      case 'delete_patient':
      case 'security_event':
        return <Badge variant="destructive" className="text-xs">Alto</Badge>
      case 'permission_change':
      case 'role_change':
      case 'password_reset':
      case 'audit_access':
        return <Badge variant="default" className="text-xs">Médio</Badge>
      default:
        return <Badge variant="secondary" className="text-xs">Baixo</Badge>
    }
  }

  const formatRelativeTime = (timestamp: string) => {
    try {
      return formatDistanceToNow(new Date(timestamp), {
        addSuffix: true,
        locale: ptBR
      })
    } catch {
      return 'Data inválida'
    }
  }

  const formatFullTime = (timestamp: string) => {
    try {
      return new Date(timestamp).toLocaleString('pt-BR')
    } catch {
      return 'Data inválida'
    }
  }

  const getInitials = (name: string) => {
    return name
      .split(' ')
      .map(n => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2)
  }

  const groupActivitiesByDate = (activities: AdminUserActivity[]) => {
    const groups: { [key: string]: AdminUserActivity[] } = {}

    activities.forEach(activity => {
      const date = new Date(activity.timestamp).toLocaleDateString('pt-BR')
      if (!groups[date]) {
        groups[date] = []
      }
      groups[date].push(activity)
    })

    return groups
  }

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Carregando atividades...</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="flex items-center space-x-3 animate-pulse">
                <div className="w-8 h-8 bg-gray-200 rounded-full"></div>
                <div className="flex-1 space-y-2">
                  <div className="h-4 bg-gray-200 rounded w-3/4"></div>
                  <div className="h-3 bg-gray-200 rounded w-1/2"></div>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    )
  }

  if (!activities || activities.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Timeline de Atividades</CardTitle>
          <CardDescription>
            Histórico de ações realizadas pelo usuário
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8">
            <Activity className="h-12 w-12 mx-auto text-gray-400 mb-4" />
            <p className="text-gray-500">Nenhuma atividade registrada</p>
            <p className="text-sm text-gray-400 mt-1">
              As atividades do usuário aparecerão aqui quando realizadas
            </p>
          </div>
        </CardContent>
      </Card>
    )
  }

  const groupedActivities = groupActivitiesByDate(activities)

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <Activity className="h-5 w-5" />
          Timeline de Atividades
        </CardTitle>
        <CardDescription>
          Histórico cronológico das ações realizadas
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ScrollArea style={{ height: maxHeight }}>
          <div className="space-y-6">
            {Object.entries(groupedActivities).map(([date, dateActivities]) => (
              <div key={date}>
                <div className="flex items-center gap-2 mb-4">
                  <Clock className="h-4 w-4 text-gray-500" />
                  <h4 className="text-sm font-medium text-gray-700">{date}</h4>
                  <Separator className="flex-1" />
                  <Badge variant="outline" className="text-xs">
                    {dateActivities.length} atividade(s)
                  </Badge>
                </div>

                <div className="space-y-3 relative">
                  {/* Timeline line */}
                  <div className="absolute left-4 top-0 bottom-0 w-px bg-gray-200"></div>

                  {dateActivities.map((activity, index) => (
                    <div key={activity.id} className="relative flex items-start space-x-3">
                      {/* Timeline dot */}
                      <div className={`relative z-10 flex items-center justify-center w-8 h-8 rounded-full border-2 ${getActivityColor(activity.action)}`}>
                        {getActivityIcon(activity.action)}
                      </div>

                      {/* Activity content */}
                      <div className={`flex-1 min-w-0 p-3 rounded-lg border ${compact ? 'pb-2' : ''} ${getActivityColor(activity.action)}`}>
                        <div className="flex items-start justify-between">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <p className="text-sm font-medium text-gray-900">
                                {getActivityDescription(activity)}
                              </p>
                              {!compact && getSeverityBadge(activity.action)}
                            </div>

                            {showUserInfo && (
                              <div className="flex items-center gap-2 mb-2">
                                <Avatar className="h-5 w-5">
                                  <AvatarFallback className="bg-blue-600 text-white text-xs">
                                    {getInitials(activity.user_email?.split('@')[0] || 'U')}
                                  </AvatarFallback>
                                </Avatar>
                                <span className="text-xs text-gray-600">
                                  {activity.user_email}
                                </span>
                              </div>
                            )}

                            <div className="flex items-center justify-between text-xs text-gray-500">
                              <span title={formatFullTime(activity.timestamp)}>
                                {formatRelativeTime(activity.timestamp)}
                              </span>
                              {activity.ip_address && !compact && (
                                <span>IP: {activity.ip_address}</span>
                              )}
                            </div>

                            {!compact && activity.details && Object.keys(activity.details).length > 0 && (
                              <details className="mt-2">
                                <summary className="text-xs text-blue-600 cursor-pointer hover:text-blue-800">
                                  Ver detalhes
                                </summary>
                                <div className="mt-2 p-2 bg-white bg-opacity-50 rounded text-xs">
                                  {Object.entries(activity.details).map(([key, value]) => (
                                    <div key={key} className="flex justify-between">
                                      <span className="font-medium">{key}:</span>
                                      <span>{typeof value === 'object' ? JSON.stringify(value) : String(value)}</span>
                                    </div>
                                  ))}
                                </div>
                              </details>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}