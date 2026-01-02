/**
 * Contact Information Section
 * Form section for patient contact details (name, phone, email, CPF)
 */

import React from 'react'
import { UseFormReturn } from 'react-hook-form'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { CreatePatientFormData, UpdatePatientFormData } from '../schemas/patientSchema'

interface ContactInfoSectionProps {
  form: UseFormReturn<CreatePatientFormData | UpdatePatientFormData>
  mode: 'create' | 'edit'
}

export function ContactInfoSection({ form, mode }: ContactInfoSectionProps) {
  const { register, formState: { errors } } = form

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Nome completo */}
        <div className="space-y-2">
          <Label htmlFor="name">
            Nome completo {mode === 'create' && '*'}
          </Label>
          <Input
            id="name"
            placeholder="Nome do paciente"
            autoComplete="name"
            {...register('name')}
          />
          {errors.name && (
            <p className="text-sm text-red-600">{errors.name.message}</p>
          )}
        </div>

        {/* Telefone */}
        <div className="space-y-2">
          <Label htmlFor="phone">
            Telefone {mode === 'create' && '*'}
          </Label>
          <Input
            id="phone"
            placeholder="+55 11 99999-9999"
            autoComplete="tel"
            {...register('phone')}
          />
          {errors.phone && (
            <p className="text-sm text-red-600">{errors.phone.message}</p>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Email */}
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            placeholder="email@exemplo.com"
            autoComplete="email"
            {...register('email')}
          />
          {errors.email && (
            <p className="text-sm text-red-600">{errors.email.message}</p>
          )}
        </div>

        {/* CPF */}
        <div className="space-y-2">
          <Label htmlFor="cpf">CPF</Label>
          <Input
            id="cpf"
            placeholder="000.000.000-00"
            autoComplete="off"
            {...register('cpf')}
          />
          {errors.cpf && (
            <p className="text-sm text-red-600">{errors.cpf.message}</p>
          )}
        </div>
      </div>
    </div>
  )
}
