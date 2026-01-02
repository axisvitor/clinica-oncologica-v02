import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { Users, Activity, Clock, CheckCircle } from 'lucide-react'
import { apiClient } from '../../lib/api-client'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { LoadingSpinner } from '@/components/ui/loading-spinner'
import type { Patient } from '@/lib/api-client'

export function PatientStats() {
  const { data: patientsData, isLoading } = useQuery({
    queryKey: ['patients', { size: 100 }],
    queryFn: () => apiClient.patients.list({ size: 100 })
  })

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {[...Array(4)].map((_, i) => (
          <Card key={i}>
            <CardContent className="pt-6">
              <div className="flex items-center justify-center">
                <LoadingSpinner size="md" />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    )
  }

  // Handle different possible response shapes from API
  interface PatientListResponse {
    items?: Patient[];
    data?: Patient[];
  }
  const typedPatientsData = patientsData as PatientListResponse | Patient[] | undefined
  const patients: Patient[] = Array.isArray(typedPatientsData)
    ? typedPatientsData
    : (typedPatientsData?.items || typedPatientsData?.data || [])
  const totalPatients = patients.length
  const activePatients = patients.filter((p: Patient) => p.status === 'active').length
  const pausedPatients = patients.filter((p: Patient) => p.status === 'paused').length
  const completedPatients = patients.filter((p: Patient) => p.status === 'completed').length

  const stats = [
    {
      title: 'Total de Pacientes',
      value: totalPatients,
      icon: Users,
      description: 'Pacientes cadastrados'
    },
    {
      title: 'Pacientes Ativos',
      value: activePatients,
      icon: Activity,
      description: 'Em tratamento ativo'
    },
    {
      title: 'Pacientes Pausados',
      value: pausedPatients,
      icon: Clock,
      description: 'Tratamento pausado'
    },
    {
      title: 'Tratamentos Concluídos',
      value: completedPatients,
      icon: CheckCircle,
      description: 'Finalizados com sucesso'
    }
  ]

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      {stats.map((stat) => {
        const Icon = stat.icon
        return (
          <Card key={stat.title}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                {stat.title}
              </CardTitle>
              <Icon className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stat.value}</div>
              <p className="text-xs text-muted-foreground">
                {stat.description}
              </p>
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}
