import React, { memo } from 'react'
import { formatDistanceToNow } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  MoreHorizontal,
  Eye,
  Edit,
  Trash2,
  Lock,
  Unlock,
  Shield,
  ShieldOff,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
} from 'lucide-react'
import { apiClient } from '@/lib/api-client'
import { AdminUser } from '@/types/admin'
import { getRoleLabel, getRoleColor } from '@/types/shared'
import { FixedSizeList } from 'react-window'
import AutoSizer from 'react-virtualized-auto-sizer'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Card } from '@/components/ui/card'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Pagination } from '@/components/ui/pagination'
import { Checkbox } from '@/components/ui/checkbox'
import { useToast } from '@/components/ui/use-toast'
import { cn } from '@/lib/utils'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'

interface UsersTableProps {
  users: AdminUser[]
  currentPage: number
  totalPages: number
  onPageChange: (page: number) => void
  onViewUser: (user: AdminUser) => void
  onEditUser: (user: AdminUser) => void
  selectedUsers?: string[]
  onToggleUserSelection?: (userId: string) => void
  sortBy?: string
  sortOrder?: 'asc' | 'desc'
  onSort?: (field: string) => void
}

// Mutation type for user operations
interface UserMutation {
  isPending: boolean
  mutate: (id: string) => void
}

interface RowData {
  users: AdminUser[]
  onViewUser: (user: AdminUser) => void
  onEditUser: (user: AdminUser) => void
  selectedUsers: string[]
  onToggleUserSelection?: (userId: string) => void
  setDeleteUserId: (id: string) => void
  activateMutation: UserMutation
  deactivateMutation: UserMutation
  unlockMutation: UserMutation
  enable2FAMutation: UserMutation
  disable2FAMutation: UserMutation
  gridCols: string
}

const MobileUserCard = memo(
  ({ style, index, data }: { style: React.CSSProperties; index: number; data: RowData }) => {
    const {
      users,
      onViewUser,
      onEditUser,
      selectedUsers,
      onToggleUserSelection,
      setDeleteUserId,
      activateMutation,
      deactivateMutation,
      unlockMutation,
      enable2FAMutation,
      disable2FAMutation,
    } = data
    const user = users[index]

    // Early return if user is undefined (shouldn't happen but satisfies TypeScript)
    if (!user) return null

    const isUserLocked = (u: AdminUser): boolean => {
      return !!(u.locked_until && new Date(u.locked_until) > new Date())
    }
    const isLocked = isUserLocked(user)
    const selected = selectedUsers.includes(user.id)

    const getInitials = (name: string) => {
      return name
        .split(' ')
        .map((n) => n[0])
        .join('')
        .toUpperCase()
        .slice(0, 2)
    }

    const formatLastLogin = (lastLogin?: string | null) => {
      if (!lastLogin) return 'Nunca'
      try {
        return formatDistanceToNow(new Date(lastLogin), { addSuffix: true, locale: ptBR })
      } catch {
        return 'Data inválida'
      }
    }

    const getRoleBadge = (role: string) => {
      const colorClasses = getRoleColor(role)
      const label = getRoleLabel(role)
      return <Badge className={colorClasses}>{label}</Badge>
    }

    const getStatusBadge = () => {
      if (isLocked) return <Badge variant="destructive">Bloqueado</Badge>
      if (!user.is_active) return <Badge variant="secondary">Inativo</Badge>
      return <Badge className="bg-green-100 text-green-800">Ativo</Badge>
    }

    return (
      <div style={style} className="px-4 pb-3">
        <Card className={`p-4 ${selected ? 'ring-2 ring-blue-500' : ''}`}>
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3 flex-1 min-w-0">
              {onToggleUserSelection && (
                <Checkbox
                  checked={selected}
                  onCheckedChange={() => onToggleUserSelection(user.id)}
                  className="flex-shrink-0"
                  onClick={(e) => e.stopPropagation()}
                />
              )}
              <Avatar className="h-10 w-10 flex-shrink-0">
                <AvatarFallback className="bg-blue-600 text-white">
                  {getInitials(user.full_name || '')}
                </AvatarFallback>
              </Avatar>
              <div className="min-w-0 flex-1">
                <p className="font-medium truncate">{user.full_name || 'Sem nome'}</p>
                <p className="text-sm text-muted-foreground truncate">{user.email}</p>
              </div>
            </div>
            {getStatusBadge()}
          </div>

          <div className="grid grid-cols-2 gap-2 text-sm mb-3">
            <div>
              <span className="text-muted-foreground">Função:</span>
              <div className="mt-1">{getRoleBadge(user.role)}</div>
            </div>
            <div>
              <span className="text-muted-foreground">2FA:</span>
              <div className="mt-1">
                {user.two_factor_enabled ? (
                  <Badge className="bg-green-100 text-green-800">Ativo</Badge>
                ) : (
                  <Badge variant="outline">Inativo</Badge>
                )}
              </div>
            </div>
            <div>
              <span className="text-muted-foreground">Último Login:</span>
              <p className="font-medium truncate">{formatLastLogin(user.last_login)}</p>
            </div>
            <div>
              <span className="text-muted-foreground">Tentativas Falhas:</span>
              <p className={`font-medium ${user.failed_login_attempts > 0 ? 'text-red-600' : ''}`}>
                {user.failed_login_attempts}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap gap-2 pt-3 border-t">
            <Button
              variant="outline"
              size="sm"
              className="flex-1 min-w-[100px] h-9"
              onClick={(e) => {
                e.stopPropagation()
                onViewUser(user)
              }}
            >
              <Eye className="h-4 w-4 mr-1" /> Ver
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="flex-1 min-w-[100px] h-9"
              onClick={(e) => {
                e.stopPropagation()
                onEditUser(user)
              }}
            >
              <Edit className="h-4 w-4 mr-1" /> Editar
            </Button>
            {isLocked ? (
              <Button
                variant="default"
                size="sm"
                className="flex-1 min-w-[100px] h-9"
                onClick={(e) => {
                  e.stopPropagation()
                  unlockMutation.mutate(user.id)
                }}
              >
                <Unlock className="h-4 w-4 mr-1" /> Desbloquear
              </Button>
            ) : (
              <Button
                variant={user.is_active ? 'outline' : 'default'}
                size="sm"
                className="flex-1 min-w-[100px] h-9"
                onClick={(e) => {
                  e.stopPropagation()
                  if (user.is_active) deactivateMutation.mutate(user.id)
                  else activateMutation.mutate(user.id)
                }}
              >
                {user.is_active ? (
                  <>
                    <Lock className="h-4 w-4 mr-1" /> Desativar
                  </>
                ) : (
                  <>
                    <Unlock className="h-4 w-4 mr-1" /> Ativar
                  </>
                )}
              </Button>
            )}
            <Button
              variant="outline"
              size="sm"
              className="flex-1 min-w-[100px] h-9"
              onClick={(e) => {
                e.stopPropagation()
                if (user.two_factor_enabled) disable2FAMutation.mutate(user.id)
                else enable2FAMutation.mutate(user.id)
              }}
            >
              {user.two_factor_enabled ? (
                <>
                  <ShieldOff className="h-4 w-4 mr-1" /> 2FA Off
                </>
              ) : (
                <>
                  <Shield className="h-4 w-4 mr-1" /> 2FA On
                </>
              )}
            </Button>
            <Button
              variant="destructive"
              size="sm"
              className="h-9 w-full sm:w-auto sm:px-4"
              onClick={(e) => {
                e.stopPropagation()
                setDeleteUserId(user.id)
              }}
            >
              <Trash2 className="h-4 w-4 mr-1" /> Excluir
            </Button>
          </div>
        </Card>
      </div>
    )
  }
)

const UserRow = memo(
  ({ style, index, data }: { style: React.CSSProperties; index: number; data: RowData }) => {
    const {
      users,
      onViewUser,
      onEditUser,
      selectedUsers,
      onToggleUserSelection,
      setDeleteUserId,
      activateMutation,
      deactivateMutation,
      unlockMutation,
      enable2FAMutation,
      disable2FAMutation,
      gridCols,
    } = data
    const user = users[index]

    // Early return if user is undefined (shouldn't happen but satisfies TypeScript)
    if (!user) return null

    const isUserLocked = (u: AdminUser): boolean => {
      return !!(u.locked_until && new Date(u.locked_until) > new Date())
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

    const getInitials = (name: string) => {
      return name
        .split(' ')
        .map((n) => n[0])
        .join('')
        .toUpperCase()
        .slice(0, 2)
    }

    const formatLastLogin = (lastLogin?: string | null) => {
      if (!lastLogin) return 'Nunca'
      try {
        return formatDistanceToNow(new Date(lastLogin), { addSuffix: true, locale: ptBR })
      } catch {
        return 'Data inválida'
      }
    }

    const handleKeyDown = (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault()
        onViewUser(user)
      }
    }

    return (
      <div
        style={style}
        className={cn(
          'grid items-center gap-4 px-4 py-2 border-b hover:bg-muted/50 transition-colors cursor-pointer text-sm',
          gridCols,
          selectedUsers.includes(user.id) ? 'bg-blue-50' : ''
        )}
        onClick={() => onViewUser(user)}
        role="button"
        tabIndex={0}
        onKeyDown={handleKeyDown}
        aria-label={`Ver detalhes do usuario ${user.full_name}`}
      >
        {onToggleUserSelection && (
          <div onClick={(e) => e.stopPropagation()}>
            <Checkbox
              checked={selectedUsers.includes(user.id)}
              onCheckedChange={() => onToggleUserSelection(user.id)}
            />
          </div>
        )}
        <div className="flex items-center space-x-3 min-w-0">
          <Avatar className="h-8 w-8 flex-shrink-0">
            <AvatarFallback className="bg-blue-600 text-white text-xs">
              {getInitials(user.full_name || '')}
            </AvatarFallback>
          </Avatar>
          <div className="min-w-0">
            <p className="font-medium text-gray-900 truncate">{user.full_name}</p>
            <p className="text-sm text-gray-500 truncate">{user.email}</p>
          </div>
        </div>
        <div>{getRoleBadge(user.role)}</div>
        <div>{getStatusBadge(user)}</div>
        <div>
          {user.two_factor_enabled ? (
            <Badge className="bg-green-100 text-green-800">Ativo</Badge>
          ) : (
            <Badge variant="outline">Inativo</Badge>
          )}
        </div>
        <div>
          {user.failed_login_attempts > 0 ? (
            <span className="text-red-600 font-medium">{user.failed_login_attempts}</span>
          ) : (
            <span className="text-gray-500">0</span>
          )}
        </div>
        <div className="text-gray-600 truncate">{formatLastLogin(user.last_login)}</div>
        <div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                className="h-8 w-8 p-0"
                onClick={(e) => e.stopPropagation()}
                aria-label="Acoes"
              >
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>Ações</DropdownMenuLabel>
              <DropdownMenuItem
                onClick={(e) => {
                  e.stopPropagation()
                  onViewUser(user)
                }}
              >
                <Eye className="mr-2 h-4 w-4" /> Visualizar
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={(e) => {
                  e.stopPropagation()
                  onEditUser(user)
                }}
              >
                <Edit className="mr-2 h-4 w-4" /> Editar
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              {isUserLocked(user) ? (
                <DropdownMenuItem
                  onClick={(e) => {
                    e.stopPropagation()
                    unlockMutation.mutate(user.id)
                  }}
                >
                  <Unlock className="mr-2 h-4 w-4" /> Desbloquear
                </DropdownMenuItem>
              ) : user.is_active ? (
                <DropdownMenuItem
                  onClick={(e) => {
                    e.stopPropagation()
                    deactivateMutation.mutate(user.id)
                  }}
                >
                  <Lock className="mr-2 h-4 w-4" /> Desativar
                </DropdownMenuItem>
              ) : (
                <DropdownMenuItem
                  onClick={(e) => {
                    e.stopPropagation()
                    activateMutation.mutate(user.id)
                  }}
                >
                  <Unlock className="mr-2 h-4 w-4" /> Ativar
                </DropdownMenuItem>
              )}
              {user.two_factor_enabled ? (
                <DropdownMenuItem
                  onClick={(e) => {
                    e.stopPropagation()
                    disable2FAMutation.mutate(user.id)
                  }}
                >
                  <ShieldOff className="mr-2 h-4 w-4" /> Desabilitar 2FA
                </DropdownMenuItem>
              ) : (
                <DropdownMenuItem
                  onClick={(e) => {
                    e.stopPropagation()
                    enable2FAMutation.mutate(user.id)
                  }}
                >
                  <Shield className="mr-2 h-4 w-4" /> Habilitar 2FA
                </DropdownMenuItem>
              )}
              <DropdownMenuSeparator />
              <DropdownMenuItem
                className="text-red-600"
                onClick={(e) => {
                  e.stopPropagation()
                  setDeleteUserId(user.id)
                }}
              >
                <Trash2 className="mr-2 h-4 w-4" /> Excluir
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    )
  }
)

export function UsersTable({
  users,
  currentPage,
  totalPages,
  onPageChange,
  onViewUser,
  onEditUser,
  selectedUsers = [],
  onToggleUserSelection,
  sortBy = 'created_at',
  sortOrder = 'desc',
  onSort,
}: UsersTableProps) {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [deleteUserId, setDeleteUserId] = React.useState<string | null>(null)

  const mutationOptions = {
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
    },
    onError: (error: unknown) => {
      const message =
        (error as { data?: { message?: string } }).data?.message || 'Ocorreu um erro inesperado.'
      toast({
        title: 'Erro',
        description: message,
        variant: 'destructive',
      })
    },
  }

  const deleteMutation = useMutation({
    mutationFn: (id: string) => apiClient.adminUsers.delete(id),
    ...mutationOptions,
    onSuccess: () => {
      mutationOptions.onSuccess()
      toast({ title: 'Usuário excluído com sucesso' })
      setDeleteUserId(null)
    },
  })

  const activateMutation = useMutation({
    mutationFn: (id: string) => apiClient.adminUsers.activate(id),
    ...mutationOptions,
    onSuccess: () => {
      mutationOptions.onSuccess()
      toast({ title: 'Usuário ativado com sucesso' })
    },
  })

  const deactivateMutation = useMutation({
    mutationFn: (id: string) => apiClient.adminUsers.deactivate(id),
    ...mutationOptions,
    onSuccess: () => {
      mutationOptions.onSuccess()
      toast({ title: 'Usuário desativado com sucesso' })
    },
  })

  const unlockMutation = useMutation({
    mutationFn: (id: string) => apiClient.adminUsers.unlock(id),
    ...mutationOptions,
    onSuccess: () => {
      mutationOptions.onSuccess()
      toast({ title: 'Usuário desbloqueado com sucesso' })
    },
  })

  const enable2FAMutation = useMutation({
    mutationFn: (id: string) => apiClient.adminUsers.enable2FA(id),
    ...mutationOptions,
    onSuccess: () => {
      mutationOptions.onSuccess()
      toast({ title: '2FA habilitado com sucesso' })
    },
  })

  const disable2FAMutation = useMutation({
    mutationFn: (id: string) => apiClient.adminUsers.disable2FA(id),
    ...mutationOptions,
    onSuccess: () => {
      mutationOptions.onSuccess()
      toast({ title: '2FA desabilitado com sucesso' })
    },
  })

  const getSortIcon = (field: string) => {
    if (sortBy !== field) {
      return <ArrowUpDown className="h-4 w-4" />
    }
    return sortOrder === 'asc' ? <ArrowUp className="h-4 w-4" /> : <ArrowDown className="h-4 w-4" />
  }

  const handleSort = (field: string) => {
    if (onSort) {
      onSort(field)
    }
  }

  if (users.length === 0) {
    return (
      <Card className="p-8 text-center text-muted-foreground">
        <p className="text-gray-500">Nenhum usuário encontrado</p>
        <p className="text-sm text-gray-400 mt-1">
          Tente ajustar os filtros ou criar um novo usuário
        </p>
      </Card>
    )
  }

  const gridCols = onToggleUserSelection
    ? 'grid-cols-[50px_2fr_1.2fr_0.8fr_0.8fr_1fr_1.2fr_70px]'
    : 'grid-cols-[2fr_1.2fr_0.8fr_0.8fr_1fr_1.2fr_70px]'

  const itemData: RowData = {
    users,
    onViewUser,
    onEditUser,
    selectedUsers,
    onToggleUserSelection,
    setDeleteUserId,
    activateMutation,
    deactivateMutation,
    unlockMutation,
    enable2FAMutation,
    disable2FAMutation,
    gridCols,
  }

  return (
    <>
      <div className="space-y-4 h-[calc(100dvh-220px)] min-h-[500px] flex flex-col">
        {/* Desktop Table */}
        <div className="hidden md:flex flex-1 flex-col rounded-md border overflow-hidden">
          <div className={cn('grid bg-gray-50 font-medium text-sm border-b', gridCols)}>
            {onToggleUserSelection && (
              <div className="px-4 py-3 flex items-center">
                <span className="sr-only">Selecionar</span>
              </div>
            )}
            <button
              type="button"
              className="px-4 py-3 flex items-center space-x-1 cursor-pointer hover:bg-gray-100 text-left"
              onClick={() => handleSort('full_name')}
            >
              <span>Usuário</span>
              {getSortIcon('full_name')}
            </button>
            <button
              type="button"
              className="px-4 py-3 flex items-center space-x-1 cursor-pointer hover:bg-gray-100 text-left"
              onClick={() => handleSort('role')}
            >
              <span>Função</span>
              {getSortIcon('role')}
            </button>
            <button
              type="button"
              className="px-4 py-3 flex items-center space-x-1 cursor-pointer hover:bg-gray-100 text-left"
              onClick={() => handleSort('is_active')}
            >
              <span>Status</span>
              {getSortIcon('is_active')}
            </button>
            <button
              type="button"
              className="px-4 py-3 flex items-center space-x-1 cursor-pointer hover:bg-gray-100 text-left"
              onClick={() => handleSort('two_factor_enabled')}
            >
              <span>2FA</span>
              {getSortIcon('two_factor_enabled')}
            </button>
            <button
              type="button"
              className="px-4 py-3 flex items-center space-x-1 cursor-pointer hover:bg-gray-100 text-left"
              onClick={() => handleSort('failed_login_attempts')}
            >
              <span>Tentativas Falhas</span>
              {getSortIcon('failed_login_attempts')}
            </button>
            <button
              type="button"
              className="px-4 py-3 flex items-center space-x-1 cursor-pointer hover:bg-gray-100 text-left"
              onClick={() => handleSort('last_login')}
            >
              <span>Último Login</span>
              {getSortIcon('last_login')}
            </button>
            <div className="px-4 py-3 w-[70px]">Ações</div>
          </div>

          <div className="flex-1">
            <AutoSizer>
              {({ height, width }) => (
                <FixedSizeList
                  height={height}
                  width={width}
                  itemCount={users.length}
                  itemSize={60}
                  itemData={itemData}
                >
                  {UserRow}
                </FixedSizeList>
              )}
            </AutoSizer>
          </div>
        </div>

        {/* Mobile Cards */}
        <div className="md:hidden flex-1">
          <AutoSizer>
            {({ height, width }) => (
              <FixedSizeList
                height={height}
                width={width}
                itemCount={users.length}
                itemSize={350}
                itemData={itemData}
              >
                {MobileUserCard}
              </FixedSizeList>
            )}
          </AutoSizer>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="pt-2">
            <Pagination
              currentPage={currentPage}
              totalPages={totalPages}
              onPageChange={onPageChange}
            />
          </div>
        )}
      </div>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={!!deleteUserId} onOpenChange={(open) => !open && setDeleteUserId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Tem certeza?</AlertDialogTitle>
            <AlertDialogDescription>
              Esta ação não pode ser desfeita. O usuário será permanentemente excluído do sistema.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => deleteUserId && deleteMutation.mutate(deleteUserId)}
              className="bg-red-600 hover:bg-red-700"
            >
              Excluir
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
