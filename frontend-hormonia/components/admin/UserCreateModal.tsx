import React, { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Eye, EyeOff, AlertCircle, Check } from 'lucide-react'
import { apiClient } from '@/lib/api-client'
import { AdminUser } from '@/types/admin'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { useToast } from '@/components/ui/use-toast'
import { LoadingSpinner } from '@/components/ui/loading-spinner'

interface UserCreateModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

interface CreateUserForm {
  email: string
  full_name: string
  password: string
  confirm_password: string
  role: 'doctor' | 'admin'
  permissions: string[]
  is_active: boolean
  two_factor_enabled: boolean
  notes?: string
}

const AVAILABLE_PERMISSIONS = [
  { id: 'admin.users.create', label: 'Criar Usuários', category: 'Usuários' },
  { id: 'admin.users.read', label: 'Visualizar Usuários', category: 'Usuários' },
  { id: 'admin.users.update', label: 'Editar Usuários', category: 'Usuários' },
  { id: 'admin.users.delete', label: 'Excluir Usuários', category: 'Usuários' },
  { id: 'admin.patients.create', label: 'Criar Pacientes', category: 'Pacientes' },
  { id: 'admin.patients.read', label: 'Visualizar Pacientes', category: 'Pacientes' },
  { id: 'admin.patients.update', label: 'Editar Pacientes', category: 'Pacientes' },
  { id: 'admin.patients.delete', label: 'Excluir Pacientes', category: 'Pacientes' },
  { id: 'admin.flows.create', label: 'Criar Fluxos', category: 'Fluxos' },
  { id: 'admin.flows.read', label: 'Visualizar Fluxos', category: 'Fluxos' },
  { id: 'admin.flows.update', label: 'Editar Fluxos', category: 'Fluxos' },
  { id: 'admin.flows.delete', label: 'Excluir Fluxos', category: 'Fluxos' },
  { id: 'admin.settings.read', label: 'Visualizar Configurações', category: 'Sistema' },
  { id: 'admin.settings.update', label: 'Editar Configurações', category: 'Sistema' },
  { id: 'admin.audit.read', label: 'Visualizar Auditoria', category: 'Sistema' },
  { id: 'admin.analytics.read', label: 'Visualizar Analytics', category: 'Sistema' },
]

export function UserCreateModal({ open, onOpenChange }: UserCreateModalProps) {
  const { toast } = useToast()
  const queryClient = useQueryClient()

  const [form, setForm] = useState<CreateUserForm>({
    email: '',
    full_name: '',
    password: '',
    confirm_password: '',
    role: 'admin',
    permissions: [],
    is_active: true,
    two_factor_enabled: false,
    notes: ''
  })

  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({})

  const createUserMutation = useMutation({
    mutationFn: async (userData: Partial<AdminUser>) => {
      return apiClient.adminUsers.create(userData)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
      toast({
        title: 'Usuário criado com sucesso',
        description: 'O novo usuário foi adicionado ao sistema.',
      })
      onOpenChange(false)
      resetForm()
    },
    onError: (error: any) => {
      toast({
        title: 'Erro ao criar usuário',
        description: error?.data?.message || 'Ocorreu um erro inesperado.',
        variant: 'destructive'
      })
    }
  })

  const resetForm = () => {
    setForm({
      email: '',
      full_name: '',
      password: '',
      confirm_password: '',
      role: 'admin',
      permissions: [],
      is_active: true,
      two_factor_enabled: false,
      notes: ''
    })
    setValidationErrors({})
  }

  const validateForm = (): boolean => {
    const errors: Record<string, string> = {}

    // Email validation
    if (!form['email']) {
      errors['email'] = 'Email é obrigatório'
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form['email'])) {
      errors['email'] = 'Email inválido'
    }

    // Name validation
    if (!form['full_name'].trim()) {
      errors['full_name'] = 'Nome completo é obrigatório'
    } else if (form['full_name'].trim().length < 2) {
      errors['full_name'] = 'Nome deve ter pelo menos 2 caracteres'
    }

    // Password validation
    if (!form['password']) {
      errors['password'] = 'Senha é obrigatória'
    } else if (form['password'].length < 8) {
      errors['password'] = 'Senha deve ter pelo menos 8 caracteres'
    } else if (!/(?=.*[a-z])(?=.*[A-Z])(?=.*\d)/.test(form['password'])) {
      errors['password'] = 'Senha deve conter pelo menos uma letra minúscula, uma maiúscula e um número'
    }

    // Confirm password validation
    if (form['password'] !== form['confirm_password']) {
      errors['confirm_password'] = 'Senhas não coincidem'
    }

    // Role validation
    if (!form['role']) {
      errors['role'] = 'Função é obrigatória'
    }

    setValidationErrors(errors)
    return Object.keys(errors).length === 0
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    if (!validateForm()) return

    const userData = {
      email: form['email'].trim(),
      full_name: form['full_name'].trim(),
      password: form['password'],
      role: form['role'],
      permissions: form.permissions,
      is_active: form.is_active,
      two_factor_enabled: form.two_factor_enabled,
      notes: form.notes?.trim() || undefined
    }

    createUserMutation.mutate(userData)
  }

  const togglePermission = (permissionId: string) => {
    setForm(prev => ({
      ...prev,
      permissions: prev.permissions.includes(permissionId)
        ? prev.permissions.filter(p => p !== permissionId)
        : [...prev.permissions, permissionId]
    }))
  }

  const setRolePermissions = (role: 'doctor' | 'admin') => {
    let defaultPermissions: string[] = []

    if (role === 'admin') {
      defaultPermissions = [
        'admin.users.read',
        'admin.patients.create',
        'admin.patients.read',
        'admin.patients.update',
        'admin.flows.create',
        'admin.flows.read',
        'admin.flows.update',
        'admin.settings.read',
        'admin.analytics.read'
      ]
    } else if (role === 'doctor') {
      defaultPermissions = [
        'admin.patients.create',
        'admin.patients.read',
        'admin.patients.update',
        'admin.flows.read',
        'admin.analytics.read'
      ]
    }

    setForm(prev => ({
      ...prev,
      role,
      permissions: defaultPermissions
    }))
  }

  const getPasswordStrength = (password: string) => {
    let score = 0
    if (password.length >= 8) score++
    if (/[a-z]/.test(password)) score++
    if (/[A-Z]/.test(password)) score++
    if (/\d/.test(password)) score++
    if (/[^A-Za-z\d]/.test(password)) score++

    return { score, label: ['Muito Fraca', 'Fraca', 'Regular', 'Boa', 'Forte'][score] }
  }

  const passwordStrength = getPasswordStrength(form['password'])

  const permissionsByCategory = AVAILABLE_PERMISSIONS.reduce((acc, permission) => {
    if (!acc[permission.category]) {
      acc[permission.category] = []
    }
    // acc[permission.category] is guaranteed to exist now
    acc[permission.category]!.push(permission)
    return acc
  }, {} as Record<string, typeof AVAILABLE_PERMISSIONS>)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Criar Novo Usuário</DialogTitle>
          <DialogDescription>
            Adicione um novo usuário ao sistema com as permissões adequadas.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Basic Information */}
          <div className="space-y-4">
            <h3 className="text-sm font-medium text-gray-900">Informações Básicas</h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="email">Email *</Label>
                <Input
                  id="email"
                  type="email"
                  value={form['email']}
                  onChange={(e) => setForm(prev => ({ ...prev, email: e.target.value }))}
                  className={validationErrors['email'] ? 'border-red-500' : ''}
                />
                {validationErrors['email'] && (
                  <p className="text-sm text-red-600">{validationErrors['email']}</p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="full_name">Nome Completo *</Label>
                <Input
                  id="full_name"
                  value={form['full_name']}
                  onChange={(e) => setForm(prev => ({ ...prev, full_name: e.target.value }))}
                  className={validationErrors['full_name'] ? 'border-red-500' : ''}
                />
                {validationErrors['full_name'] && (
                  <p className="text-sm text-red-600">{validationErrors['full_name']}</p>
                )}
              </div>
            </div>
          </div>

          {/* Password */}
          <div className="space-y-4">
            <h3 className="text-sm font-medium text-gray-900">Senha</h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="password">Senha *</Label>
                <div className="relative">
                  <Input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    value={form['password']}
                    onChange={(e) => setForm(prev => ({ ...prev, password: e.target.value }))}
                    className={validationErrors['password'] ? 'border-red-500' : ''}
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="absolute right-0 top-0 h-full px-3 py-2 hover:bg-transparent"
                    onClick={() => setShowPassword(!showPassword)}
                  >
                    {showPassword ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </Button>
                </div>
                {form['password'] && (
                  <div className="flex items-center gap-2">
                    <div className={`h-2 w-full rounded-full ${
                      passwordStrength.score <= 2 ? 'bg-red-200' :
                      passwordStrength.score === 3 ? 'bg-yellow-200' : 'bg-green-200'
                    }`}>
                      <div
                        className={`h-2 rounded-full transition-all ${
                          passwordStrength.score <= 2 ? 'bg-red-500' :
                          passwordStrength.score === 3 ? 'bg-yellow-500' : 'bg-green-500'
                        }`}
                        style={{ width: `${(passwordStrength.score / 5) * 100}%` }}
                      />
                    </div>
                    <span className="text-xs text-gray-500">{passwordStrength.label}</span>
                  </div>
                )}
                {validationErrors['password'] && (
                  <p className="text-sm text-red-600">{validationErrors['password']}</p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="confirm_password">Confirmar Senha *</Label>
                <div className="relative">
                  <Input
                    id="confirm_password"
                    type={showConfirmPassword ? 'text' : 'password'}
                    value={form['confirm_password']}
                    onChange={(e) => setForm(prev => ({ ...prev, confirm_password: e.target.value }))}
                    className={validationErrors['confirm_password'] ? 'border-red-500' : ''}
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="absolute right-0 top-0 h-full px-3 py-2 hover:bg-transparent"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  >
                    {showConfirmPassword ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </Button>
                </div>
                {validationErrors['confirm_password'] && (
                  <p className="text-sm text-red-600">{validationErrors['confirm_password']}</p>
                )}
              </div>
            </div>
          </div>

          {/* Role and Status */}
          <div className="space-y-4">
            <h3 className="text-sm font-medium text-gray-900">Função e Status</h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="role">Função *</Label>
                <Select value={form['role']} onValueChange={(value: 'doctor' | 'admin') => setRolePermissions(value)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="doctor">Médico</SelectItem>
                    <SelectItem value="admin">Administrador</SelectItem>
                  </SelectContent>
                </Select>
                {validationErrors['role'] && (
                  <p className="text-sm text-red-600">{validationErrors['role']}</p>
                )}
              </div>

              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <Label htmlFor="is_active">Usuário Ativo</Label>
                  <Switch
                    id="is_active"
                    checked={form.is_active}
                    onCheckedChange={(checked) => setForm(prev => ({ ...prev, is_active: checked }))}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <Label htmlFor="two_factor_enabled">Ativar 2FA</Label>
                  <Switch
                    id="two_factor_enabled"
                    checked={form.two_factor_enabled}
                    onCheckedChange={(checked) => setForm(prev => ({ ...prev, two_factor_enabled: checked }))}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Permissions */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium text-gray-900">Permissões</h3>
              <Badge variant="secondary">{form.permissions.length} selecionadas</Badge>
            </div>

            <div className="space-y-4 max-h-48 overflow-y-auto border rounded-lg p-4">
              {Object.entries(permissionsByCategory).map(([category, permissions]) => (
                <div key={category} className="space-y-2">
                  <h4 className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                    {category}
                  </h4>
                  <div className="grid grid-cols-1 gap-2">
                    {permissions.map((permission) => (
                      <div key={permission.id} className="flex items-center space-x-2">
                        <input
                          type="checkbox"
                          id={permission.id}
                          checked={form.permissions.includes(permission.id)}
                          onChange={() => togglePermission(permission.id)}
                          className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                        />
                        <Label htmlFor={permission.id} className="text-sm">
                          {permission.label}
                        </Label>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Notes */}
          <div className="space-y-2">
            <Label htmlFor="notes">Observações</Label>
            <Textarea
              id="notes"
              value={form.notes}
              onChange={(e) => setForm(prev => ({ ...prev, notes: e.target.value }))}
              placeholder="Observações adicionais sobre o usuário..."
              rows={3}
            />
          </div>

          {/* Submit */}
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={createUserMutation.isPending}
            >
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={createUserMutation.isPending}
            >
              {createUserMutation.isPending ? (
                <>
                  <LoadingSpinner size="sm" className="mr-2" />
                  Criando...
                </>
              ) : (
                <>
                  <Check className="h-4 w-4 mr-2" />
                  Criar Usuário
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}