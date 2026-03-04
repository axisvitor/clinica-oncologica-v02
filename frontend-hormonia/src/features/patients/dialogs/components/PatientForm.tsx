/**
 * Patient Form Component
 * Shared form component for both Create and Edit patient dialogs
 */

import React from 'react'
import { UseFormReturn } from 'react-hook-form'
import { Button } from '@/components/ui/button'
import { DialogFooter } from '@/components/ui/dialog'
import { LoadingSpinner } from '@/components/ui/loading-spinner'
import { ContactInfoSection } from './ContactInfoSection'
import { MedicalInfoSection } from './MedicalInfoSection'
import { DoctorSelectionSection } from './DoctorSelectionSection'
import type { CreatePatientFormData, UpdatePatientFormData } from '../schemas/patientSchema'

interface DoctorOption {
  id: string
  label: string
}

interface PatientFormProps {
  form: UseFormReturn<CreatePatientFormData | UpdatePatientFormData>
  mode: 'create' | 'edit'
  onSubmit: (data: CreatePatientFormData | UpdatePatientFormData) => void
  onCancel: () => void
  isPending: boolean

  // Doctor selection props (only for create mode)
  isAdmin?: boolean
  doctorOptions?: DoctorOption[]
  selectedDoctorId?: string
  onDoctorChange?: (doctorId: string) => void
  isLoadingDoctors?: boolean
  currentUserName?: string
  showDoctorError?: boolean
}

export function PatientForm({
  form,
  mode,
  onSubmit,
  onCancel,
  isPending,
  isAdmin = false,
  doctorOptions = [],
  selectedDoctorId = '',
  onDoctorChange = () => {},
  isLoadingDoctors = false,
  currentUserName = '',
  showDoctorError = false,
}: PatientFormProps) {
  const { handleSubmit } = form

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      {/* Contact Information */}
      <ContactInfoSection form={form} mode={mode} />

      {/* Doctor Selection (only for create mode) */}
      {mode === 'create' && (
        <DoctorSelectionSection
          isAdmin={isAdmin}
          doctorOptions={doctorOptions}
          selectedDoctorId={selectedDoctorId}
          onDoctorChange={onDoctorChange}
          isLoading={isLoadingDoctors}
          currentUserName={currentUserName}
          showError={showDoctorError}
        />
      )}

      {/* Medical Information */}
      <MedicalInfoSection form={form} mode={mode} />

      {/* Form Actions */}
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onCancel} disabled={isPending}>
          Cancelar
        </Button>
        <Button type="submit" disabled={isPending}>
          {isPending ? (
            <>
              <LoadingSpinner size="sm" className="mr-2" />
              {mode === 'create' ? 'Criando...' : 'Atualizando...'}
            </>
          ) : mode === 'create' ? (
            'Criar Paciente'
          ) : (
            'Atualizar Paciente'
          )}
        </Button>
      </DialogFooter>
    </form>
  )
}
