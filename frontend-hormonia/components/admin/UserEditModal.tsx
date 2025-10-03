import React, { useState, useEffect } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Eye, EyeOff, Save, RotateCcw } from 'lucide-react'
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useToast } from '@/components/ui/use-toast'
import { LoadingSpinner } from '@/components/ui/loading-spinner'

interface UserEditModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  user: AdminUser | null
}

interface EditUserForm {
  email: string
  full_name: string
  role: 'doctor' | 'admin'
  is_active: boolean
  two_factor_enabled: boolean
  notes?: string
  new_password?: string
  confirm_password?: string
}

export function UserEditModal({ open, onOpenChange, user }: UserEditModalProps) {
  const { toast } = useToast()
  const queryClient = useQueryClient()

  const [form, setForm] = useState<EditUserForm>({
    email: '',
    full_name: '',
    role: 'admin',
    is_active: true,
    two_factor_enabled: false,
    notes: '',
    new_password: '',
    confirm_password: ''
  })

  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({})
  const [hasChanges, setHasChanges] = useState(false)

  // Load user data into form when user changes
  useEffect(() => {
    if (user) {
      setForm({
        email: user['email'],
        full_name: user['full_name'],
        role: user['role'] as any,
        is_active: user.is_active,
        two_factor_enabled: user.two_factor_enabled,
        notes: '',
        new_password: '',
        confirm_password: ''
      })
      setHasChanges(false)
      setValidationErrors({})
    }
  }, [user])

  // Track changes
  useEffect(() => {
    if (!user) return

    const hasFormChanges =
      form['email'] !== user['email'] ||
      form['full_name'] !== user['full_name'] ||
      form.role !== (user['role'] as any) ||
      form.is_active !== user.is_active ||
      form.two_factor_enabled !== user.two_factor_enabled ||
      form['new_password'] !== '' ||
      form.notes !== ''

    setHasChanges(hasFormChanges)
  }, [form, user])

  const updateUserMutation = useMutation({
    mutationFn: async ({ id, userData }: { id: string, userData: Partial<AdminUser> }) => {
      return apiClient.adminUsers.update(id, userData)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
      queryClient.invalidateQueries({ queryKey: ['admin-user', user?.id] })
      toast({
        title: 'Usuário atualizado com sucesso',
        description: 'As alterações foram salvas.',
      })
      onOpenChange(false)
    },
    onError: (error: any) => {
      toast({
        title: 'Erro ao atualizar usuário',
        description: error.data?.message || 'Ocorreu um erro inesperado.',
        variant: 'destructive'
      })
    }
  })

  const resetPasswordMutation = useMutation({
    mutationFn: async (id: string) => {
      return apiClient.adminUsers.resetPassword(id)
    },
    onSuccess: (response) => {
      toast({
        title: 'Senha redefinida com sucesso',
        description: `Nova senha temporária: ${response.temporary_password}`,
      })
    },
    onError: (error: any) => {
      toast({
        title: 'Erro ao redefinir senha',
        description: error.data?.message || 'Ocorreu um erro inesperado.',
        variant: 'destructive'
      })
    }
  })

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

    // Password validation (only if provided)
    if (form['new_password']) {
      if (form['new_password'].length < 8) {
        errors['new_password'] = 'Senha deve ter pelo menos 8 caracteres'
      } else if (!/(?=.*[a-z])(?=.*[A-Z])(?=.*\d)/.test(form['new_password'])) {
        errors['new_password'] = 'Senha deve conter pelo menos uma letra minúscula, uma maiúscula e um número'
      }

      // Confirm password validation
      if (form['new_password'] !== form['confirm_password']) {
        errors['confirm_password'] = 'Senhas não coincidem'
      }
    }

    setValidationErrors(errors)
    return Object.keys(errors).length === 0
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    if (!user || !validateForm()) return

    const userData: Partial<AdminUser> = {
      email: form['email'].trim(),
      full_name: form['full_name'].trim(),
      role: form.role,
      is_active: form.is_active,
      two_factor_enabled: form.two_factor_enabled,
    }

    // Add password if provided
    if (form['new_password']) {
      userData.password = form['new_password']
    }

    updateUserMutation.mutate({ id: user['id'], userData })
  }

  const handleResetPassword = () => {
    if (!user) return
    resetPasswordMutation.mutate(user['id'])
  }

  const resetForm = () => {
    if (user) {
      setForm({
        email: user['email'],
        full_name: user['full_name'],
        role: user['role'] as any,
        is_active: user.is_active,
        two_factor_enabled: user.two_factor_enabled,
        notes: '',
        new_password: '',
        confirm_password: ''
      })
      setValidationErrors({})
    }
  }

  if (!user) return null

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Editar Usuário</DialogTitle>
          <DialogDescription>
            Edite as informações do usuário {user['full_name']}
          </DialogDescription>
        </DialogHeader>

        <Tabs defaultValue="basic" className="space-y-4">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="basic">Informações Básicas</TabsTrigger>
            <TabsTrigger value="security">Segurança</TabsTrigger>
            <TabsTrigger value="activity">Atividade</TabsTrigger>
          </TabsList>

          <form onSubmit={handleSubmit}>
            <TabsContent value="basic" className="space-y-4">
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

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="role">Função *</Label>
                  <Select value={form.role} onValueChange={(value: 'doctor' | 'admin') => setForm(prev => ({ ...prev, role: value }))}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="doctor">Médico</SelectItem>
                      <SelectItem value="admin">Administrador</SelectItem>
                    </SelectContent>
                  </Select>
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
                    <Label htmlFor="two_factor_enabled">2FA Ativo</Label>
                    <Switch
                      id="two_factor_enabled"
                      checked={form.two_factor_enabled}
                      onCheckedChange={(checked) => setForm(prev => ({ ...prev, two_factor_enabled: checked }))}
                    />
                  </div>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="notes">Observações</Label>
                <Textarea
                  id="notes"
                  value={form.notes}
                  onChange={(e) => setForm(prev => ({ ...prev, notes: e.target.value }))}
                  placeholder="Observações sobre o usuário..."
                  rows={3}
                />
              </div>
            </TabsContent>

            <TabsContent value="security" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Alterar Senha</CardTitle>
                  <CardDescription>
                    Deixe em branco para manter a senha atual
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="new_password">Nova Senha</Label>
                      <div className="relative">
                        <Input
                          id="new_password"
                          type={showPassword ? 'text' : 'password'}
                          value={form['new_password']}
                          onChange={(e) => setForm(prev => ({ ...prev, new_password: e.target.value }))}
                          className={validationErrors['new_password'] ? 'border-red-500' : ''}
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
                      {validationErrors['new_password'] && (
                        <p className="text-sm text-red-600">{validationErrors['new_password']}</p>
                      )}
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="confirm_password">Confirmar Nova Senha</Label>
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
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Redefinir Senha</CardTitle>
                  <CardDescription>
                    Gera uma nova senha temporária para o usuário
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={handleResetPassword}
                    disabled={resetPasswordMutation.isPending}
                  >
                    {resetPasswordMutation.isPending ? (
                      <>
                        <LoadingSpinner size="sm" className="mr-2" />
                        Redefinindo...
                      </>
                    ) : (
                      <>
                        <RotateCcw className="h-4 w-4 mr-2" />
                        Redefinir Senha
                      </>
                    )}
                  </Button>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Informações de Segurança</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Tentativas de Login Falhadas:</span>
                    <Badge variant={user.failed_login_attempts > 0 ? 'destructive' : 'secondary'}>
                      {user.failed_login_attempts}
                    </Badge>
                  </div>

                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Status da Conta:</span>
                    <Badge variant={user.is_active ? 'default' : 'secondary'}>
                      {user.is_active ? 'Ativa' : 'Inativa'}
                    </Badge>
                  </div>

                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Bloqueio:</span>
                    <Badge variant={user.locked_until && new Date(user.locked_until) > new Date() ? 'destructive' : 'secondary'}>
                      {user.locked_until && new Date(user.locked_until) > new Date() ? 'Bloqueada' : 'Desbloqueada'}
                    </Badge>
                  </div>

                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Último Login:</span>
                    <span className="text-sm text-gray-900">
                      {user.last_login ? new Date(user.last_login).toLocaleString('pt-BR') : 'Nunca'}
                    </span>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="activity" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Informações da Conta</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">ID do Usuário:</span>
                    <span className="text-sm font-mono text-gray-900">{user['id']}</span>
                  </div>

                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Criado em:</span>
                    <span className="text-sm text-gray-900">
                      {new Date(user.created_at).toLocaleString('pt-BR')}
                    </span>
                  </div>

                  <div className="flex justify-between items-center">
                    <span className="text-sm text-gray-600">Permissões:</span>
                    <Badge variant="secondary">
                      {user.permissions.length} permissões
                    </Badge>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Permissões Atuais</CardTitle>
                  <CardDescription>
                    Lista de todas as permissões atribuídas ao usuário
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap gap-2">
                    {user.permissions.length > 0 ? (
                      user.permissions.map((permission) => (
                        <Badge key={permission} variant="outline" className="text-xs">
                          {permission}
                        </Badge>
                      ))
                    ) : (
                      <p className="text-sm text-gray-500">Nenhuma permissão específica atribuída</p>
                    )}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <DialogFooter className="mt-6">
              <div className="flex justify-between w-full">
                <Button
                  type="button"
                  variant="outline"
                  onClick={resetForm}
                  disabled={!hasChanges || updateUserMutation.isPending}
                >
                  <RotateCcw className="h-4 w-4 mr-2" />
                  Reverter
                </Button>

                <div className="flex gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => onOpenChange(false)}
                    disabled={updateUserMutation.isPending}
                  >
                    Cancelar
                  </Button>
                  <Button
                    type="submit"
                    disabled={!hasChanges || updateUserMutation.isPending}
                  >
                    {updateUserMutation.isPending ? (
                      <>
                        <LoadingSpinner size="sm" className="mr-2" />
                        Salvando...
                      </>
                    ) : (
                      <>
                        <Save className="h-4 w-4 mr-2" />
                        Salvar Alterações
                      </>
                    )}
                  </Button>
                </div>
              </div>
            </DialogFooter>
          </form>
        </Tabs>
      </DialogContent>
    </Dialog>
  )
}