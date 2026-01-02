/**
 * Doctor Selection Section
 * Form section for selecting responsible doctor (admin only)
 */

import React from 'react'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

interface DoctorOption {
  id: string
  label: string
}

interface DoctorSelectionSectionProps {
  isAdmin: boolean
  doctorOptions: DoctorOption[]
  selectedDoctorId: string
  onDoctorChange: (doctorId: string) => void
  isLoading?: boolean
  currentUserName?: string
  showError?: boolean
}

export function DoctorSelectionSection({
  isAdmin,
  doctorOptions,
  selectedDoctorId,
  onDoctorChange,
  isLoading = false,
  currentUserName,
  showError = false
}: DoctorSelectionSectionProps) {
  const hasDoctorOptions = doctorOptions.length > 0

  // Admin com opções de médicos
  if (isAdmin && hasDoctorOptions) {
    return (
      <div className="space-y-2">
        <Label htmlFor="doctor_id">Médico responsável *</Label>
        <Select
          name="doctor_id"
          value={selectedDoctorId}
          onValueChange={onDoctorChange}
          disabled={isLoading}
        >
          <SelectTrigger id="doctor_id">
            <SelectValue
              placeholder={isLoading ? 'Carregando médicos...' : 'Selecione o médico responsável'}
            />
          </SelectTrigger>
          <SelectContent>
            {doctorOptions.map((doctor) => (
              <SelectItem key={doctor.id} value={doctor.id}>
                {doctor.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {showError && !selectedDoctorId && !isLoading && (
          <p className="text-sm text-red-600">Selecione o médico responsável.</p>
        )}
      </div>
    )
  }

  // Admin sem opções de médicos
  if (isAdmin && !hasDoctorOptions) {
    return (
      <div className="space-y-2">
        <Label>Médico responsável</Label>
        <div className="rounded-md border border-dashed border-muted-foreground/40 px-3 py-2 text-sm text-muted-foreground">
          Nenhum médico foi cadastrado ainda. O paciente será atribuído ao administrador atual.
        </div>
      </div>
    )
  }

  // Usuário não-admin
  return (
    <div className="space-y-2">
      <Label>Médico responsável</Label>
      <Input
        id="current_doctor_display"
        name="current_doctor_display"
        disabled
        value={currentUserName || 'Você'}
        className="bg-muted text-muted-foreground"
      />
      <p className="text-xs text-muted-foreground">
        Você será registrado como o médico responsável por este paciente.
      </p>
    </div>
  )
}
