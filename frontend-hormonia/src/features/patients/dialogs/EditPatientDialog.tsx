/**
 * Edit Patient Dialog
 * Wrapper component for patient editing using shared form
 */

import React from 'react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import type { Patient } from '@/types/api'
import { PatientForm } from './components/PatientForm'
import { usePatientForm } from './hooks/usePatientForm'

interface EditPatientDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  patient: Patient | null
}

export function EditPatientDialog({ open, onOpenChange, patient }: EditPatientDialogProps) {
  const handleClose = () => {
    onOpenChange(false)
  }

  const form = usePatientForm({
    mode: 'edit',
    patient,
    onClose: handleClose
  })

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>Editar Paciente</DialogTitle>
          <DialogDescription>
            Atualize as informações do paciente {patient?.name}.
          </DialogDescription>
        </DialogHeader>

        <PatientForm
          form={form.form}
          mode="edit"
          onSubmit={form.onSubmit}
          onCancel={handleClose}
          isPending={form.isPending}
        />
      </DialogContent>
    </Dialog>
  )
}
