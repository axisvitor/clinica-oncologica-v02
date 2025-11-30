/**
 * User Validation Schemas for Admin User Management
 *
 * These schemas are used by CreateUserModal and UserDetailsModal.
 * They have different field names than admin-schemas.ts for backward compatibility.
 *
 * @see CreateUserModal.tsx
 * @see UserDetailsModal.tsx
 */

import { z } from 'zod'

// ============================================================================
// CREATE USER SCHEMA
// ============================================================================

/**
 * Schema for creating a new user
 * Used by CreateUserModal
 */
export const createUserSchema = z.object({
  full_name: z.string()
    .min(2, 'Nome deve ter pelo menos 2 caracteres')
    .max(255, 'Nome deve ter no máximo 255 caracteres'),
  email: z.string()
    .email('Email inválido')
    .min(1, 'Email é obrigatório'),
  password: z.string()
    .min(8, 'Senha deve ter pelo menos 8 caracteres')
    .max(128, 'Senha deve ter no máximo 128 caracteres')
    .regex(/[0-9]/, 'Senha deve conter pelo menos um dígito')
    .regex(/[a-zA-Z]/, 'Senha deve conter pelo menos uma letra'),
  confirm_password: z.string()
    .min(8, 'Confirmação de senha é obrigatória'),
  role: z.enum(['admin', 'doctor']).default('doctor'),
  phone_number: z.string()
    .max(20, 'Telefone deve ter no máximo 20 caracteres')
    .optional()
    .nullable(),
  permissions: z.array(z.string()).optional().default([]),
  is_active: z.boolean().optional().default(true),
  two_factor_enabled: z.boolean().optional().default(false),
}).refine((data) => data.password === data.confirm_password, {
  message: 'As senhas não coincidem',
  path: ['confirm_password'],
})

export type CreateUserFormData = z.infer<typeof createUserSchema>

// ============================================================================
// UPDATE USER SCHEMA
// ============================================================================

/**
 * Schema for updating an existing user
 * Used by UserDetailsModal
 */
export const updateUserSchema = z.object({
  full_name: z.string()
    .min(2, 'Nome deve ter pelo menos 2 caracteres')
    .max(255, 'Nome deve ter no máximo 255 caracteres')
    .optional()
    .nullable(),
  email: z.string()
    .email('Email inválido')
    .optional()
    .nullable(),
  role: z.enum(['admin', 'doctor']).optional().nullable(),
  phone_number: z.string()
    .max(20, 'Telefone deve ter no máximo 20 caracteres')
    .optional()
    .nullable(),
  permissions: z.array(z.string()).optional().default([]),
  is_active: z.boolean().optional().nullable(),
  two_factor_enabled: z.boolean().optional().nullable(),
})

export type UpdateUserFormData = z.infer<typeof updateUserSchema>

// ============================================================================
// PASSWORD RESET SCHEMA
// ============================================================================

/**
 * Schema for resetting user password
 */
export const passwordResetSchema = z.object({
  new_password: z.string()
    .min(8, 'Senha deve ter pelo menos 8 caracteres')
    .max(128, 'Senha deve ter no máximo 128 caracteres')
    .regex(/[0-9]/, 'Senha deve conter pelo menos um dígito')
    .regex(/[a-zA-Z]/, 'Senha deve conter pelo menos uma letra'),
  confirm_password: z.string()
    .min(8, 'Confirmação de senha é obrigatória'),
}).refine((data) => data.new_password === data.confirm_password, {
  message: 'As senhas não coincidem',
  path: ['confirm_password'],
})

export type PasswordResetFormData = z.infer<typeof passwordResetSchema>

// ============================================================================
// USER FILTER SCHEMA
// ============================================================================

/**
 * Schema for filtering users list
 */
export const userFilterSchema = z.object({
  search: z.string().optional(),
  role: z.enum(['admin', 'doctor', 'all']).optional().default('all'),
  is_active: z.boolean().optional(),
  page: z.number().optional().default(1),
  page_size: z.number().optional().default(10),
})

export type UserFilterFormData = z.infer<typeof userFilterSchema>
