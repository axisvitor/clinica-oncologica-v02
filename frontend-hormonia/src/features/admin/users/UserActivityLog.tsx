import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { formatDistanceToNow } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import { Activity, AlertCircle, CheckCircle, Info, XCircle, Filter } from 'lucide-react'
import { apiClient } from '@/lib/api-client'
import { AdminUserActivity } from '@/types/admin'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Pagination } from '@/components/ui/pagination'
import { toReactString } from '@/lib/utils/type-guards'

interface UserActivityLogProps {
  userId: string
}

const ACTION_COLORS: Record<string, string> = {
  login: 'bg-blue-100 text-blue-800',
  logout: 'bg-gray-100 text-gray-800',
  create: 'bg-green-100 text-green-800',
  update: 'bg-yellow-100 text-yellow-800',
  delete: 'bg-red-100 text-red-800',
  view: 'bg-purple-100 text-purple-800',
  export: 'bg-orange-100 text-orange-800'
}

const ACTION_ICONS: Record<string, React.ReactNode> = {
  login: <CheckCircle className="h-4 w-4" />,
  logout: <Info className="h-4 w-4" />,
  create: <CheckCircle className="h-4 w-4" />,
  update: <AlertCircle className="h-4 w-4" />,
  delete: <XCircle className="h-4 w-4" />,
  view: <Info className="h-4 w-4" />,
  export: <Activity className="h-4 w-4" />
}

export function UserActivityLog({ userId }: UserActivityLogProps) {
  const [currentPage, setCurrentPage] = useState(1)
  const [actionFilter, setActionFilter] = useState<string>('all')
  const pageSize = 10

  const { data, isLoading, error } = useQuery({
    queryKey: ['user-activity', userId, currentPage, actionFilter],
    queryFn: async () => {
      const params: Record<string, string | number> = {
        page: currentPage,
        size: pageSize
      }

      if (actionFilter !== 'all') {
        params['action'] = actionFilter
      }

      return apiClient.adminUsers.getActivity(userId, params)
    }
  })

  const formatTimestamp = (timestamp: string) => {
    try {
      return formatDistanceToNow(new Date(timestamp), {
        addSuffix: true,
        locale: ptBR
      })
    } catch {
      return 'Data inválida'
    }
  }

  const getActionBadge = (action: string) => {
    const colorClass = ACTION_COLORS[action.toLowerCase()] || 'bg-gray-100 text-gray-800'
    const icon = ACTION_ICONS[action.toLowerCase()] || <Activity className="h-4 w-4" />

    return (
      <Badge className={`${colorClass} flex items-center gap-1`}>
        {icon}
        {action}
      </Badge>
    )
  }

  const getUniqueActions = () => {
    const actions = new Set<string>()
    data?.items?.forEach((activity: AdminUserActivity) => {
      actions.add(activity.action)
    })
    return Array.from(actions)
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center py-8">
        <p className="text-red-500">Erro ao carregar atividades</p>
        <p className="text-sm text-muted-foreground mt-1">
          {error instanceof Error ? error.message : 'Erro desconhecido'}
        </p>
      </div>
    )
  }

  const activities = data?.items || []

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium">Filtrar por ação:</span>
        </div>
        <Select value={actionFilter} onValueChange={setActionFilter}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Todas as ações" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Todas as ações</SelectItem>
            {getUniqueActions().map((action) => (
              <SelectItem key={action} value={action}>
                {action}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {actionFilter !== 'all' && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setActionFilter('all')}
          >
            Limpar
          </Button>
        )}
      </div>

      {/* Activity List */}
      {activities.length === 0 ? (
        <div className="text-center py-8">
          <Activity className="h-12 w-12 text-muted-foreground mx-auto mb-2" />
          <p className="text-muted-foreground">Nenhuma atividade registrada</p>
        </div>
      ) : (
        <ScrollArea className="h-[400px] border rounded-lg">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Ação</TableHead>
                <TableHead>Recurso</TableHead>
                <TableHead>Detalhes</TableHead>
                <TableHead>IP</TableHead>
                <TableHead>Quando</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {activities.map((activity: AdminUserActivity) => (
                <TableRow key={activity['id']}>
                  <TableCell>
                    {getActionBadge(activity.action)}
                  </TableCell>
                  <TableCell>
                    <div className="space-y-1">
                      <p className="font-medium">{activity.resource}</p>
                      {activity.details?.['id'] != null && (
                        <p className="text-xs text-muted-foreground">
                          ID: {toReactString(activity.details['id'], 'N/A')}
                        </p>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    {activity.details && Object.keys(activity.details).length > 0 ? (
                      <div className="text-sm text-muted-foreground max-w-[200px] truncate">
                        {JSON.stringify(activity.details)}
                      </div>
                    ) : (
                      <span className="text-muted-foreground">-</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <span className="text-sm font-mono">{activity.ip_address}</span>
                  </TableCell>
                  <TableCell>
                    <span className="text-sm text-muted-foreground">
                      {formatTimestamp(activity.timestamp)}
                    </span>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </ScrollArea>
      )}

      {/* Pagination */}
      {data?.pages && data.pages > 1 && (
        <Pagination
          currentPage={currentPage}
          totalPages={data.pages}
          onPageChange={setCurrentPage}
        />
      )}
    </div>
  )
}