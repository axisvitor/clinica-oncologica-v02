import React from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { apiClient } from '@/lib/api-client'
import { createUserSchema, CreateUserFormData } from '@/lib/validations/user-schemas'
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
import { useToast } from '@/components/ui/use-toast'
import { UserPermissionsEditor } from './UserPermissionsEditor'

interface CreateUserModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function CreateUserModal({ open, onOpenChange }: CreateUserModalProps) {
  const { toast } = useToast()
  const queryClient = useQueryClient()

  const {
    register,
    handleSubmit,
    formState: { errors },
    setValue,
    watch,
    reset
  } = useForm<CreateUserFormData>({
    resolver: zodResolver(createUserSchema),
    defaultValues: {
      email: '',
      full_name: '',
      role: 'doctor',
      password: '',
      confirm_password: '',
      permissions: [],
      is_active: true,
      two_factor_enabled: false
    }
  })

  const createMutation = useMutation({
    mutationFn: (data: CreateUserFormData) => {
      const { confirm_password, ...userData } = data
      return apiClient.adminUsers.create(userData)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
      toast({
        title: 'Usuário criado com sucesso',
        description: 'O novo usuário foi adicionado ao sistema.'
      })
      reset()
      onOpenChange(false)
    },
    onError: (error: unknown) => {
      const message = (error as { data?: { message?: string } }).data?.message || 'Ocorreu um erro inesperado.';
      toast({
        title: 'Erro ao criar usuário',
        description: message,
        variant: 'destructive'
      })
    }
  })

  const onSubmit = (data: CreateUserFormData) => {
    createMutation.mutate(data)
  }

  const handlePermissionsChange = (permissions: string[]) => {
    setValue('permissions', permissions)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-[95vw] max-w-2xl max-h-[90vh] overflow-y-auto px-4 sm:px-6">
        <DialogHeader>
          <DialogTitle>Criar Novo Usuário</DialogTitle>
          <DialogDescription>
            Preencha os dados abaixo para criar um novo usuário administrativo.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
          <div className="grid gap-4">
            {/* Full Name */}
            <div className="space-y-2">
              <Label htmlFor="full_name">Nome Completo *</Label>
              <Input
                id="full_name"
                {...register('full_name')}
                placeholder="Ex: João Silva"
                disabled={createMutation.isPending}
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
                placeholder="Ex: joao@example.com"
                disabled={createMutation.isPending}
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
                disabled={createMutation.isPending}
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

            {/* Password */}
            <div className="space-y-2">
              <Label htmlFor="password">Senha *</Label>
              <Input
                id="password"
                type="password"
                {...register('password')}
                placeholder="Mínimo 8 caracteres"
                disabled={createMutation.isPending}
              />
              {errors['password'] && (
                <p className="text-sm text-red-500">{errors['password']?.['message']}</p>
              )}
            </div>

            {/* Confirm Password */}
            <div className="space-y-2">
              <Label htmlFor="confirm_password">Confirmar Senha *</Label>
              <Input
                id="confirm_password"
                type="password"
                {...register('confirm_password')}
                placeholder="Digite a senha novamente"
                disabled={createMutation.isPending}
              />
              {errors['confirm_password'] && (
                <p className="text-sm text-red-500">{errors['confirm_password']?.['message']}</p>
              )}
            </div>

            {/* Permissions */}
            <div className="space-y-2">
              <Label>Permissões</Label>
              <UserPermissionsEditor
                selectedPermissions={watch('permissions') || []}
                onChange={handlePermissionsChange}
                disabled={createMutation.isPending}
              />
            </div>

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
                disabled={createMutation.isPending}
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
                disabled={createMutation.isPending}
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={createMutation.isPending}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={createMutation.isPending}>
              {createMutation.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Criar Usuário
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}