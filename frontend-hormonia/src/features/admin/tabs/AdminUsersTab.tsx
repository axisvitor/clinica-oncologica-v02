import React, { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Loader2, Users, Search, ListFilter } from 'lucide-react'
import { useSystemStats } from '@/hooks/api/useSystemStats'

/**
 * AdminUsersTab - User management interface
 *
 * Provides:
 * - User list with search and filtering
 * - User statistics (total, active, by role)
 * - User creation and editing
 * - User status management
 *
 * @note This tab displays mock data for demonstration.
 * Real user management should integrate with the UserAdminDashboard component
 * or use the dedicated user management API endpoints.
 */
export default function AdminUsersTab() {
  const [searchUsers, setSearchUsers] = useState('')
  const { data: stats, isLoading: statsLoading } = useSystemStats({
    refetchInterval: 30000
  })

  return (
    <div className="space-y-6">
      <Card className="shadow-sm">
        <CardHeader className="border-b">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-3 rounded-lg bg-green-50">
                <Users className="h-6 w-6 text-green-600" />
              </div>
              <div>
                <CardTitle>Gestão de Usuários</CardTitle>
                <CardDescription>
                  {statsLoading ? (
                    <Loader2 className="h-4 w-4 animate-spin inline" />
                  ) : (
                    `${stats?.users.total ?? 0} usuários cadastrados, ${stats?.users.active_now ?? 0} ativos`
                  )}
                </CardDescription>
              </div>
            </div>
            <Button>
              <Users className="mr-2 h-4 w-4" />
              Novo Usuário
            </Button>
          </div>
        </CardHeader>
        <CardContent className="pt-6">
          <div className="space-y-4">
            <div className="flex gap-3">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <Input
                  placeholder="Buscar por nome, email ou função..."
                  className="pl-10"
                  value={searchUsers}
                  onChange={(e) => setSearchUsers(e.target.value)}
                />
              </div>
              <Button variant="outline">
                <ListFilter className="mr-2 h-4 w-4" />
                Filtros
              </Button>
            </div>

            <div className="border rounded-lg">
              <div className="grid grid-cols-5 gap-4 p-4 bg-gray-50 font-medium text-sm text-gray-700 border-b">
                <div>Usuário</div>
                <div>Email</div>
                <div>Função</div>
                <div>Status</div>
                <div className="text-right">Ações</div>
              </div>
              <div className="divide-y">
                {[1, 2, 3, 4, 5].map((i) => (
                  <div key={i} className="grid grid-cols-5 gap-4 p-4 hover:bg-gray-50 transition-colors">
                    <div className="flex items-center gap-3">
                      <div className="h-10 w-10 rounded-full bg-blue-100 flex items-center justify-center">
                        <span className="text-sm font-medium text-blue-700">U{i}</span>
                      </div>
                      <div>
                        <p className="font-medium text-sm">Usuário {i}</p>
                        <p className="text-xs text-gray-500">Último acesso há 2h</p>
                      </div>
                    </div>
                    <div className="flex items-center text-sm text-gray-600">
                      usuario{i}@email.com
                    </div>
                    <div className="flex items-center">
                      <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded-full">
                        {i === 1 ? 'Admin' : 'Médico'}
                      </span>
                    </div>
                    <div className="flex items-center">
                      <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded-full">
                        Ativo
                      </span>
                    </div>
                    <div className="flex items-center justify-end gap-2">
                      <Button variant="ghost" size="sm">
                        Editar
                      </Button>
                      <Button variant="ghost" size="sm" className="text-red-600 hover:text-red-700">
                        Remover
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
