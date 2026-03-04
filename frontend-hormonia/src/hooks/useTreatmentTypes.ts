import { useState, useEffect } from 'react'

export interface TreatmentType {
  id: string
  name: string
  description?: string
}

const DEFAULT_TREATMENT_TYPES: TreatmentType[] = [
  {
    id: 'chemotherapy',
    name: 'Quimioterapia',
    description: 'Tratamento com medicamentos quimioterápicos',
  },
  { id: 'radiotherapy', name: 'Radioterapia', description: 'Tratamento com radiação' },
  { id: 'surgery', name: 'Cirurgia', description: 'Procedimento cirúrgico' },
  {
    id: 'immunotherapy',
    name: 'Imunoterapia',
    description: 'Tratamento que estimula o sistema imunológico',
  },
  { id: 'hormone_therapy', name: 'Terapia Hormonal', description: 'Tratamento com hormônios' },
  {
    id: 'targeted_therapy',
    name: 'Terapia Alvo',
    description: 'Medicamentos direcionados a alvos específicos',
  },
  {
    id: 'palliative_care',
    name: 'Cuidados Paliativos',
    description: 'Cuidados para melhorar a qualidade de vida',
  },
]

export function useTreatmentTypes() {
  const [treatmentTypes, setTreatmentTypes] = useState<TreatmentType[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {
    const fetchTreatmentTypes = async () => {
      try {
        setLoading(true)
        // In a real app, this would fetch from an API
        // For now, we'll use default treatment types
        await new Promise((resolve) => setTimeout(resolve, 500)) // Simulate API delay
        setTreatmentTypes(DEFAULT_TREATMENT_TYPES)
        setError(null)
      } catch (err) {
        setError(err instanceof Error ? err : new Error('Failed to fetch treatment types'))
      } finally {
        setLoading(false)
      }
    }

    fetchTreatmentTypes()
  }, [])

  return {
    treatmentTypes,
    loading,
    error,
    refetch: () => {
      setLoading(true)
      setError(null)
      // Re-fetch logic would go here
      setTreatmentTypes(DEFAULT_TREATMENT_TYPES)
      setLoading(false)
    },
  }
}

export default useTreatmentTypes
