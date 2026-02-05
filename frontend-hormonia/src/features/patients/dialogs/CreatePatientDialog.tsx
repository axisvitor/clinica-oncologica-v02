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

  const [selectedDoctorId, setSelectedDoctorId] = useState<string>(userId)

  // Fetch doctor list for admins (filter locally to avoid backend role filter issues)
  const { data: doctorList = [], isLoading: isLoadingDoctors } = useQuery<DoctorUser[]>({
    queryKey: ['admin-doctors', isAdminUser],
    queryFn: async () => {
      const response = await apiClient.adminUsers.list({ size: 100 })
      const responseRecord = response as { items?: unknown[]; data?: unknown[]; role?: string }
      const rawList = Array.isArray(response)
        ? response
        : Array.isArray(responseRecord?.items)
          ? responseRecord.items
          : Array.isArray(responseRecord?.data)
            ? responseRecord.data
            : []
      // Return all users without role filtering
      return rawList.filter((user: unknown): user is DoctorUser =>
        typeof user === 'object' &&
        user !== null &&
        'id' in user &&
        typeof (user as DoctorUser).id === 'string'
      )
    },
    enabled: isAdminUser
  })

  const doctorOptions = useMemo(() => {
    const options = doctorList.map((doctor) => ({
      id: doctor.id,
      label: doctor.full_name || doctor.name || doctor.email || 'Médico'
    }))

    if (isAdminUser && userId) {
      const adminLabel = user?.full_name || user?.email || 'Administrador atual'
      if (!options.some((doctor) => doctor.id === userId)) {
        options.unshift({ id: userId, label: `${adminLabel} (você)` })
      }
    }

    return options
  }, [doctorList, isAdminUser, userId, user?.full_name, user?.email])

  const hasDoctorOptions = doctorOptions.length > 0
  const requiresDoctorSelection = isAdminUser

  // Reset doctor selection when dialog opens
  useEffect(() => {
    if (isAdminUser) {
      setSelectedDoctorId((current) => current || userId)
    } else {
      setSelectedDoctorId(userId)
    }
  }, [isAdminUser, userId])

  const handleClose = () => {
    setSelectedDoctorId(userId)
    form.resetIdempotencyKey()
    onOpenChange(false)
  }

  const handleSuccess = () => {
    if (isAdminUser) {
      setSelectedDoctorId(userId)
    }
  }

  // Validation before submit
  const handleSubmitWrapper = (data: Record<string, unknown>) => {
    if (isAdminUser && requiresDoctorSelection && !selectedDoctorId) {
      const description = hasDoctorOptions
        ? 'É necessário definir o médico responsável pelo paciente.'
        : 'Nenhum médico disponível. Cadastre um médico antes de continuar.'
      toast({
        title: 'Selecione o médico responsável',
        description,
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
      <DialogContent className="sm:max-w-[600px]" onOpenAutoFocus={(e) => {
        // Prevent default focus to avoid conflicts with Select trigger and aria-hidden
        e.preventDefault()
        // Wait a tick to ensure aria-hidden is cleared by Radix before focusing
        setTimeout(() => {
          document.getElementById('name')?.focus()
        }, 50)
      }}>
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
