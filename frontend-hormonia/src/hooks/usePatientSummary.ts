/**
 * usePatientSummary Hook
 *
 * React Query hook for patient summary generation and management.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import type {
  PatientSummaryResponse,
  PatientSummaryListResponse,
  GenerateSummaryRequest,
} from '@/types/api'

// Query keys
export const patientSummaryKeys = {
  all: ['patient-summaries'] as const,
  list: (patientId: string) => [...patientSummaryKeys.all, 'list', patientId] as const,
  detail: (summaryId: string) => [...patientSummaryKeys.all, 'detail', summaryId] as const,
}

/**
 * Hook for generating patient summaries
 */
export function useGenerateSummary() {
  const queryClient = useQueryClient()

  return useMutation<PatientSummaryResponse, Error, GenerateSummaryRequest>({
    mutationFn: async (request: GenerateSummaryRequest) => {
      return apiClient.ai.generateSummary(request)
    },
    onSuccess: (data: PatientSummaryResponse) => {
      // Invalidate list cache for this patient
      queryClient.invalidateQueries({
        queryKey: patientSummaryKeys.list(data.patient_id),
      })
    },
  })
}

/**
 * Hook for fetching saved summaries
 */
export function usePatientSummaries(
  patientId: string,
  options?: { limit?: number; offset?: number; enabled?: boolean }
) {
  const { limit = 10, offset = 0, enabled = true } = options || {}

  return useQuery<PatientSummaryListResponse, Error>({
    queryKey: [...patientSummaryKeys.list(patientId), { limit, offset }],
    queryFn: () => apiClient.ai.getSummaries(patientId, limit, offset),
    enabled: enabled && !!patientId,
  })
}

/**
 * Hook for fetching a specific summary
 */
export function usePatientSummary(summaryId: string, enabled = true) {
  return useQuery<PatientSummaryResponse, Error>({
    queryKey: patientSummaryKeys.detail(summaryId),
    queryFn: () => apiClient.ai.getSummary(summaryId),
    enabled: enabled && !!summaryId,
  })
}

/**
 * Hook for exporting summary as PDF
 */
export function useExportSummaryPdf() {
  return useMutation<Blob, Error, string>({
    mutationFn: async (summaryId: string) => {
      return apiClient.ai.exportSummaryPdf(summaryId)
    },
  })
}

/**
 * Combined hook for patient summary management
 */
export function usePatientSummaryManager(patientId: string, options?: { enabled?: boolean }) {
  const queryClient = useQueryClient()
  const summariesQuery = usePatientSummaries(patientId, {
    enabled: options?.enabled ?? false,
  })
  const generateMutation = useGenerateSummary()
  const exportMutation = useExportSummaryPdf()

  const generateSummary = async (startDate: string, endDate: string, forceRefresh = false) => {
    return generateMutation.mutateAsync({
      patient_id: patientId,
      start_date: startDate,
      end_date: endDate,
      force_refresh: forceRefresh,
      save_summary: true,
    })
  }

  const exportToPdf = async (summaryId: string) => {
    const blob = await exportMutation.mutateAsync(summaryId)

    // Download the PDF
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `patient_summary_${summaryId}.pdf`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  }

  const refreshSummaries = () => {
    queryClient.invalidateQueries({
      queryKey: patientSummaryKeys.list(patientId),
    })
  }

  return {
    // Queries
    summaries: summariesQuery.data?.summaries ?? [],
    total: summariesQuery.data?.total ?? 0,
    hasMore: summariesQuery.data?.has_more ?? false,
    isLoading: summariesQuery.isLoading,
    isFetching: summariesQuery.isFetching,
    error: summariesQuery.error,

    // Mutations
    generateSummary,
    isGenerating: generateMutation.isPending,
    generatedSummary: generateMutation.data,
    generateError: generateMutation.error,

    // Export
    exportToPdf,
    isExporting: exportMutation.isPending,

    // Actions
    refreshSummaries,
  }
}
