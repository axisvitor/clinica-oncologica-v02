import { useQuery } from '@tanstack/react-query'

export interface TreatmentType {
  id: string
  name: string
  description?: string
}

export function useTreatmentTypes() {
  return useQuery<TreatmentType[]>({
    queryKey: ['treatment-types'],
    queryFn: async () => {
      // Mock data for now - replace with API call when backend endpoint is ready
      return [
        { id: '1', name: 'Hormonal', description: 'Terapia de reposição hormonal' },
        { id: '2', name: 'Quimioterapia', description: 'Tratamento quimioterápico' },
        { id: '3', name: 'Radioterapia', description: 'Tratamento radioterápico' },
        { id: '4', name: 'Imunoterapia', description: 'Tratamento imunoterápico' },
        { id: '5', name: 'Terapia Alvo', description: 'Terapia alvo molecular' }
      ]
    },
    staleTime: 1000 * 60 * 60, // 1 hour
    gcTime: 1000 * 60 * 60 * 24 // 24 hours
  })
}