import React, { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { formatDistanceToNow } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import { Loader2, Shield, Lock, Key, Activity } from 'lucide-react'
import { apiClient } from '@/lib/api-client'
import { updateUserSchema, UpdateUserFormData } from '@/lib/validations/user-schemas'
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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { useToast } from '@/components/ui/use-toast'
import { UserPermissionsEditor } from './UserPermissionsEditor'
import { UserActivityLog } from './UserActivityLog'

interface UserDetailsModalProps {
  user: AdminUser
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function UserDetailsModal({ user, open, onOpenChange }: UserDetailsModalProps) {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [isEditing, setIsEditing] = useState(false)

  const {
    register,
    handleSubmit,
    formState: { errors },
    setValue,
    watch,
    reset
  } = useForm<UpdateUserFormData>({
    resolver: zodResolver(updateUserSchema),
    defaultValues: {
      email: user['email'],
      full_name: user['full_name'] || '',
      role: user['role'],
      permissions: user.permissions,
      is_active: user.is_active,
      two_factor_enabled: user.two_factor_enabled ?? false
    }
  })

  React.useEffect(() => {
    reset({
      email: user['email'],
      full_name: user['full_name'] || '',
      role: user['role'],
      permissions: user.permissions,
      is_active: user.is_active,
      two_factor_enabled: user.two_factor_enabled ?? false
    })
  }, [user, reset])

  const updateMutation = useMutation({
    mutationFn: (data: UpdateUserFormData) => apiClient.adminUsers.update(user['id'], data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
      toast({
        title: 'Usuário atualizado com sucesso',
        description: 'As informações do usuário foram atualizadas.'
      })
      setIsEditing(false)
    },
    onError: (error: unknown) => {
      const message = (error as { data?: { message?: string } }).data?.message || 'Ocorreu um erro inesperado.';
      toast({
        title: 'Erro ao atualizar usuário',
        description: message,
        variant: 'destructive'
      })
    }
  })

  const resetPasswordMutation = useMutation({
    mutationFn: async () => {
      // Generate secure temporary password client-side
      const tempPassword = generateTemporaryPassword()

      // Send password to backend for user update
      await apiClient.adminUsers.resetPassword(user['id'], {
        new_password: tempPassword,
        force_change: true
      })

      // Return generated password for display
      return { temporary_password: tempPassword }
    },
    onSuccess: (data) => {
      toast({
        title: 'Senha resetada com sucesso',
        description: `Senha temporária: ${data.temporary_password}`
      })
    },
    onError: (error: unknown) => {
      const message = (error as { data?: { message?: string } }).data?.message || 'Ocorreu um erro inesperado.';
      toast({
        title: 'Erro ao resetar senha',
        description: message,
        variant: 'destructive'
      })
    }
  })

  const onSubmit = (data: UpdateUserFormData) => {
    updateMutation.mutate(data)
  }

  const handlePermissionsChange = (permissions: string[]) => {
    setValue('permissions', permissions)
  }

  // Generate secure temporary password
  function generateTemporaryPassword(): string {
    const length = 12
    const charset = 'ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789!@#$%^&*'
    const array = new Uint8Array(length)
    crypto.getRandomValues(array)
    return Array.from(array, (byte) => charset[byte % charset.length]).join('')
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

  const isUserLocked = user.locked_until && new Date(user.locked_until) > new Date()

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Detalhes do Usuário</DialogTitle>
          <DialogDescription>
            Visualize e edite as informações do usuário administrativo.
          </DialogDescription>
        </DialogHeader>

        <Tabs defaultValue="details" className="w-full">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="details">Detalhes</TabsTrigger>
            <TabsTrigger value="security">Segurança</TabsTrigger>
            <TabsTrigger value="activity">Atividade</TabsTrigger>
          </TabsList>

          {/* Details Tab */}
          <TabsContent value="details" className="space-y-4 mt-4">
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              <div className="grid gap-4">
                {/* Full Name */}
                <div className="space-y-2">
                  <Label htmlFor="full_name">Nome Completo *</Label>
                  <Input
                    id="full_name"
                    {...register('full_name')}
                    disabled={!isEditing || updateMutation.isPending}
                  />
                  {errors['full_name'] && (
                    <p className="text-sm text-red-500">{errors['full_name']?.['message']}</p>
                  )}
                </div>

                {/* Email */}
                <div className="space-y-2">
                  <Label htmlFor="email">Email *</Label>
                  <Input
                    id="email"
                    type="email"
                    {...register('email')}
                    disabled={!isEditing || updateMutation.isPending}
                  />
                  {errors['email'] && (
                    <p className="text-sm text-red-500">{errors['email']?.['message']}</p>
                  )}
                </div>

                {/* Role */}
                <div className="space-y-2">
                  <Label htmlFor="role">Função *</Label>
                  <Select
                    value={watch('role')}
                    onValueChange={(value: 'doctor' | 'admin') => setValue('role', value)}
                    disabled={!isEditing || updateMutation.isPending}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="doctor">Médico</SelectItem>
                      <SelectItem value="admin">Administrador</SelectItem>
                    </SelectContent>
                  </Select>
                  {errors['role'] && (
                    <p className="text-sm text-red-500">{errors['role']?.['message']}</p>
                  )}
                </div>

                {/* Permissions */}
                <div className="space-y-2">
                  <Label>Permissões</Label>
                  <UserPermissionsEditor
                    selectedPermissions={watch('permissions') || []}
                    onChange={handlePermissionsChange}
                    disabled={!isEditing || updateMutation.isPending}
                  />
                </div>

                <Separator />

                {/* Active Status */}
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label htmlFor="is_active">Usuário Ativo</Label>
                    <p className="text-sm text-muted-foreground">
                      Permite que o usuário faça login no sistema
                    </p>
                  </div>
                  <Switch
                    id="is_active"
                    checked={watch('is_active')}
                    onCheckedChange={(checked) => setValue('is_active', checked)}
                    disabled={!isEditing || updateMutation.isPending}
                  />
                </div>

                {/* 2FA */}
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label htmlFor="two_factor_enabled">Autenticação de Dois Fatores</Label>
                    <p className="text-sm text-muted-foreground">
                      Requer código de verificação adicional no login
                    </p>
                  </div>
                  <Switch
                    id="two_factor_enabled"
                    checked={watch('two_factor_enabled')}
                    onCheckedChange={(checked) => setValue('two_factor_enabled', checked)}
                    disabled={!isEditing || updateMutation.isPending}
                  />
                </div>
              </div>

              <DialogFooter>
                {isEditing ? (
                  <>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => {
                        setIsEditing(false)
                        reset()
                      }}
                      disabled={updateMutation.isPending}
                    >
                      Cancelar
                    </Button>
                    <Button type="submit" disabled={updateMutation.isPending}>
                      {updateMutation.isPending && (
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      )}
                      Salvar Alterações
                    </Button>
                  </>
                ) : (
                  <Button type="button" onClick={() => setIsEditing(true)}>
                    Editar
                  </Button>
                )}
              </DialogFooter>
            </form>
          </TabsContent>

          {/* Security Tab */}
          <TabsContent value="security" className="space-y-4 mt-4">
            <div className="space-y-4">
              <div className="grid gap-4">
                <div className="flex items-center justify-between p-4 border rounded-lg">
                  <div className="flex items-center gap-3">
                    <Shield className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <p className="font-medium">Status de Segurança</p>
                      <p className="text-sm text-muted-foreground">
                        {isUserLocked ? 'Conta bloqueada' : 'Conta ativa'}
                      </p>
                    </div>
                  </div>
                  {isUserLocked ? (
                    <Badge variant="destructive">Bloqueado</Badge>
                  ) : (
                    <Badge className="bg-green-100 text-green-800">Ativo</Badge>
                  )}
                </div>

                <div className="flex items-center justify-between p-4 border rounded-lg">
                  <div className="flex items-center gap-3">
                    <Activity className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <p className="font-medium">Tentativas de Login Falhadas</p>
                      <p className="text-sm text-muted-foreground">
                        Contagem de tentativas recentes
                      </p>
                    </div>
                  </div>
                  <Badge variant={user.failed_login_attempts > 0 ? 'destructive' : 'secondary'}>
                    {user.failed_login_attempts}
                  </Badge>
                </div>

                <div className="flex items-center justify-between p-4 border rounded-lg">
                  <div className="flex items-center gap-3">
                    <Lock className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <p className="font-medium">Último Login</p>
                      <p className="text-sm text-muted-foreground">
                        {formatLastLogin(user.last_login)}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="flex items-center justify-between p-4 border rounded-lg">
                  <div className="flex items-center gap-3">
                    <Key className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <p className="font-medium">Resetar Senha</p>
                      <p className="text-sm text-muted-foreground">
                        Gerar nova senha temporária
                      </p>
                    </div>
                  </div>
                  <Button
                    variant="outline"
                    onClick={() => resetPasswordMutation.mutate()}
                    disabled={resetPasswordMutation.isPending}
                  >
                    {resetPasswordMutation.isPending && (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    )}
                    Resetar
                  </Button>
                </div>
              </div>
            </div>
          </TabsContent>

          {/* Activity Tab */}
          <TabsContent value="activity" className="space-y-4 mt-4">
            <UserActivityLog userId={user['id']} />
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  )
}