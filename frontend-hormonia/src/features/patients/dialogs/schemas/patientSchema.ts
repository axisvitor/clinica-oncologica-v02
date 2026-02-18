/**
 * Patient Form Validation Schema
 * Unified Zod schema for patient creation and update forms
 */

import { z } from 'zod'
import { cpfRefinement, cleanCPF } from '@/lib/utils/cpf'
import { normalizePhone } from '@/lib/utils/phone'

const optionalEmailSchema = z.preprocess(
  (value) => {
    if (typeof value === 'string' && value.trim() === '') {
      return undefined
    }
    return value
  },
  z.string().email('Email inválido').optional().nullable()
)

/**
 * Schema base para campos comuns de paciente
 */
const basePatientFields = {
  name: z.string().min(2, 'Nome deve ter pelo menos 2 caracteres'),

  phone: z.string()
    .min(10, 'Telefone deve ter pelo menos 10 dígitos')
    .transform(normalizePhone)
    .refine(
      (value) => /^\+[1-9]\d{9,14}$/.test(value),
      'Telefone deve incluir código do país (ex: +5511999999999)'
    ),

  email: optionalEmailSchema,

  cpf: z.string()
    .optional()
    .refine(cpfRefinement, { message: 'CPF inválido' })
    .transform(val => val ? cleanCPF(val) : undefined),

  birth_date: z.string().optional(),

  treatment_type: z.string().min(1, 'Selecione um tipo de tratamento'),

  treatment_phase: z.enum([
    'initial',
    'adjustment',
    'maintenance',
    'monitoring',
    'followup',
    'completed'
  ]).optional(),

  treatment_start_date: z.string().optional(),

  diagnosis: z.string().optional(),

  doctor_notes: z.string().optional(),

  timezone: z.string().default('America/Sao_Paulo')
}

/**
 * Schema para criação de paciente (todos campos obrigatórios)
 */
export const createPatientSchema = z.object(basePatientFields)

/**
 * Schema para atualização de paciente (todos campos opcionais)
 */
export const updatePatientSchema = z.object({
  name: z.string().min(2, 'Nome deve ter pelo menos 2 caracteres').optional(),

  phone: z.string()
    .min(10, 'Telefone deve ter pelo menos 10 dígitos')
    .optional()
    .transform(value => value ? normalizePhone(value) : value)
    .refine(
      (value) => !value || /^\+[1-9]\d{9,14}$/.test(value),
      'Telefone deve incluir código do país (ex: +5511999999999)'
    ),

  email: optionalEmailSchema,

  cpf: z.string()
    .optional()
    .refine(cpfRefinement, { message: 'CPF inválido' })
    .transform(val => val ? cleanCPF(val) : undefined),

  birth_date: z.string().optional(),

  treatment_type: z.string().optional(),

  treatment_phase: z.enum([
    'initial',
    'adjustment',
    'maintenance',
    'monitoring',
    'followup',
    'completed'
  ]).optional(),

  treatment_start_date: z.string().optional(),

  diagnosis: z.string().optional(),

  doctor_notes: z.string().optional(),

  timezone: z.string().optional()
})

/**
 * Tipos TypeScript derivados dos schemas
 */
export type CreatePatientFormData = z.infer<typeof createPatientSchema>
export type UpdatePatientFormData = z.infer<typeof updatePatientSchema>

/**
 * Constantes para opções de formulário
 */
export const TREATMENT_TYPES = [
  { value: 'Terapia Hormonal Feminina', label: 'Terapia Hormonal Feminina' },
  { value: 'Terapia Hormonal Masculina', label: 'Terapia Hormonal Masculina' },
  { value: 'Reposição Hormonal', label: 'Reposição Hormonal' },
  { value: 'Tratamento Personalizado', label: 'Tratamento Personalizado' }
] as const

export const TREATMENT_PHASES = [
  { value: 'initial', label: 'Inicial' },
  { value: 'adjustment', label: 'Ajuste' },
  { value: 'maintenance', label: 'Manutenção' },
  { value: 'monitoring', label: 'Monitoramento' },
  { value: 'followup', label: 'Acompanhamento' },
  { value: 'completed', label: 'Concluído' }
] as const

export const TIMEZONES = [
  { value: 'America/Sao_Paulo', label: 'Brasília (GMT-3)' },
  { value: 'America/Manaus', label: 'Manaus (GMT-4)' },
  { value: 'America/Belem', label: 'Belém (GMT-3)' },
  { value: 'America/Fortaleza', label: 'Fortaleza (GMT-3)' },
  { value: 'America/Recife', label: 'Recife (GMT-3)' },
  { value: 'America/Cuiaba', label: 'Cuiabá (GMT-4)' },
  { value: 'America/Campo_Grande', label: 'Campo Grande (GMT-4)' },
  { value: 'America/Porto_Velho', label: 'Porto Velho (GMT-4)' },
  { value: 'America/Rio_Branco', label: 'Rio Branco (GMT-5)' },
  { value: 'America/Noronha', label: 'Fernando de Noronha (GMT-2)' }
] as const
