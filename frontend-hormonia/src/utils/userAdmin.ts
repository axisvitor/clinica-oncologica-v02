import { AdminUser } from '@/types/admin'
import { ROLE_LABELS, ROLE_COLORS, getRoleLabel, getRoleColor } from '@/types/shared'

/**
 * Utility functions for user administration
 */

export function getInitials(name: string): string {
  return name
    .split(' ')
    .map(n => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)
}

export function getRoleBadgeVariant(role: string): 'default' | 'secondary' | 'destructive' | 'outline' {
  // Map roles to badge variants for UI components that need specific variants
  const roleKey = role.toLowerCase()
  if (roleKey === 'super_admin') return 'default'
  if (roleKey === 'admin') return 'default'
  if (roleKey === 'doctor') return 'secondary'
  return 'outline'
}

export function getRoleDisplayName(role: string): string {
  return getRoleLabel(role)
}

export function getStatusBadgeVariant(user: AdminUser): 'default' | 'secondary' | 'destructive' {
  if (user.locked_until && new Date(user.locked_until) > new Date()) {
    return 'destructive'
  }
  if (!user.is_active) {
    return 'secondary'
  }
  return 'default'
}

export function getStatusDisplayName(user: AdminUser): string {
  if (user.locked_until && new Date(user.locked_until) > new Date()) {
    return 'Bloqueado'
  }
  if (!user.is_active) {
    return 'Inativo'
  }
  return 'Ativo'
}

export function isUserLocked(user: AdminUser): boolean {
  return !!(user.locked_until && new Date(user.locked_until) > new Date())
}

export function formatUserActivity(action: string): string {
  const activityMap: Record<string, string> = {
    'login': 'Fez login no sistema',
    'logout': 'Fez logout do sistema',
    'failed_login': 'Tentativa de login falhada',
    'password_change': 'Alterou a senha',
    'password_reset': 'Redefiniu a senha',
    'permission_change': 'Permissões foram alteradas',
    'role_change': 'Função foi alterada',
    'create_user': 'Criou um novo usuário',
    'update_user': 'Atualizou informações de usuário',
    'delete_user': 'Excluiu um usuário',
    'view_patient': 'Acessou dados de paciente',
    'create_patient': 'Criou um novo paciente',
    'update_patient': 'Atualizou informações de paciente',
    'delete_patient': 'Excluiu um paciente',
    'settings_change': 'Modificou configurações do sistema',
    'report_generated': 'Gerou um relatório',
    'export_data': 'Exportou dados',
    'audit_access': 'Acessou logs de auditoria',
    'security_event': 'Evento de segurança registrado'
  }

  return activityMap[action.toLowerCase()] || action.replace('_', ' ')
}

export function getActivitySeverity(action: string): 'low' | 'medium' | 'high' {
  const highSeverityActions = [
    'failed_login',
    'delete_user',
    'delete_patient',
    'permission_change',
    'security_event'
  ]

  const mediumSeverityActions = [
    'create_user',
    'create_patient',
    'update_user',
    'update_patient',
    'role_change',
    'password_reset',
    'settings_change'
  ]

  if (highSeverityActions.includes(action.toLowerCase())) {
    return 'high'
  }

  if (mediumSeverityActions.includes(action.toLowerCase())) {
    return 'medium'
  }

  return 'low'
}

export function validatePassword(password: string): {
  isValid: boolean
  errors: string[]
  strength: 'weak' | 'medium' | 'strong'
} {
  const errors: string[] = []
  let strength: 'weak' | 'medium' | 'strong' = 'weak'

  if (password.length < 8) {
    errors.push('Senha deve ter pelo menos 8 caracteres')
  }

  if (!/[a-z]/.test(password)) {
    errors.push('Senha deve conter pelo menos uma letra minúscula')
  }

  if (!/[A-Z]/.test(password)) {
    errors.push('Senha deve conter pelo menos uma letra maiúscula')
  }

  if (!/\d/.test(password)) {
    errors.push('Senha deve conter pelo menos um número')
  }

  if (!/[^A-Za-z\d]/.test(password)) {
    errors.push('Senha deve conter pelo menos um caractere especial')
  }

  // Calculate strength
  let score = 0
  if (password.length >= 8) score++
  if (/[a-z]/.test(password)) score++
  if (/[A-Z]/.test(password)) score++
  if (/\d/.test(password)) score++
  if (/[^A-Za-z\d]/.test(password)) score++

  if (score >= 4) {
    strength = 'strong'
  } else if (score >= 2) {
    strength = 'medium'
  }

  return {
    isValid: errors.length === 0,
    errors,
    strength
  }
}

export function validateEmail(email: string): boolean {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  return emailRegex.test(email)
}

export function formatPermissionName(permission: string): string {
  const parts = permission.split('.')
  if (parts.length >= 2) {
    const resource = parts[1]
    const action = parts[2] || 'access'

    const resourceNames: Record<string, string> = {
      users: 'Usuários',
      patients: 'Pacientes',
      flows: 'Fluxos',
      settings: 'Configurações',
      analytics: 'Analytics',
      reports: 'Relatórios',
      audit: 'Auditoria'
    }

    const actionNames: Record<string, string> = {
      create: 'Criar',
      read: 'Visualizar',
      update: 'Editar',
      delete: 'Excluir',
      export: 'Exportar',
      access: 'Acessar'
    }

    const resourceName = resourceNames[resource as keyof typeof resourceNames] || resource
    const actionName = actionNames[action as keyof typeof actionNames] || action

    return `${actionName} ${resourceName}`
  }

  return permission
}

export function sortUsers(users: AdminUser[], sortBy: string, sortOrder: 'asc' | 'desc'): AdminUser[] {
  return [...users].sort((a, b) => {
    let aVal: any = a[sortBy as keyof AdminUser]
    let bVal: any = b[sortBy as keyof AdminUser]

    // Handle date sorting
    if (sortBy === 'created_at' || sortBy === 'last_login') {
      aVal = aVal ? new Date(aVal).getTime() : 0
      bVal = bVal ? new Date(bVal).getTime() : 0
    }

    // Handle string sorting
    if (typeof aVal === 'string') {
      aVal = aVal.toLowerCase()
      bVal = bVal.toLowerCase()
    }

    if (sortOrder === 'asc') {
      return aVal > bVal ? 1 : -1
    } else {
      return aVal < bVal ? 1 : -1
    }
  })
}

export function filterUsers(
  users: AdminUser[],
  filters: {
    search?: string
    role?: string
    status?: string
    twoFactor?: string
  }
): AdminUser[] {
  return users.filter(user => {
    // Search filter
    if (filters.search) {
      const searchLower = filters.search.toLowerCase()
      const matchesSearch =
        user['full_name'].toLowerCase().includes(searchLower) ||
        user['email'].toLowerCase().includes(searchLower)
      if (!matchesSearch) return false
    }

    // Role filter
    if (filters.role && filters.role !== 'all' && user['role'] !== filters.role) {
      return false
    }

    // Status filter
    if (filters.status && filters.status !== 'all') {
      if (filters.status === 'active' && !user.is_active) return false
      if (filters.status === 'inactive' && user.is_active) return false
      if (filters.status === 'locked' && !isUserLocked(user)) return false
    }

    // Two factor filter
    if (filters.twoFactor && filters.twoFactor !== 'all') {
      if (filters.twoFactor === 'enabled' && !user.two_factor_enabled) return false
      if (filters.twoFactor === 'disabled' && user.two_factor_enabled) return false
    }

    return true
  })
}

export function exportUsersToCSV(users: AdminUser[]): string {
  const headers = [
    'ID',
    'Nome Completo',
    'Email',
    'Função',
    'Status',
    '2FA Ativo',
    'Tentativas de Login Falhadas',
    'Último Login',
    'Data de Criação',
    'Permissões'
  ]

  const rows = users.map(user => [
    user['id'],
    user['full_name'],
    user['email'],
    getRoleLabel(user['role']),
    getStatusDisplayName(user),
    user.two_factor_enabled ? 'Sim' : 'Não',
    user.failed_login_attempts.toString(),
    user.last_login ? new Date(user.last_login).toLocaleString('pt-BR') : 'Nunca',
    new Date(user.created_at).toLocaleString('pt-BR'),
    user.permissions.join('; ')
  ])

  const csvContent = [
    headers.join(','),
    ...rows.map(row => row.map(cell => `"${cell}"`).join(','))
  ].join('\n')

  return csvContent
}

export function downloadCSV(content: string, filename: string): void {
  const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')

  if (link.download !== undefined) {
    const url = URL.createObjectURL(blob)
    link.setAttribute('href', url)
    link.setAttribute('download', filename)
    link.style.visibility = 'hidden'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }
}