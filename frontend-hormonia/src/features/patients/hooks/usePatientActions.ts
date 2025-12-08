/**
 * usePatientActions Hook
 * Manages all patient mutation actions (delete, activate, deactivate)
 */

import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useToast } from '@/components/ui/use-toast'
import { apiClient } from '@/lib/api-client'
import { getErrorMessage } from '@/lib/utils/type-guards'

export function usePatientActions() {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)

  const mutationOptions = {
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patients'] })
    },
    onError: (error: unknown) => {
      toast({
        title: 'Erro',
        description: getErrorMessage(error) || 'Ocorreu um erro inesperado.',
        variant: 'destructive'
      })
    }
  }

  const deleteMutation = useMutation({
    mutationFn: (id: string) => apiClient.patients.deletePatient(id),
    ...mutationOptions,
    onSuccess: () => {
      mutationOptions.onSuccess()
      toast({ title: 'Paciente excluído com sucesso' })
    }
  })

  const activateMutation = useMutation({
    mutationFn: (id: string) => apiClient.patients.activate(id),
    ...mutationOptions,
    onSuccess: () => {
      mutationOptions.onSuccess()
      toast({ title: 'Paciente ativado com sucesso' })
    }
  })

  const deactivateMutation = useMutation({
    mutationFn: (id: string) => apiClient.patients.deactivate(id),
    ...mutationOptions,
    onSuccess: () => {
      mutationOptions.onSuccess()
      toast({ title: 'Paciente desativado (pausado) com sucesso' })
    }
  })

  const handleDelete = (
    e: React.MouseEvent,
    patientId: string,
    patientName: string
  ) => {
    e.stopPropagation()

    if (confirmDeleteId === patientId) {
      setConfirmDeleteId(null)
      deleteMutation.mutate(patientId)
      return
    }

    setConfirmDeleteId(patientId)
    toast({
      title: 'Confirme a exclusão',
      description: `Clique novamente para excluir ${patientName}.`,
      variant: 'destructive'
    })

    setTimeout(() => {
      setConfirmDeleteId((prev) => (prev === patientId ? null : prev))
    }, 3000)
  }

  const handleActivate = (id: string) => {
    activateMutation.mutate(id)
  }

  const handleDeactivate = (id: string) => {
    deactivateMutation.mutate(id)
  }

  return {
    handleDelete,
    handleActivate,
    handleDeactivate,
    confirmDeleteId,
    isDeleting: deleteMutation.isPending,
    isActivating: activateMutation.isPending,
    isDeactivating: deactivateMutation.isPending
  }
}
