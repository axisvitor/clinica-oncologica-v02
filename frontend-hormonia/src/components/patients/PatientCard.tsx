import React from 'react'
import { formatDistanceToNow } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import { useNavigate } from 'react-router-dom'
import { Phone, Mail, Calendar, Activity, MoveHorizontal as MoreHorizontal } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

interface Patient {
  id: string
  name: string
  phone: string
  email?: string
  treatment_type: string
  status: 'active' | 'inactive' | 'completed' | 'paused' | 'cancelled'
  current_day?: number
  last_contact?: string
  created_at: string
}

interface PatientCardProps {
  patient: Patient
  onEdit?: (patient: Patient) => void
  onMessage?: (patient: Patient) => void
}

export function PatientCard({ patient, onEdit, onMessage }: PatientCardProps) {
  const navigate = useNavigate()

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'active':
        return <Badge className="bg-green-100 text-green-800">Ativo</Badge>
      case 'paused':
        return <Badge className="bg-yellow-100 text-yellow-800">Pausado</Badge>
      case 'completed':
        return <Badge className="bg-blue-100 text-blue-800">Concluído</Badge>
      case 'inactive':
        return <Badge variant="secondary">Inativo</Badge>
      case 'cancelled':
        return <Badge className="bg-red-100 text-red-800">Cancelado</Badge>
      default:
        return <Badge variant="outline">{status}</Badge>
    }
  }

  const getInitials = (name: string) => {
    return name
      .split(' ')
      .map(n => n[0])
      .join('')
      .toUpperCase()
      .slice(0, 2)
  }

  const formatLastContact = (lastContact?: string) => {
    if (!lastContact) return 'Nunca'
    
    try {
      return formatDistanceToNow(new Date(lastContact), {
        addSuffix: true,
        locale: ptBR
      })
    } catch {
      return 'Data inválida'
    }
  }

  return (
    <Card className="hover:shadow-md transition-shadow cursor-pointer">
      <CardHeader className="pb-3 px-4 md:px-6 pt-4 md:pt-6">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center space-x-2 md:space-x-3 flex-1 min-w-0">
            <Avatar className="h-10 w-10 md:h-12 md:w-12 flex-shrink-0">
              <AvatarImage src="" alt={patient.name} />
              <AvatarFallback className="bg-blue-600 text-white text-sm md:text-base">
                {getInitials(patient.name)}
              </AvatarFallback>
            </Avatar>
            <div className="flex-1 min-w-0">
              <CardTitle
                className="text-base md:text-lg cursor-pointer hover:text-blue-600 truncate"
                onClick={() => navigate(`/patients/${patient.id}`)}
              >
                {patient.name}
              </CardTitle>
              <CardDescription className="flex items-center space-x-1 md:space-x-2 text-xs md:text-sm">
                <Phone className="h-3 w-3 flex-shrink-0" />
                <span className="truncate">{patient.phone}</span>
              </CardDescription>
            </div>
          </div>
          <div className="flex items-center space-x-1 md:space-x-2 flex-shrink-0">
            {getStatusBadge(patient.status)}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                  <MoreHorizontal className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuLabel>Ações</DropdownMenuLabel>
                <DropdownMenuItem onClick={() => navigate(`/patients/${patient.id}`)}>
                  Visualizar detalhes
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => onEdit?.(patient)}>
                  Editar paciente
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={() => onMessage?.(patient)}>
                  Enviar mensagem
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-2 md:space-y-3 px-4 md:px-6 pb-4 md:pb-6">
        {patient.email && (
          <div className="flex items-center space-x-2 text-xs md:text-sm text-gray-600">
            <Mail className="h-3 w-3 flex-shrink-0" />
            <span className="truncate">{patient.email}</span>
          </div>
        )}

        <div className="flex items-center space-x-2 text-xs md:text-sm text-gray-600">
          <Activity className="h-3 w-3 flex-shrink-0" />
          <span className="truncate">{patient.treatment_type}</span>
        </div>

        <div className="flex items-center justify-between text-xs md:text-sm">
          <span className="text-gray-600">Dia atual:</span>
          <span className="font-medium">{patient.current_day ?? 0}</span>
        </div>

        <div className="flex items-center justify-between text-xs md:text-sm">
          <span className="text-gray-600">Último contato:</span>
          <span className="font-medium truncate ml-2">{formatLastContact(patient.last_contact)}</span>
        </div>

        <div className="flex flex-col sm:flex-row gap-2 pt-2">
          <Button
            size="sm"
            variant="outline"
            className="flex-1 text-xs md:text-sm"
            onClick={() => navigate(`/patients/${patient.id}`)}
          >
            Ver detalhes
          </Button>
          <Button
            size="sm"
            className="flex-1 text-xs md:text-sm"
            onClick={() => onMessage?.(patient)}
          >
            Mensagem
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
