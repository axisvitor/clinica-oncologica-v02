import React, { useState, useMemo } from 'react'
import { Plus, Search, Users, UserCheck, UserX, AlertTriangle } from 'lucide-react'
import { useUserAdmin } from '@/hooks/admin'
import { useAuth } from '@/app/providers/AuthContext'
import { AdminUser } from '@/types/admin'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Checkbox } from '@/components/ui/checkbox'
import { LoadingSpinner } from '@/components/ui/loading-spinner'
import { UsersTable } from './users/UsersTable'
import { UserCreateModal } from './UserCreateModal'
import { UserEditModal } from './UserEditModal'
import { UserDetailsPanel } from './UserDetailsPanel'
import { RoleAssignmentModal } from './RoleAssignmentModal'
import { PermissionGuard } from './PermissionGuard'
import { createLogger } from '../../lib/logger'

const logger = createLogger('UserAdminDashboard')

interface FilterState {
  search: string
  role: string
  status: string
  twoFactor: string
  dateRange: {
    from: Date | null
    to: Date | null
  }
}

export function UserAdminDashboard() {
  useAuth()
  const { users, stats, bulkActivate, bulkDeactivate, isLoading } = useUserAdmin()

  // Modal states
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showEditModal, setShowEditModal] = useState(false)
  const [showDetailsPanel, setShowDetailsPanel] = useState(false)
  const [showRoleModal, setShowRoleModal] = useState(false)
  const [selectedUser, setSelectedUser] = useState<AdminUser | null>(null)

  // Filter and pagination states
  const [filters, setFilters] = useState<FilterState>({
    search: '',
    role: 'all',
    status: 'all',
    twoFactor: 'all',
    dateRange: { from: null, to: null }
  })
  const [currentPage, setCurrentPage] = useState(1)
  const [selectedUsers, setSelectedUsers] = useState<string[]>([])
  const [sortBy, setSortBy] = useState('created_at')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')

  // Filtered and sorted users
  const filteredUsers = useMemo(() => {
    if (!users) return [] as AdminUser[]

    return users.filter((user: AdminUser) => {
      // Search filter
      if (filters.search) {
        const searchLower = filters.search.toLowerCase()
        const matchesSearch =
          (user.full_name?.toLowerCase() ?? '').includes(searchLower) ||
          user.email.toLowerCase().includes(searchLower)
        if (!matchesSearch) return false
      }

      // Role filter
      if (filters.role !== 'all' && user.role !== filters.role) return false

      // Status filter
      if (filters.status === 'active' && !user.is_active) return false
      if (filters.status === 'inactive' && user.is_active) return false
      if (filters.status === 'locked' && (!user.locked_until || new Date(user.locked_until) <= new Date())) return false

      // Two factor filter
      if (filters.twoFactor === 'enabled' && !user.two_factor_enabled) return false
      if (filters.twoFactor === 'disabled' && user.two_factor_enabled) return false

      return true
    }).sort((a: AdminUser, b: AdminUser) => {
      const aRaw = a[sortBy as keyof AdminUser]
      const bRaw = b[sortBy as keyof AdminUser]

      let aVal: string | number
      let bVal: string | number

      // Handle date sorting
      if (sortBy === 'created_at' || sortBy === 'last_login') {
        aVal = aRaw ? new Date(String(aRaw)).getTime() : 0
        bVal = bRaw ? new Date(String(bRaw)).getTime() : 0
      } else if (typeof aRaw === 'string') {
        aVal = aRaw.toLowerCase()
        bVal = typeof bRaw === 'string' ? bRaw.toLowerCase() : ''
      } else if (typeof aRaw === 'number') {
        aVal = aRaw
        bVal = typeof bRaw === 'number' ? bRaw : 0
      } else {
        aVal = ''
        bVal = ''
      }

      if (sortOrder === 'asc') {
        return aVal > bVal ? 1 : -1
      } else {
        return aVal < bVal ? 1 : -1
      }
    })
  }, [users, filters, sortBy, sortOrder])

  // Pagination
  const itemsPerPage = 10
  const totalPages = Math.ceil(filteredUsers.length / itemsPerPage)
  const paginatedUsers = filteredUsers.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  )

  // Handlers
  const handleViewUser = (user: AdminUser) => {
    setSelectedUser(user)
    setShowDetailsPanel(true)
  }

  const handleEditUser = (user: AdminUser) => {
    setSelectedUser(user)
    setShowEditModal(true)
  }

  const handleAssignRole = (user: AdminUser) => {
    setSelectedUser(user)
    setShowRoleModal(true)
  }

  const handleBulkAction = async (action: 'activate' | 'deactivate') => {
    if (selectedUsers.length === 0) return

    try {
      if (action === 'activate') {
        await bulkActivate(selectedUsers)
      } else {
        await bulkDeactivate(selectedUsers)
      }
      setSelectedUsers([])
    } catch (error) {
      logger.error('Bulk action failed', { error, action, selectedUsers })
    }
  }

  const toggleUserSelection = (userId: string) => {
    setSelectedUsers(prev =>
      prev.includes(userId)
        ? prev.filter(id => id !== userId)
        : [...prev, userId]
    )
  }

  const toggleAllUsers = () => {
    if (selectedUsers.length === paginatedUsers.length) {
      setSelectedUsers([])
    } else {
      setSelectedUsers(paginatedUsers.map((user: AdminUser) => user.id))
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Gerenciamento de Usuários</h1>
          <p className="text-muted-foreground">
            Gerencie usuários do sistema, permissões e configurações de segurança
          </p>
        </div>
        <PermissionGuard permissions={['admin.users.create']}>
          <Button onClick={() => setShowCreateModal(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Novo Usuário
          </Button>
        </PermissionGuard>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total de Usuários</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.users.total || 0}</div>
            <p className="text-xs text-muted-foreground">
              +{stats?.users.new_today || 0} hoje
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Usuários Ativos</CardTitle>
            <UserCheck className="h-4 w-4 text-green-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.users.active || 0}</div>
            <p className="text-xs text-muted-foreground">
              {stats?.users.total ? Math.round((stats.users.active / stats.users.total) * 100) : 0}% do total
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Usuários Bloqueados</CardTitle>
            <UserX className="h-4 w-4 text-red-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.users.locked || 0}</div>
            <p className="text-xs text-muted-foreground">
              Requer atenção
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Tentativas de Login Falhadas</CardTitle>
            <AlertTriangle className="h-4 w-4 text-orange-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.security.failed_logins || 0}</div>
            <p className="text-xs text-muted-foreground">
              Últimas 24h
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Filters and Search */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col md:flex-row gap-4">
            {/* Search */}
            <div className="flex-1">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-4 w-4" />
                <Input
                  placeholder="Buscar por nome ou email..."
                  value={filters.search}
                  onChange={(e) => setFilters(prev => ({ ...prev, search: e.target.value }))}
                  className="pl-10"
                />
              </div>
            </div>

            {/* Role Filter */}
            <Select value={filters.role} onValueChange={(value) => setFilters(prev => ({ ...prev, role: value }))}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Filtrar por função" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todas as funções</SelectItem>
                <SelectItem value="doctor">Médico</SelectItem>
                <SelectItem value="admin">Administrador</SelectItem>
              </SelectContent>
            </Select>

            {/* Status Filter */}
            <Select value={filters.status} onValueChange={(value) => setFilters(prev => ({ ...prev, status: value }))}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Filtrar por status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos os status</SelectItem>
                <SelectItem value="active">Ativo</SelectItem>
                <SelectItem value="inactive">Inativo</SelectItem>
                <SelectItem value="locked">Bloqueado</SelectItem>
              </SelectContent>
            </Select>

            {/* 2FA Filter */}
            <Select value={filters.twoFactor} onValueChange={(value) => setFilters(prev => ({ ...prev, twoFactor: value }))}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Filtrar por 2FA" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos</SelectItem>
                <SelectItem value="enabled">2FA Ativo</SelectItem>
                <SelectItem value="disabled">2FA Inativo</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Bulk Actions */}
      {selectedUsers.length > 0 && (
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Badge variant="secondary">
                  {selectedUsers.length} usuário(s) selecionado(s)
                </Badge>
              </div>
              <div className="flex gap-2">
                <PermissionGuard permissions={['admin.users.update']}>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleBulkAction('activate')}
                  >
                    Ativar Selecionados
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleBulkAction('deactivate')}
                  >
                    Desativar Selecionados
                  </Button>
                </PermissionGuard>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Users Table */}
      <Card>
        <CardContent className="pt-6">
          <div className="space-y-4">
            {/* Table Header with Bulk Select */}
            <div className="flex items-center gap-2">
              <Checkbox
                checked={selectedUsers.length === paginatedUsers.length && paginatedUsers.length > 0}
                onCheckedChange={toggleAllUsers}
              />
              <span className="text-sm text-muted-foreground">
                Selecionar todos ({paginatedUsers.length})
              </span>
            </div>

            <UsersTable
              users={paginatedUsers}
              currentPage={currentPage}
              totalPages={totalPages}
              onPageChange={setCurrentPage}
              onViewUser={handleViewUser}
              onEditUser={handleEditUser}
              selectedUsers={selectedUsers}
              onToggleUserSelection={toggleUserSelection}
              sortBy={sortBy}
              sortOrder={sortOrder}
              onSort={(field) => {
                if (sortBy === field) {
                  setSortOrder(prev => prev === 'asc' ? 'desc' : 'asc')
                } else {
                  setSortBy(field)
                  setSortOrder('asc')
                }
              }}
            />
          </div>
        </CardContent>
      </Card>

      {/* Modals */}
      <UserCreateModal
        open={showCreateModal}
        onOpenChange={setShowCreateModal}
      />

      <UserEditModal
        open={showEditModal}
        onOpenChange={setShowEditModal}
        user={selectedUser}
      />

      <UserDetailsPanel
        open={showDetailsPanel}
        onOpenChange={setShowDetailsPanel}
        user={selectedUser}
        onEdit={handleEditUser}
        onAssignRole={handleAssignRole}
      />

      <RoleAssignmentModal
        open={showRoleModal}
        onOpenChange={setShowRoleModal}
        user={selectedUser}
      />
    </div>
  )
}
