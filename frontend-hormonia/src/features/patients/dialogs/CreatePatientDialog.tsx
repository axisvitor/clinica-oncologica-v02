/**
 * Create Patient Dialog
 * Wrapper component for patient creation using shared form
 */

import React, { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { useToast } from '@/components/ui/use-toast'
import { useAuth } from '@/app/providers/AuthContext'
import { apiClient } from '@/lib/api-client'
import { PatientForm } from './components/PatientForm'
import { usePatientForm } from './hooks/usePatientForm'

interface CreatePatientDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

interface DoctorUser {
  id: string
  full_name?: string
  name?: string
  email?: string
}

export function CreatePatientDialog({ open, onOpenChange }: CreatePatientDialogProps) {
  const { toast } = useToast()
  const { user } = useAuth()

  const normalizedRole = (user?.role ?? '').toLowerCase()
  const isAdminUser = normalizedRole === 'admin' || normalizedRole === 'super_admin'
  const userId = user?.id ?? ''

  const [selectedDoctorId, setSelectedDoctorId] = useState<string>(
    isAdminUser ? '' : userId
  )

  // Fetch doctor list for admins
  const { data: doctorList = [], isLoading: isLoadingDoctors } = useQuery<DoctorUser[]>({
    queryKey: ['admin-doctors', isAdminUser],
    queryFn: async () => {
      const response = await apiClient.adminUsers.list({ size: 100, role: 'doctor' })
      const rawList = Array.isArray(response)
        ? response
        : Array.isArray((response as any)?.items)
          ? (response as any).items
          : Array.isArray((response as any)?.data)
            ? (response as any).data
            : []
      return rawList.filter((doctor: unknown): doctor is DoctorUser =>
        typeof doctor === 'object' && doctor !== null && 'id' in doctor && typeof doctor.id === 'string'
      )
    },
    enabled: isAdminUser
  })

  const doctorOptions = useMemo(
    () =>
      doctorList.map((doctor) => ({
        id: doctor.id,
        label: doctor.full_name || doctor.name || doctor.email || 'Médico'
      })),
    [doctorList]
  )

  const hasDoctorOptions = doctorOptions.length > 0
  const requiresDoctorSelection = isAdminUser && hasDoctorOptions

  // Reset doctor selection when dialog opens
  useEffect(() => {
    if (isAdminUser && hasDoctorOptions) {
      setSelectedDoctorId('')
    } else {
      setSelectedDoctorId(userId)
    }
  }, [isAdminUser, hasDoctorOptions, userId])

  const handleClose = () => {
    setSelectedDoctorId(isAdminUser && hasDoctorOptions ? '' : userId)
    onOpenChange(false)
  }

  const handleSuccess = () => {
    if (isAdminUser) {
      setSelectedDoctorId('')
    }
  }

  // Validation before submit
  const handleSubmitWrapper = (data: any) => {
    if (isAdminUser && requiresDoctorSelection && !selectedDoctorId) {
      toast({
        title: 'Selecione o médico responsável',
        description: 'É necessário definir o médico responsável pelo paciente.',
        variant: 'destructive'
      })
      return
    }
    form.onSubmit(data)
  }

  // STRICT ENFORCEMENT: If not admin, ALWAYS use current user ID
  const targetDoctorId = isAdminUser ? selectedDoctorId : userId

  const form = usePatientForm({
    mode: 'create',
    doctorId: targetDoctorId,
    onSuccess: handleSuccess,
    onClose: handleClose
  })

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>Novo Paciente</DialogTitle>
          <DialogDescription>
            Adicione um novo paciente ao sistema de terapia hormonal.
          </DialogDescription>
        </DialogHeader>

        <PatientForm
          form={form.form}
          mode="create"
          onSubmit={handleSubmitWrapper}
          onCancel={handleClose}
          isPending={form.isPending}
          isAdmin={isAdminUser}
          doctorOptions={doctorOptions}
          selectedDoctorId={selectedDoctorId}
          onDoctorChange={setSelectedDoctorId}
          isLoadingDoctors={isLoadingDoctors}
          currentUserName={user?.full_name || user?.email}
          showDoctorError={requiresDoctorSelection && !selectedDoctorId && !isLoadingDoctors}
        />
      </DialogContent>
    </Dialog>
  )
}
