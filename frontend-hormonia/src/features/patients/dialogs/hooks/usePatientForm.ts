/**
 * Patient Form Hook
 * Unified form logic for patient creation and update
 */

import { useForm, UseFormReturn } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import React, { useRef, useEffect } from 'react'
import { v4 as uuidv4 } from 'uuid'
import { useToast } from '@/components/ui/use-toast'
import { apiClient } from '@/lib/api-client'
import { getErrorMessage } from '@/lib/utils/type-guards'
import type { Patient } from '@/types/api'
import {
  createPatientSchema,
  updatePatientSchema,
  type CreatePatientFormData,
  type UpdatePatientFormData
} from '../schemas/patientSchema'

interface UsePatientFormProps {
  mode: 'create' | 'edit'
  patient?: Patient | null
  doctorId?: string
  onSuccess?: () => void
  onClose?: () => void
}

interface UsePatientFormReturn {
  form: UseFormReturn<CreatePatientFormData | UpdatePatientFormData>
  onSubmit: (data: CreatePatientFormData | UpdatePatientFormData) => void
  isPending: boolean
  reset: () => void
}

/**
 * Hook customizado para gerenciar formulário de paciente
 * Suporta tanto criação quanto edição
 */
export function usePatientForm({
  mode,
  patient,
  doctorId,
  onSuccess,
  onClose
}: UsePatientFormProps): UsePatientFormReturn {
  const { toast } = useToast()
  const queryClient = useQueryClient()

  // Idempotency key for preventing duplicate patient creation
  // QW-004: Reset after successful creation for next patient
  const idempotencyKeyRef = useRef<string>(uuidv4())

  // Configuração do form baseada no modo
  const form = useForm<CreatePatientFormData | UpdatePatientFormData>({
    resolver: zodResolver(mode === 'create' ? createPatientSchema : updatePatientSchema),
    defaultValues: mode === 'edit' && patient ? {
      name: patient.name,
      phone: patient.phone,
      email: patient.email || '',
      cpf: patient.cpf || '',
      birth_date: patient.birth_date || '',
      treatment_type: patient.treatment_type,
      treatment_phase: patient.treatment_phase as 'initial' | 'adjustment' | 'maintenance' | 'monitoring' | 'followup' | 'completed' | undefined,
      treatment_start_date: patient.treatment_start_date || '',
      diagnosis: patient.diagnosis || '',
      doctor_notes: patient.doctor_notes || '',
      timezone: patient.timezone || 'America/Sao_Paulo'
    } : {
      timezone: 'America/Sao_Paulo'
    }
  })

  // Mutation para criação
  const createMutation = useMutation({
    mutationFn: (data: CreatePatientFormData) => {
      if (!doctorId) {
        throw new Error('Selecione o médico responsável antes de criar o paciente.')
      }

      // Build clean payload
      const cleanData: Partial<CreatePatientFormData> & { doctor_id: string } = {
        name: data.name,
        phone: data.phone,
        treatment_type: data.treatment_type,
        doctor_id: doctorId,
        timezone: data.timezone,
        cpf: data.cpf,
        diagnosis: data.diagnosis,
        treatment_phase: data.treatment_phase
      }

      // Only include optional fields if they have values
      if (data.email) cleanData.email = data.email
      if (data.birth_date) cleanData.birth_date = data.birth_date
      if (data.treatment_start_date) cleanData.treatment_start_date = data.treatment_start_date
      if (data.doctor_notes) cleanData.doctor_notes = data.doctor_notes

      // QW-004: Send idempotency key via header to prevent duplicates
      return apiClient.patients.create(
        cleanData as Parameters<typeof apiClient.patients.create>[0],
        {
          headers: {
            'X-Idempotency-Key': idempotencyKeyRef.current
          }
        }
      )
    },
    onSuccess: () => {
      // QW-004: Reset idempotency key for next patient creation
      idempotencyKeyRef.current = uuidv4()

      queryClient.invalidateQueries({ queryKey: ['patients'] })
      toast({
        title: 'Paciente criado com sucesso',
        description: 'O novo paciente foi adicionado e o fluxo de onboarding foi iniciado via WhatsApp.',
      })
      form.reset()
      onSuccess?.()
      onClose?.()
    },
    onError: (error: unknown) => {
      toast({
        title: 'Erro ao criar paciente',
        description: getErrorMessage(error) || 'Ocorreu um erro inesperado.',
        variant: 'destructive'
      })
    }
  })

  // Mutation para atualização
  const updateMutation = useMutation({
    mutationFn: (data: UpdatePatientFormData) => {
      if (!patient) throw new Error('No patient selected')

      // Clean up empty strings and undefined values
      const cleanData = Object.fromEntries(
        Object.entries(data).filter(([_, value]) => value !== '' && value !== undefined)
      )

      return apiClient.patients.update(patient.id, cleanData, {
        headers: {
          'X-Idempotency-Key': `patient-update-${patient.id}-${Date.now()}`
        }
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patients'] })
      queryClient.invalidateQueries({ queryKey: ['patient', patient?.id] })
      toast({
        title: 'Paciente atualizado com sucesso',
        description: 'As informações do paciente foram atualizadas.',
      })
      form.reset()
      onSuccess?.()
      onClose?.()
    },
    onError: (error: unknown) => {
      toast({
        title: 'Erro ao atualizar paciente',
        description: getErrorMessage(error) || 'Ocorreu um erro inesperado.',
        variant: 'destructive'
      })
    }
  })

  // Reseta form quando paciente muda (modo edit)
  useEffect(() => {
    if (mode === 'edit' && patient) {
      form.reset({
        name: patient.name,
        phone: patient.phone,
        email: patient.email || '',
        cpf: patient.cpf || '',
        birth_date: patient.birth_date || '',
        treatment_type: patient.treatment_type,
        treatment_phase: patient.treatment_phase as 'initial' | 'adjustment' | 'maintenance' | 'monitoring' | 'followup' | 'completed' | undefined,
        treatment_start_date: patient.treatment_start_date || '',
        diagnosis: patient.diagnosis || '',
        doctor_notes: patient.doctor_notes || '',
        timezone: patient.timezone || 'America/Sao_Paulo'
      })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- form object reference is stable, only form.reset needed
  }, [mode, patient, form.reset])

  const onSubmit = (data: CreatePatientFormData | UpdatePatientFormData) => {
    if (mode === 'create') {
      createMutation.mutate(data as CreatePatientFormData)
    } else {
      updateMutation.mutate(data as UpdatePatientFormData)
    }
  }

  const mutation = mode === 'create' ? createMutation : updateMutation

  return {
    form,
    onSubmit,
    isPending: mutation.isPending,
    reset: form.reset
  }
}

