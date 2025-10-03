import React from 'react'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import { Badge } from '@/components/ui/badge'

interface PermissionGroup {
  name: string
  label: string
  description: string
  permissions: Permission[]
}

interface Permission {
  id: string
  label: string
  description: string
}

const PERMISSION_GROUPS: PermissionGroup[] = [
  {
    name: 'users',
    label: 'Usuários',
    description: 'Gerenciamento de usuários do sistema',
    permissions: [
      { id: 'users.view', label: 'Visualizar', description: 'Ver lista de usuários' },
      { id: 'users.create', label: 'Criar', description: 'Criar novos usuários' },
      { id: 'users.update', label: 'Editar', description: 'Editar usuários existentes' },
      { id: 'users.delete', label: 'Excluir', description: 'Excluir usuários' },
      { id: 'users.manage_permissions', label: 'Gerenciar Permissões', description: 'Alterar permissões de usuários' }
    ]
  },
  {
    name: 'patients',
    label: 'Pacientes',
    description: 'Gerenciamento de pacientes',
    permissions: [
      { id: 'patients.view', label: 'Visualizar', description: 'Ver lista de pacientes' },
      { id: 'patients.create', label: 'Criar', description: 'Criar novos pacientes' },
      { id: 'patients.update', label: 'Editar', description: 'Editar pacientes existentes' },
      { id: 'patients.delete', label: 'Excluir', description: 'Excluir pacientes' },
      { id: 'patients.export', label: 'Exportar', description: 'Exportar dados de pacientes' }
    ]
  },
  {
    name: 'flows',
    label: 'Fluxos',
    description: 'Gerenciamento de fluxos de conversação',
    permissions: [
      { id: 'flows.view', label: 'Visualizar', description: 'Ver fluxos' },
      { id: 'flows.create', label: 'Criar', description: 'Criar novos fluxos' },
      { id: 'flows.update', label: 'Editar', description: 'Editar fluxos existentes' },
      { id: 'flows.delete', label: 'Excluir', description: 'Excluir fluxos' },
      { id: 'flows.start', label: 'Iniciar', description: 'Iniciar fluxos para pacientes' },
      { id: 'flows.pause', label: 'Pausar', description: 'Pausar fluxos em andamento' }
    ]
  },
  {
    name: 'messages',
    label: 'Mensagens',
    description: 'Gerenciamento de mensagens',
    permissions: [
      { id: 'messages.view', label: 'Visualizar', description: 'Ver mensagens' },
      { id: 'messages.send', label: 'Enviar', description: 'Enviar mensagens' },
      { id: 'messages.retry', label: 'Reenviar', description: 'Reenviar mensagens falhadas' }
    ]
  },
  {
    name: 'analytics',
    label: 'Analytics',
    description: 'Visualização de análises e métricas',
    permissions: [
      { id: 'analytics.view', label: 'Visualizar', description: 'Ver dashboards e métricas' },
      { id: 'analytics.export', label: 'Exportar', description: 'Exportar relatórios' }
    ]
  },
  {
    name: 'settings',
    label: 'Configurações',
    description: 'Configurações do sistema',
    permissions: [
      { id: 'settings.view', label: 'Visualizar', description: 'Ver configurações' },
      { id: 'settings.update', label: 'Atualizar', description: 'Modificar configurações do sistema' },
      { id: 'settings.ai', label: 'IA', description: 'Configurar IA e automação' },
      { id: 'settings.integrations', label: 'Integrações', description: 'Configurar integrações externas' }
    ]
  },
  {
    name: 'audit',
    label: 'Auditoria',
    description: 'Logs e auditoria do sistema',
    permissions: [
      { id: 'audit.view', label: 'Visualizar', description: 'Ver logs de auditoria' },
      { id: 'audit.export', label: 'Exportar', description: 'Exportar logs' }
    ]
  }
]

interface UserPermissionsEditorProps {
  selectedPermissions: string[]
  onChange: (permissions: string[]) => void
  disabled?: boolean
}

export function UserPermissionsEditor({
  selectedPermissions,
  onChange,
  disabled = false
}: UserPermissionsEditorProps) {
  const handlePermissionToggle = (permissionId: string) => {
    if (selectedPermissions.includes(permissionId)) {
      onChange(selectedPermissions.filter(p => p !== permissionId))
    } else {
      onChange([...selectedPermissions, permissionId])
    }
  }

  const handleGroupToggle = (group: PermissionGroup) => {
    const groupPermissionIds = group.permissions.map(p => p.id)
    const allSelected = groupPermissionIds.every(id => selectedPermissions.includes(id))

    if (allSelected) {
      // Deselect all in group
      onChange(selectedPermissions.filter(p => !groupPermissionIds.includes(p)))
    } else {
      // Select all in group
      const newPermissions = [...selectedPermissions]
      groupPermissionIds.forEach(id => {
        if (!newPermissions.includes(id)) {
          newPermissions.push(id)
        }
      })
      onChange(newPermissions)
    }
  }

  const isGroupSelected = (group: PermissionGroup) => {
    const groupPermissionIds = group.permissions.map(p => p.id)
    return groupPermissionIds.every(id => selectedPermissions.includes(id))
  }

  const isGroupPartiallySelected = (group: PermissionGroup) => {
    const groupPermissionIds = group.permissions.map(p => p.id)
    const selectedCount = groupPermissionIds.filter(id => selectedPermissions.includes(id)).length
    return selectedCount > 0 && selectedCount < groupPermissionIds.length
  }

  return (
    <div className="border rounded-lg">
      <div className="p-4 bg-muted/50 border-b flex items-center justify-between">
        <div>
          <p className="font-medium">Permissões do Usuário</p>
          <p className="text-sm text-muted-foreground">
            Selecione as permissões que este usuário deve ter
          </p>
        </div>
        <Badge variant="secondary">
          {selectedPermissions.length} selecionadas
        </Badge>
      </div>

      <ScrollArea className="h-[400px]">
        <div className="p-4 space-y-6">
          {PERMISSION_GROUPS.map((group) => (
            <div key={group.name} className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <div className="flex items-center gap-2">
                    <Checkbox
                      id={`group-${group.name}`}
                      checked={isGroupSelected(group)}
                      onCheckedChange={() => handleGroupToggle(group)}
                      disabled={disabled}
                      className={isGroupPartiallySelected(group) ? 'opacity-50' : ''}
                    />
                    <Label
                      htmlFor={`group-${group.name}`}
                      className="font-semibold cursor-pointer"
                    >
                      {group.label}
                    </Label>
                  </div>
                  <p className="text-sm text-muted-foreground ml-6">
                    {group.description}
                  </p>
                </div>
              </div>

              <div className="ml-6 space-y-2">
                {group.permissions.map((permission) => (
                  <div key={permission.id} className="flex items-start space-x-3">
                    <Checkbox
                      id={permission.id}
                      checked={selectedPermissions.includes(permission.id)}
                      onCheckedChange={() => handlePermissionToggle(permission.id)}
                      disabled={disabled}
                      className="mt-1"
                    />
                    <div className="flex-1">
                      <Label
                        htmlFor={permission.id}
                        className="text-sm font-medium cursor-pointer"
                      >
                        {permission.label}
                      </Label>
                      <p className="text-xs text-muted-foreground">
                        {permission.description}
                      </p>
                    </div>
                  </div>
                ))}
              </div>

              {group !== PERMISSION_GROUPS[PERMISSION_GROUPS.length - 1] && (
                <Separator className="mt-4" />
              )}
            </div>
          ))}
        </div>
      </ScrollArea>
    </div>
  )
}