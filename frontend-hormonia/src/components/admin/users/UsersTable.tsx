import React from 'react'
import { formatDistanceToNow } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { MoreHorizontal, Eye, Edit, Trash2, Lock, Unlock, Shield, ShieldOff, ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react'
import { apiClient } from '@/lib/api-client'
import { AdminUser } from '@/types/admin'
import { getRoleLabel, getRoleColor } from '@/types/shared'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
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
  onSort
}: UsersTableProps) {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [deleteUserId, setDeleteUserId] = React.useState<string | null>(null)

  const mutationOptions = {
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
    },
    onError: (error: any) => {
      toast({
        title: 'Erro',
        description: error.data?.message || 'Ocorreu um erro inesperado.',
        variant: 'destructive'
      })
    }
  }

  const deleteMutation = useMutation({
    mutationFn: (id: string) => apiClient.adminUsers.delete(id),
    ...mutationOptions,
    onSuccess: () => {
      mutationOptions.onSuccess()
      toast({ title: 'Usuário excluído com sucesso' })
      setDeleteUserId(null)
    }
  })

  const activateMutation = useMutation({
    mutationFn: (id: string) => apiClient.adminUsers.activate(id),
    ...mutationOptions,
    onSuccess: () => {
      mutationOptions.onSuccess()
      toast({ title: 'Usuário ativado com sucesso' })
    }
  })

  const deactivateMutation = useMutation({
    mutationFn: (id: string) => apiClient.adminUsers.deactivate(id),
    ...mutationOptions,
    onSuccess: () => {
      mutationOptions.onSuccess()
      toast({ title: 'Usuário desativado com sucesso' })
    }
  })

  const unlockMutation = useMutation({
    mutationFn: (id: string) => apiClient.adminUsers.unlock(id),
    ...mutationOptions,
    onSuccess: () => {
      mutationOptions.onSuccess()
      toast({ title: 'Usuário desbloqueado com sucesso' })
    }
  })

  const enable2FAMutation = useMutation({
    mutationFn: (id: string) => apiClient.adminUsers.enable2FA(id),
    ...mutationOptions,
    onSuccess: () => {
      mutationOptions.onSuccess()
      toast({ title: '2FA habilitado com sucesso' })
    }
  })

  const disable2FAMutation = useMutation({
    mutationFn: (id: string) => apiClient.adminUsers.disable2FA(id),
    ...mutationOptions,
    onSuccess: () => {
      mutationOptions.onSuccess()
      toast({ title: '2FA desabilitado com sucesso' })
    }
  })

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
      .map(n => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2)
  }

  const formatLastLogin = (lastLogin?: string | null) => {
    if (!lastLogin) return 'Nunca'

    try {
      return formatDistanceToNow(new Date(lastLogin), {
        addSuffix: true,
        locale: ptBR
      })
    } catch {
      return 'Data inválida'
    }
  }

  const isUserLocked = (user: AdminUser) => {
    return user.locked_until && new Date(user.locked_until) > new Date()
  }

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
      <div className="text-center py-8">
        <p className="text-gray-500">Nenhum usuário encontrado</p>
        <p className="text-sm text-gray-400 mt-1">
          Tente ajustar os filtros ou criar um novo usuário
        </p>
      </div>
    )
  }

  return (
    <>
      <div className="space-y-4">
        <Table>
          <TableHeader>
            <TableRow>
              {onToggleUserSelection && (
                <TableHead className="w-[50px]">
                  <span className="sr-only">Selecionar</span>
                </TableHead>
              )}
              <TableHead
                className="cursor-pointer hover:bg-gray-50"
                onClick={() => handleSort('full_name')}
              >
                <div className="flex items-center space-x-1">
                  <span>Usuário</span>
                  {getSortIcon('full_name')}
                </div>
              </TableHead>
              <TableHead
                className="cursor-pointer hover:bg-gray-50"
                onClick={() => handleSort('role')}
              >
                <div className="flex items-center space-x-1">
                  <span>Função</span>
                  {getSortIcon('role')}
                </div>
              </TableHead>
              <TableHead
                className="cursor-pointer hover:bg-gray-50"
                onClick={() => handleSort('is_active')}
              >
                <div className="flex items-center space-x-1">
                  <span>Status</span>
                  {getSortIcon('is_active')}
                </div>
              </TableHead>
              <TableHead
                className="cursor-pointer hover:bg-gray-50"
                onClick={() => handleSort('two_factor_enabled')}
              >
                <div className="flex items-center space-x-1">
                  <span>2FA</span>
                  {getSortIcon('two_factor_enabled')}
                </div>
              </TableHead>
              <TableHead
                className="cursor-pointer hover:bg-gray-50"
                onClick={() => handleSort('failed_login_attempts')}
              >
                <div className="flex items-center space-x-1">
                  <span>Tentativas Falhas</span>
                  {getSortIcon('failed_login_attempts')}
                </div>
              </TableHead>
              <TableHead
                className="cursor-pointer hover:bg-gray-50"
                onClick={() => handleSort('last_login')}
              >
                <div className="flex items-center space-x-1">
                  <span>Último Login</span>
                  {getSortIcon('last_login')}
                </div>
              </TableHead>
              <TableHead className="w-[70px]">Ações</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {users.map((user) => (
              <TableRow
                key={user['id']}
                className={`cursor-pointer hover:bg-muted/50 ${
                  selectedUsers.includes(user['id']) ? 'bg-blue-50' : ''
                }`}
                onClick={() => onViewUser(user)}
              >
                {onToggleUserSelection && (
                  <TableCell onClick={(e) => e.stopPropagation()}>
                    <Checkbox
                      checked={selectedUsers.includes(user['id'])}
                      onCheckedChange={() => onToggleUserSelection(user['id'])}
                    />
                  </TableCell>
                )}
                <TableCell>
                  <div className="flex items-center space-x-3">
                    <Avatar className="h-8 w-8">
                      <AvatarFallback className="bg-blue-600 text-white text-xs">
                        {getInitials(user['full_name'])}
                      </AvatarFallback>
                    </Avatar>
                    <div>
                      <p className="font-medium text-gray-900">{user['full_name']}</p>
                      <p className="text-sm text-gray-500">{user['email']}</p>
                    </div>
                  </div>
                </TableCell>
                <TableCell>
                  {getRoleBadge(user['role'])}
                </TableCell>
                <TableCell>
                  {getStatusBadge(user)}
                </TableCell>
                <TableCell>
                  {user.two_factor_enabled ? (
                    <Badge className="bg-green-100 text-green-800">Ativo</Badge>
                  ) : (
                    <Badge variant="outline">Inativo</Badge>
                  )}
                </TableCell>
                <TableCell>
                  {user.failed_login_attempts > 0 ? (
                    <span className="text-red-600 font-medium">{user.failed_login_attempts}</span>
                  ) : (
                    <span className="text-gray-500">0</span>
                  )}
                </TableCell>
                <TableCell>
                  <span className="text-sm text-gray-600">
                    {formatLastLogin(user.last_login)}
                  </span>
                </TableCell>
                <TableCell>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="ghost"
                        className="h-8 w-8 p-0"
                        onClick={(e) => e.stopPropagation()}
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
                        <Eye className="mr-2 h-4 w-4" />
                        Visualizar
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={(e) => {
                          e.stopPropagation()
                          onEditUser(user)
                        }}
                      >
                        <Edit className="mr-2 h-4 w-4" />
                        Editar
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      {isUserLocked(user) ? (
                        <DropdownMenuItem
                          onClick={(e) => {
                            e.stopPropagation()
                            unlockMutation.mutate(user['id'])
                          }}
                        >
                          <Unlock className="mr-2 h-4 w-4" />
                          Desbloquear
                        </DropdownMenuItem>
                      ) : user.is_active ? (
                        <DropdownMenuItem
                          onClick={(e) => {
                            e.stopPropagation()
                            deactivateMutation.mutate(user['id'])
                          }}
                        >
                          <Lock className="mr-2 h-4 w-4" />
                          Desativar
                        </DropdownMenuItem>
                      ) : (
                        <DropdownMenuItem
                          onClick={(e) => {
                            e.stopPropagation()
                            activateMutation.mutate(user['id'])
                          }}
                        >
                          <Unlock className="mr-2 h-4 w-4" />
                          Ativar
                        </DropdownMenuItem>
                      )}
                      {user.two_factor_enabled ? (
                        <DropdownMenuItem
                          onClick={(e) => {
                            e.stopPropagation()
                            disable2FAMutation.mutate(user['id'])
                          }}
                        >
                          <ShieldOff className="mr-2 h-4 w-4" />
                          Desabilitar 2FA
                        </DropdownMenuItem>
                      ) : (
                        <DropdownMenuItem
                          onClick={(e) => {
                            e.stopPropagation()
                            enable2FAMutation.mutate(user['id'])
                          }}
                        >
                          <Shield className="mr-2 h-4 w-4" />
                          Habilitar 2FA
                        </DropdownMenuItem>
                      )}
                      <DropdownMenuSeparator />
                      <DropdownMenuItem
                        className="text-red-600"
                        onClick={(e) => {
                          e.stopPropagation()
                          setDeleteUserId(user['id'])
                        }}
                      >
                        <Trash2 className="mr-2 h-4 w-4" />
                        Excluir
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>

        {totalPages > 1 && (
          <Pagination
            currentPage={currentPage}
            totalPages={totalPages}
            onPageChange={onPageChange}
          />
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