import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Plus, Search, Filter, Download } from 'lucide-react'
import { apiClient } from '@/lib/api-client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { UsersTable } from './UsersTable'
import { CreateUserModal } from './CreateUserModal'
import { UserDetailsModal } from './UserDetailsModal'
import { AdminUser } from '@/types/admin'
import { createLogger } from '../../../lib/logger'

const logger = createLogger('UserListPage')

export function UserListPage() {
  const [currentPage, setCurrentPage] = useState(1)
  const [search, setSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState<string>('all')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [createModalOpen, setCreateModalOpen] = useState(false)
  const [selectedUser, setSelectedUser] = useState<AdminUser | null>(null)
  const pageSize = 10

  const { data, isLoading, error } = useQuery({
    queryKey: ['admin-users', currentPage, search, roleFilter, statusFilter],
    queryFn: async () => {
      const params: any = {
        page: currentPage,
        size: pageSize
      }

      if (search) params.search = search
      if (roleFilter !== 'all') params.role = roleFilter
      if (statusFilter !== 'all') params.is_active = statusFilter === 'active'

      return apiClient.adminUsers.list(params)
    }
  })

  const handleSearch = (value: string) => {
    setSearch(value)
    setCurrentPage(1)
  }

  const handleRoleFilter = (value: string) => {
    setRoleFilter(value)
    setCurrentPage(1)
  }

  const handleStatusFilter = (value: string) => {
    setStatusFilter(value)
    setCurrentPage(1)
  }

  const handleExport = () => {
    // TODO: Implement export functionality
    logger.info('Export users data requested')
  }

  const handleViewUser = (user: AdminUser) => {
    setSelectedUser(user)
  }

  const handleEditUser = (user: AdminUser) => {
    setSelectedUser(user)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Gerenciamento de Usuários</h1>
          <p className="text-muted-foreground">
            Gerencie usuários administrativos, permissões e atividades
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleExport}>
            <Download className="mr-2 h-4 w-4" />
            Exportar
          </Button>
          <Button onClick={() => setCreateModalOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Novo Usuário
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total de Usuários</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{data?.total || 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Usuários Ativos</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {data?.items?.filter((u: AdminUser) => u.is_active).length || 0}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Administradores</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {data?.items?.filter((u: AdminUser) => u.role === 'admin').length || 0}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Bloqueados</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {data?.items?.filter((u: AdminUser) => u.locked_until && new Date(u.locked_until) > new Date()).length || 0}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle>Filtros</CardTitle>
          <CardDescription>
            Use os filtros abaixo para encontrar usuários específicos
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex gap-4 flex-wrap">
            <div className="flex-1 min-w-[200px]">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Buscar por nome ou email..."
                  value={search}
                  onChange={(e) => handleSearch(e.target.value)}
                  className="pl-9"
                />
              </div>
            </div>
            <Select value={roleFilter} onValueChange={handleRoleFilter}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Função" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todas as Funções</SelectItem>
                <SelectItem value="doctor">Médico</SelectItem>
                <SelectItem value="admin">Administrador</SelectItem>
              </SelectContent>
            </Select>
            <Select value={statusFilter} onValueChange={handleStatusFilter}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos os Status</SelectItem>
                <SelectItem value="active">Ativos</SelectItem>
                <SelectItem value="inactive">Inativos</SelectItem>
              </SelectContent>
            </Select>
            {(search || roleFilter !== 'all' || statusFilter !== 'all') && (
              <Button
                variant="ghost"
                onClick={() => {
                  setSearch('')
                  setRoleFilter('all')
                  setStatusFilter('all')
                }}
              >
                Limpar Filtros
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Users Table */}
      <Card>
        <CardContent className="pt-6">
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
            </div>
          ) : error ? (
            <div className="text-center py-8">
              <p className="text-red-500">Erro ao carregar usuários</p>
              <p className="text-sm text-muted-foreground mt-1">
                {error instanceof Error ? error.message : 'Erro desconhecido'}
              </p>
            </div>
          ) : (
            <UsersTable
              users={data?.items || []}
              currentPage={currentPage}
              totalPages={data?.pages || 1}
              onPageChange={setCurrentPage}
              onViewUser={handleViewUser}
              onEditUser={handleEditUser}
            />
          )}
        </CardContent>
      </Card>

      {/* Modals */}
      <CreateUserModal
        open={createModalOpen}
        onOpenChange={setCreateModalOpen}
      />

      {selectedUser && (
        <UserDetailsModal
          user={selectedUser}
          open={!!selectedUser}
          onOpenChange={(open) => !open && setSelectedUser(null)}
        />
      )}
    </div>
  )
}