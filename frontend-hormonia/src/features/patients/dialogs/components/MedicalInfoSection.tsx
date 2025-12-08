/**
 * Medical Information Section
 * Form section for patient medical details (treatment, diagnosis, dates)
 */

import React from 'react'
import { UseFormReturn } from 'react-hook-form'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  TREATMENT_TYPES,
  TREATMENT_PHASES,
  TIMEZONES,
  type CreatePatientFormData,
  type UpdatePatientFormData
} from '../schemas/patientSchema'

interface MedicalInfoSectionProps {
  form: UseFormReturn<CreatePatientFormData | UpdatePatientFormData>
  mode: 'create' | 'edit'
}

export function MedicalInfoSection({ form, mode }: MedicalInfoSectionProps) {
  const { register, setValue, watch, formState: { errors } } = form

  return (
    <div className="space-y-4">
      {/* Tipo de tratamento e Data de início */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="treatment_type">
            Tipo de tratamento {mode === 'create' && '*'}
          </Label>
          <Select
            value={watch('treatment_type') ?? ''}
            onValueChange={(value) => setValue('treatment_type', value)}
          >
            <SelectTrigger>
              <SelectValue placeholder="Selecione o tratamento" />
            </SelectTrigger>
            <SelectContent>
              {TREATMENT_TYPES.map((type) => (
                <SelectItem key={type.value} value={type.value}>
                  {type.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {errors.treatment_type && (
            <p className="text-sm text-red-600">{errors.treatment_type.message}</p>
          )}
        </div>

        <div className="space-y-2">
          <Label htmlFor="treatment_start_date">Data de início do tratamento</Label>
          <Input
            id="treatment_start_date"
            type="date"
            {...register('treatment_start_date')}
          />
        </div>
      </div>

      {/* Fase do tratamento e Data de nascimento */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="treatment_phase">Fase do Tratamento</Label>
          <Select
            value={watch('treatment_phase') ?? ''}
            onValueChange={(value) => setValue('treatment_phase', value as any)}
          >
            <SelectTrigger>
              <SelectValue placeholder="Selecione a fase" />
            </SelectTrigger>
            <SelectContent>
              {TREATMENT_PHASES.map((phase) => (
                <SelectItem key={phase.value} value={phase.value}>
                  {phase.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label htmlFor="birth_date">Data de nascimento</Label>
          <Input
            id="birth_date"
            type="date"
            {...register('birth_date')}
          />
        </div>
      </div>

      {/* Fuso horário */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="timezone">Fuso Horário</Label>
          <Select
            value={watch('timezone') ?? 'America/Sao_Paulo'}
            onValueChange={(value) => setValue('timezone', value)}
          >
            <SelectTrigger>
              <SelectValue placeholder="Selecione o fuso horário" />
            </SelectTrigger>
            <SelectContent>
              {TIMEZONES.map((tz) => (
                <SelectItem key={tz.value} value={tz.value}>
                  {tz.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Diagnóstico */}
      <div className="space-y-2">
        <Label htmlFor="diagnosis">Diagnóstico</Label>
        <Textarea
          id="diagnosis"
          placeholder="Diagnóstico médico..."
          rows={2}
          {...register('diagnosis')}
        />
      </div>

      {/* Observações */}
      <div className="space-y-2">
        <Label htmlFor="doctor_notes">Observações</Label>
        <Textarea
          id="doctor_notes"
          placeholder="Observações sobre o paciente ou tratamento..."
          rows={3}
          {...register('doctor_notes')}
        />
      </div>
    </div>
  )
}
