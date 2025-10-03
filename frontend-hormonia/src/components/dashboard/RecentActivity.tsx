import React from 'react'
import { formatDistanceToNow } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import { 
  MessageSquare, 
  UserPlus, 
  AlertTriangle, 
  FileText,
  Activity
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'

interface ActivityItem {
  id: string
  type: 'message' | 'patient' | 'alert' | 'report' | 'quiz'
  description: string
  timestamp: string
  patient_name?: string
  metadata?: Record<string, any>
}

interface RecentActivityProps {
  activities: ActivityItem[]
}

export function RecentActivity({ activities }: RecentActivityProps) {
  const getActivityIcon = (type: string) => {
    switch (type) {
      case 'message':
        return MessageSquare
      case 'patient':
        return UserPlus
      case 'alert':
        return AlertTriangle
      case 'report':
        return FileText
      case 'quiz':
        return Activity
      default:
        return Activity
    }
  }

  const getActivityColor = (type: string) => {
    switch (type) {
      case 'message':
        return 'text-blue-600 bg-blue-100'
      case 'patient':
        return 'text-green-600 bg-green-100'
      case 'alert':
        return 'text-red-600 bg-red-100'
      case 'report':
        return 'text-purple-600 bg-purple-100'
      case 'quiz':
        return 'text-orange-600 bg-orange-100'
      default:
        return 'text-gray-600 bg-gray-100'
    }
  }

  const getActivityLabel = (type: string) => {
    switch (type) {
      case 'message':
        return 'Mensagem'
      case 'patient':
        return 'Paciente'
      case 'alert':
        return 'Alerta'
      case 'report':
        return 'Relatório'
      case 'quiz':
        return 'Questionário'
      default:
        return 'Atividade'
    }
  }

  if (!activities || activities.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Atividade Recente</CardTitle>
          <CardDescription>
            Últimas ações no sistema
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8">
            <Activity className="mx-auto h-12 w-12 text-gray-400 mb-4" />
            <p className="text-gray-500">Nenhuma atividade recente</p>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Atividade Recente</CardTitle>
        <CardDescription>
          Últimas {activities.length} ações no sistema
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ScrollArea className="h-[300px]">
          <div className="space-y-4">
            {activities.map((activity) => {
              const Icon = getActivityIcon(activity.type)
              const colorClass = getActivityColor(activity.type)
              
              return (
                <div key={activity.id} className="flex items-start space-x-3">
                  <div className={`flex items-center justify-center w-8 h-8 rounded-full ${colorClass}`}>
                    <Icon className="w-4 h-4" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <p className="text-sm font-medium text-gray-900">
                        {activity.description}
                      </p>
                      <Badge variant="outline" className="text-xs">
                        {getActivityLabel(activity.type)}
                      </Badge>
                    </div>
                    {activity.patient_name && (
                      <p className="text-sm text-gray-600">
                        Paciente: {activity.patient_name}
                      </p>
                    )}
                    <p className="text-xs text-gray-500">
                      {formatDistanceToNow(new Date(activity.timestamp), {
                        addSuffix: true,
                        locale: ptBR
                      })}
                    </p>
                  </div>
                </div>
              )
            })}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}
