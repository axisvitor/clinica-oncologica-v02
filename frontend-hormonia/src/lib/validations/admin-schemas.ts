/**
 * Admin RBAC Validation Schemas
 *
 * Zod schemas matching backend Pydantic schemas for type-safe validation
 * Backend: app/schemas/admin_users.py
 */

import { z } from 'zod'
import { UserRole, Permission } from '@/types/rbac'

// ============================================================================
// USER ROLE VALIDATION
// ============================================================================

/**
 * User role enum validation
 * Backend: app/schemas/admin_users.py UserRole enum
 */
export const userRoleSchema = z.nativeEnum(UserRole, {
  errorMap: () => ({ message: 'Função inválida. Apenas admin ou doctor são permitidos.' }),
})

// ============================================================================
// USER CREATION
// ============================================================================

/**
 * User creation schema
 * Backend: app/schemas/admin_users.py UserCreate
 */
export const userCreateSchema = z.object({
  name: z
    .string()
    .min(2, 'Nome deve ter pelo menos 2 caracteres')
    .max(255, 'Nome deve ter no máximo 255 caracteres'),
  email: z.string().email('Email inválido').min(1, 'Email é obrigatório'),
  password: z
    .string()
    .min(8, 'Senha deve ter pelo menos 8 caracteres')
    .max(128, 'Senha deve ter no máximo 128 caracteres')
    .regex(/[0-9]/, 'Senha deve conter pelo menos um dígito')
    .regex(/[a-zA-Z]/, 'Senha deve conter pelo menos uma letra'),
  role: userRoleSchema.default(UserRole.DOCTOR),
  phone_number: z
    .string()
    .max(20, 'Telefone deve ter no máximo 20 caracteres')
    .regex(/^[0-9+\-() .]+$/, 'Formato de telefone inválido')
    .refine((val) => {
      const cleaned = val.replace(/[^0-9+]/g, '')
      return cleaned.length >= 10
    }, 'Telefone deve conter pelo menos 10 dígitos')
    .optional()
    .nullable(),
})

export type UserCreateFormData = z.infer<typeof userCreateSchema>

// ============================================================================
// USER UPDATE
// ============================================================================

/**
 * User update schema
 * Backend: app/schemas/admin_users.py UserUpdate
 */
export const userUpdateSchema = z
  .object({
    name: z
      .string()
      .min(2, 'Nome deve ter pelo menos 2 caracteres')
      .max(255, 'Nome deve ter no máximo 255 caracteres')
      .optional()
      .nullable(),
    email: z.string().email('Email inválido').optional().nullable(),
    role: userRoleSchema.optional().nullable(),
    phone_number: z
      .string()
      .max(20, 'Telefone deve ter no máximo 20 caracteres')
      .regex(/^[0-9+\-() .]+$/, 'Formato de telefone inválido')
      .refine((val) => {
        const cleaned = val.replace(/[^0-9+]/g, '')
        return cleaned.length >= 10
      }, 'Telefone deve conter pelo menos 10 dígitos')
      .optional()
      .nullable(),
    is_active: z.boolean().optional().nullable(),
  })
  .refine(
    (data) => Object.values(data).some((v) => v !== null && v !== undefined),
    'Pelo menos um campo deve ser fornecido para atualização'
  )

export type UserUpdateFormData = z.infer<typeof userUpdateSchema>

// ============================================================================
// ROLE ASSIGNMENT
// ============================================================================

/**
 * Role update schema
 * Backend: app/schemas/admin_users.py RoleUpdate
 */
export const roleUpdateSchema = z.object({
  role: userRoleSchema,
})

export type RoleUpdateFormData = z.infer<typeof roleUpdateSchema>

// ============================================================================
// PERMISSIONS UPDATE
// ============================================================================

/**
 * Valid permission values matching backend Permission enum
 */
const VALID_PERMISSIONS = Object.values(Permission)

/**
 * Permissions update schema
 * Backend: app/schemas/admin_users.py PermissionsUpdate
 */
export const permissionsUpdateSchema = z.object({
  permissions: z
    .array(z.string())
    .min(1, 'Pelo menos uma permissão deve ser fornecida')
    .refine(
      (perms) => perms.every((p) => VALID_PERMISSIONS.includes(p as Permission)),
      'Permissão inválida detectada'
    ),
})

export type PermissionsUpdateFormData = z.infer<typeof permissionsUpdateSchema>

// ============================================================================
// PASSWORD RESET
// ============================================================================

/**
 * Password reset schema
 * Backend: app/schemas/admin_users.py PasswordReset
 */
export const passwordResetSchema = z.object({
  new_password: z
    .string()
    .min(8, 'Senha deve ter pelo menos 8 caracteres')
    .max(128, 'Senha deve ter no máximo 128 caracteres')
    .regex(/[0-9]/, 'Senha deve conter pelo menos um dígito')
    .regex(/[a-zA-Z]/, 'Senha deve conter pelo menos uma letra'),
})

export type PasswordResetFormData = z.infer<typeof passwordResetSchema>

/**
 * Password change with confirmation
 */
export const passwordChangeSchema = passwordResetSchema
  .extend({
    confirm_password: z.string().min(1, 'Confirmação de senha é obrigatória'),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: 'As senhas não coincidem',
    path: ['confirm_password'],
  })

export type PasswordChangeFormData = z.infer<typeof passwordChangeSchema>

// ============================================================================
// USER FILTERS
// ============================================================================

/**
 * User filter schema
 * Backend: app/schemas/admin_users.py UserFilter
 */
export const userFilterSchema = z.object({
  name: z.string().optional().nullable(),
  email: z.string().optional().nullable(),
  role: userRoleSchema.optional().nullable(),
  is_active: z.boolean().optional().nullable(),
  phone_number: z.string().optional().nullable(),
  created_after: z.string().datetime().optional().nullable(),
  created_before: z.string().datetime().optional().nullable(),
  has_patients: z.boolean().optional().nullable(),
})

export type UserFilterFormData = z.infer<typeof userFilterSchema>

// ============================================================================
// BULK OPERATIONS
// ============================================================================

/**
 * Bulk user operation schema
 * Backend: app/schemas/admin_users.py BulkUserOperation
 */
export const bulkUserOperationSchema = z.object({
  user_ids: z
    .array(z.string().uuid())
    .min(1, 'Pelo menos um usuário deve ser selecionado')
    .max(100, 'Máximo de 100 usuários por operação'),
  operation: z.enum(['activate', 'deactivate', 'delete'], {
    errorMap: () => ({ message: 'Operação inválida' }),
  }),
})

export type BulkUserOperationFormData = z.infer<typeof bulkUserOperationSchema>

// ============================================================================
// VALIDATION HELPERS
// ============================================================================

/**
 * Validate email domain against allowed domains for role
 */
export function validateEmailDomain(
  email: string,
  role: UserRole
): { valid: boolean; message?: string } {
  const domain = email.split('@')[1]?.toLowerCase()

  if (!domain) {
    return { valid: false, message: 'Email inválido' }
  }

  // Get allowed domains from ROLE_DEFINITIONS
  const allowedDomains: Record<UserRole, string[]> = {
    [UserRole.ADMIN]: ['hormonia.io', 'admin.local', 'clinica.med.br'],
    [UserRole.DOCTOR]: ['med.br', 'saude.gov.br', 'crm.org.br', 'hospital.com.br'],
  }

  const allowed = allowedDomains[role]

  // For doctors, check if domain ends with allowed domains
  if (role === UserRole.DOCTOR) {
    const isAllowed = allowed.some((d) => domain.endsWith(d))
    if (!isAllowed) {
      return {
        valid: false,
        message: `Domínio ${domain} não é permitido para médicos. Use domínios como ${allowed.join(', ')}`,
      }
    }
  }

  // For admins, exact match required
  if (role === UserRole.ADMIN) {
    if (!allowed.includes(domain)) {
      return {
        valid: false,
        message: `Domínio ${domain} não é permitido para administradores. Domínios permitidos: ${allowed.join(', ')}`,
      }
    }
  }

  return { valid: true }
}

/**
 * Type guard for UserRole
 */
export function isValidUserRole(role: string): role is UserRole {
  return Object.values(UserRole).includes(role as UserRole)
}

/**
 * Type guard for Permission
 */
export function isValidPermission(permission: string): permission is Permission {
  return VALID_PERMISSIONS.includes(permission as Permission)
}
