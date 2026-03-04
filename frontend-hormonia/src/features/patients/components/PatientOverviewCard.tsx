import React from 'react'
import { Phone, Mail, Activity, Calendar } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'

interface PatientOverviewCardProps {
  patient: {
    name: string
    phone?: string
    email?: string
    treatment_type?: string
    birth_date?: string
    treatment_start_date?: string
    current_day?: string | number
  }
}

export function PatientOverviewCard({ patient }: PatientOverviewCardProps) {
  const getInitials = (name: string) => {
    return name
      .split(' ')
      .map((n) => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2)
  }

  const formatDate = (dateString: string) => {
    try {
      return new Date(dateString).toLocaleDateString('pt-BR')
    } catch {
      return 'Data inválida'
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Informações do Paciente</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-start space-x-6">
          <Avatar className="h-20 w-20">
            <AvatarImage src="" alt={patient.name} />
            <AvatarFallback className="bg-blue-600 text-white text-lg">
              {getInitials(patient.name)}
            </AvatarFallback>
          </Avatar>

          <div className="flex-1 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <div className="space-y-3">
              <div className="flex items-center space-x-2">
                <Phone className="h-4 w-4 text-gray-400" />
                <span className="text-sm text-gray-600">Telefone</span>
              </div>
              <p className="font-medium">{patient.phone}</p>
            </div>

            {patient.email && (
              <div className="space-y-3">
                <div className="flex items-center space-x-2">
                  <Mail className="h-4 w-4 text-gray-400" />
                  <span className="text-sm text-gray-600">Email</span>
                </div>
                <p className="font-medium">{patient.email}</p>
              </div>
            )}

            <div className="space-y-3">
              <div className="flex items-center space-x-2">
                <Activity className="h-4 w-4 text-gray-400" />
                <span className="text-sm text-gray-600">Tratamento</span>
              </div>
              <p className="font-medium">{patient.treatment_type}</p>
            </div>

            {patient.birth_date && (
              <div className="space-y-3">
                <div className="flex items-center space-x-2">
                  <Calendar className="h-4 w-4 text-gray-400" />
                  <span className="text-sm text-gray-600">Data de nascimento</span>
                </div>
                <p className="font-medium">{formatDate(patient.birth_date)}</p>
              </div>
            )}

            {patient.treatment_start_date && (
              <div className="space-y-3">
                <div className="flex items-center space-x-2">
                  <Calendar className="h-4 w-4 text-gray-400" />
                  <span className="text-sm text-gray-600">Início do tratamento</span>
                </div>
                <p className="font-medium">{formatDate(patient.treatment_start_date)}</p>
              </div>
            )}

            <div className="space-y-3">
              <div className="flex items-center space-x-2">
                <Activity className="h-4 w-4 text-gray-400" />
                <span className="text-sm text-gray-600">Dia atual</span>
              </div>
              <p className="font-medium">{patient.current_day}</p>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
