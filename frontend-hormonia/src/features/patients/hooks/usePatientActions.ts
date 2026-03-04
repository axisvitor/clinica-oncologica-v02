/**
 * usePatientActions Hook
 * Manages all patient mutation actions (delete, activate, deactivate)
 */

import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useToast } from '@/components/ui/use-toast'
import { apiClient } from '@/lib/api-client'
import { getErrorMessage } from '@/lib/utils/type-guards'
import { useAuth } from '@/app/providers/AuthContext'
import { isAdmin, isDoctor } from '@/types/shared'
import {
  getPatientsFromCache,
  setPatientsInCache,
  type PatientListCacheBase,
} from '../patient-cache-utils'

export function usePatientActions() {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)
  const canDeletePatient = isAdmin(user?.role ?? '') || isDoctor(user?.role ?? '')

  type PatientListCache = PatientListCacheBase & {
    size?: number
    limit?: number
    page?: number
  }

  const handleMutationError = (error: unknown) => {
    toast({
      title: 'Erro',
      description: getErrorMessage(error) || 'Ocorreu um erro inesperado.',
      variant: 'destructive',
    })
  }

  const deleteMutation = useMutation({
    mutationFn: (id: string) => apiClient.patients.deletePatient(id),
    onMutate: async (patientId: string) => {
      await queryClient.cancelQueries({ queryKey: ['patients'] })
      const previous = queryClient.getQueriesData<PatientListCache>({ queryKey: ['patients'] })

      queryClient.setQueriesData<PatientListCache>({ queryKey: ['patients'] }, (cache) => {
        if (!cache) return cache
        const current = getPatientsFromCache(cache)
        if (!current.length) return cache

        const next = current.filter((patient) => patient.id !== patientId)
        if (next.length === current.length) return cache

        const nextTotal =
          typeof cache.total === 'number' ? Math.max(0, cache.total - 1) : cache.total
        return setPatientsInCache(cache, next, nextTotal)
      })

      queryClient.removeQueries({ queryKey: ['patient', patientId] })

      return { previous }
    },
    onError: (error, _patientId, context) => {
      context?.previous?.forEach(([key, data]) => {
        queryClient.setQueryData(key, data)
      })
      handleMutationError(error)
    },
    onSuccess: () => {
      toast({ title: 'Paciente excluído com sucesso' })
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['patients'] })
    },
  })

  const activateMutation = useMutation({
    mutationFn: (id: string) => apiClient.patients.activate(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patients'] })
      toast({ title: 'Paciente ativado com sucesso' })
    },
    onError: handleMutationError,
  })

  const deactivateMutation = useMutation({
    mutationFn: (id: string) => apiClient.patients.deactivate(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patients'] })
      toast({ title: 'Paciente desativado (pausado) com sucesso' })
    },
    onError: handleMutationError,
  })

  const handleDelete = (e: React.MouseEvent, patientId: string, patientName: string) => {
    e.stopPropagation()
    if (!canDeletePatient) {
      toast({
        title: 'Permissão insuficiente',
        description: 'Você não tem permissão para excluir pacientes.',
        variant: 'destructive',
      })
      return
    }

    if (confirmDeleteId === patientId) {
      setConfirmDeleteId(null)
      deleteMutation.mutate(patientId)
      return
    }

    setConfirmDeleteId(patientId)
    toast({
      title: 'Confirme a exclusão',
      description: `Clique novamente para excluir ${patientName}.`,
      variant: 'destructive',
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
    isDeactivating: deactivateMutation.isPending,
    canDelete: canDeletePatient,
  }
}
