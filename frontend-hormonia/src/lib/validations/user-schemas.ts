import { z } from 'zod'

export const createUserSchema = z.object({
  email: z.string()
    .min(1, 'Email é obrigatório')
    .email('Email inválido'),
  full_name: z.string()
    .min(3, 'Nome deve ter pelo menos 3 caracteres')
    .max(100, 'Nome deve ter no máximo 100 caracteres'),
  role: z.enum(['super_admin', 'admin', 'doctor', 'nurse', 'patient', 'researcher', 'coordinator'], {
    required_error: 'Função é obrigatória'
  }),
  password: z.string()
    .min(8, 'Senha deve ter pelo menos 8 caracteres')
    .regex(/[A-Z]/, 'Senha deve conter pelo menos uma letra maiúscula')
    .regex(/[a-z]/, 'Senha deve conter pelo menos uma letra minúscula')
    .regex(/[0-9]/, 'Senha deve conter pelo menos um número')
    .regex(/[^A-Za-z0-9]/, 'Senha deve conter pelo menos um caractere especial'),
  confirm_password: z.string()
    .min(1, 'Confirmação de senha é obrigatória'),
  permissions: z.array(z.string()).default([]),
  is_active: z.boolean().default(true),
  two_factor_enabled: z.boolean().default(false)
}).refine((data) => data['password'] === data['confirm_password'], {
  message: 'As senhas não coincidem',
  path: ['confirm_password']
})

export const updateUserSchema = z.object({
  email: z.string()
    .min(1, 'Email é obrigatório')
    .email('Email inválido'),
  full_name: z.string()
    .min(3, 'Nome deve ter pelo menos 3 caracteres')
    .max(100, 'Nome deve ter no máximo 100 caracteres'),
  role: z.enum(['super_admin', 'admin', 'doctor', 'nurse', 'patient', 'researcher', 'coordinator'], {
    required_error: 'Função é obrigatória'
  }),
  permissions: z.array(z.string()).default([]),
  is_active: z.boolean().default(true),
  two_factor_enabled: z.boolean().default(false)
})

export const updatePasswordSchema = z.object({
  current_password: z.string().min(1, 'Senha atual é obrigatória'),
  new_password: z.string()
    .min(8, 'Nova senha deve ter pelo menos 8 caracteres')
    .regex(/[A-Z]/, 'Nova senha deve conter pelo menos uma letra maiúscula')
    .regex(/[a-z]/, 'Nova senha deve conter pelo menos uma letra minúscula')
    .regex(/[0-9]/, 'Nova senha deve conter pelo menos um número')
    .regex(/[^A-Za-z0-9]/, 'Nova senha deve conter pelo menos um caractere especial'),
  confirm_new_password: z.string()
    .min(1, 'Confirmação de senha é obrigatória')
}).refine((data) => data['new_password'] === data['confirm_new_password'], {
  message: 'As senhas não coincidem',
  path: ['confirm_new_password']
})

export const userPermissionsSchema = z.object({
  permissions: z.array(z.string()).min(1, 'Selecione pelo menos uma permissão')
})

export const userRoleSchema = z.object({
  role: z.enum(['super_admin', 'admin', 'doctor', 'nurse', 'patient', 'researcher', 'coordinator'], {
    required_error: 'Função é obrigatória'
  })
})

export type CreateUserFormData = z.infer<typeof createUserSchema>
export type UpdateUserFormData = z.infer<typeof updateUserSchema>
export type UpdatePasswordFormData = z.infer<typeof updatePasswordSchema>
export type UserPermissionsFormData = z.infer<typeof userPermissionsSchema>
export type UserRoleFormData = z.infer<typeof userRoleSchema>