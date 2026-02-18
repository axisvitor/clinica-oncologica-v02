import React, { useState, useMemo, useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { Search, Phone, MessageSquare, User as User2 } from 'lucide-react'
import { apiClient } from '@/lib/api-client'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { ScrollArea } from '@/components/ui/scroll-area'
import { MessagesSkeleton } from '@/features/messages/MessagesSkeleton'
import { MessagesList } from '@/features/messages/MessagesList'
import { MessageComposer } from '@/features/messages/MessageComposer'
import type { Patient } from '@/types/api'

// Debounce hook to prevent excessive API calls
function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])

  return debouncedValue
}

export function MessagesPage() {
  const [searchParams] = useSearchParams()
  const [selectedPatient, setSelectedPatient] = useState<Patient | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const queryClient = useQueryClient()

  // Debounce search term to reduce API calls
  const debouncedSearch = useDebounce(searchTerm, 300)

  const { data: patientsData, isLoading: patientsLoading } = useQuery({
    queryKey: ['patients', { search: debouncedSearch, size: 50 }],
    queryFn: () => apiClient.patients.list({ search: debouncedSearch, size: 50 }),
    enabled: debouncedSearch.length === 0 || debouncedSearch.length >= 2
  })

  const { data: messagesData, isLoading: messagesLoading } = useQuery({
    queryKey: ['messages', { patient_id: selectedPatient?.id }],
    queryFn: () => apiClient.messages.list({ patient_id: selectedPatient!.id }),
    enabled: !!selectedPatient
  })

  // Auto-select patient from URL params
  React.useEffect(() => {
    const patientId = searchParams.get('patient')
    if (patientId && patientsData?.items) {
      const patient = patientsData.items.find((p: Patient) => p.id === patientId)
      if (patient) {
        setSelectedPatient(patient)
      }
    }
  }, [searchParams, patientsData])

  const getInitials = (name: string) => {
    const parts = name.split(' ').filter(n => n.length > 0)
    if (parts.length >= 2) {
      return `${parts[0]?.[0] || ''}${parts[parts.length - 1]?.[0] || ''}`.toUpperCase()
    }
    return name.substring(0, 2).toUpperCase()
  }

  const getAvatarColor = (name: string) => {
    const colors = [
      'bg-blue-500',
      'bg-green-500',
      'bg-yellow-500',
      'bg-red-500',
      'bg-teal-500',
      'bg-orange-500',
      'bg-cyan-500',
      'bg-emerald-500'
    ]
    const hash = name.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0)
    return colors[hash % colors.length]
  }

  const formatLastContact = (lastContact?: string) => {
    if (!lastContact) return 'Nunca'

    try {
      const date = new Date(lastContact)
      const now = new Date()
      const diffInMs = now.getTime() - date.getTime()
      const diffInMins = Math.floor(diffInMs / (1000 * 60))
      const diffInHours = Math.floor(diffInMs / (1000 * 60 * 60))
      const diffInDays = Math.floor(diffInMs / (1000 * 60 * 60 * 24))

      if (diffInMins < 1) return 'Agora'
      if (diffInMins < 60) return `${diffInMins}m atrás`
      if (diffInHours < 24) return `${diffInHours}h atrás`
      if (diffInDays < 7) return `${diffInDays}d atrás`

      return date.toLocaleDateString('pt-BR', {
        day: '2-digit',
        month: '2-digit'
      })
    } catch {
      return 'Data inválida'
    }
  }

  const filteredPatients = useMemo(() => {
    if (!patientsData?.items) return []
    return patientsData.items.filter((patient: Patient) =>
      (patient.name || '').toLowerCase().includes(debouncedSearch.toLowerCase()) ||
      patient.phone?.includes(debouncedSearch)
    )
  }, [patientsData, debouncedSearch])

  return (
    <div className="space-y-4 md:space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl md:text-3xl font-bold text-gray-900">Mensagens</h1>
        <p className="text-sm md:text-base text-gray-600">
          Gerencie conversas com os pacientes
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 md:gap-6 min-h-[calc(100dvh-10rem)] md:min-h-[calc(100dvh-12rem)]">
        {/* Patients List */}
        <Card className="lg:col-span-1 flex flex-col max-h-[calc(100dvh-10rem)]">
          <CardHeader>
            <CardTitle>Conversas</CardTitle>
            <CardDescription>
              Selecione um paciente para visualizar as mensagens
            </CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <div className="p-4 border-b">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <Input
                  placeholder="Buscar pacientes..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>

            <ScrollArea className="h-[400px] md:h-[500px] flex-1">
              {patientsLoading ? (
                <MessagesSkeleton />
              ) : filteredPatients.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-8 px-4 text-center">
                  <User2 className="h-12 w-12 text-gray-300 mb-3" />
                  <p className="text-sm text-gray-500">
                    {searchTerm ? 'Nenhum paciente encontrado' : 'Nenhuma conversa ainda'}
                  </p>
                </div>
              ) : (
                <div className="space-y-1 p-2">
                  {filteredPatients.map((patient: Patient) => (
                    <div
                      key={patient.id}
                      className={`flex items-center space-x-3 p-3 rounded-lg cursor-pointer transition-colors ${selectedPatient?.id === patient.id
                        ? 'bg-blue-50 border border-blue-200'
                        : 'hover:bg-gray-50'
                        }`}
                      onClick={() => setSelectedPatient(patient)}
                    >
                      <Avatar className="h-12 w-12 flex-shrink-0">
                        <AvatarImage src="" alt={patient.name} />
                        <AvatarFallback className={`${getAvatarColor(patient.name)} text-white text-sm font-semibold`}>
                          {getInitials(patient.name)}
                        </AvatarFallback>
                      </Avatar>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between mb-1">
                          <p className="font-semibold text-gray-900 truncate">
                            {patient.name}
                          </p>
                          <span className="text-xs text-gray-400 ml-2 flex-shrink-0">
                            {formatLastContact(patient.last_contact)}
                          </span>
                        </div>
                        <div className="flex items-center space-x-2">
                          <Phone className="h-3 w-3 text-gray-400 flex-shrink-0" />
                          <p className="text-sm text-gray-500 truncate">
                            {patient.phone}
                          </p>
                        </div>
                        <div className="flex items-center justify-between mt-1">
                          <Badge variant="outline" className="text-xs">
                            {patient.status}
                          </Badge>
                          {(patient.unread_count || 0) > 0 && (
                            <Badge className="bg-blue-600 text-white text-xs">
                              {patient.unread_count}
                            </Badge>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </ScrollArea>
          </CardContent>
        </Card>

        {/* Messages Area */}
        <div className="lg:col-span-2 space-y-6">
          {selectedPatient ? (
            <>
              {/* Messages List */}
              <MessagesList
                messages={messagesData?.items || []}
                isLoading={messagesLoading}
                patientName={selectedPatient.name}
              />

              {/* Message Composer */}
              <MessageComposer
                patientId={selectedPatient.id}
                patientName={selectedPatient.name}
                onMessageSent={() => {
                  // Refresh messages query for real-time updates
                  queryClient.invalidateQueries({
                    queryKey: ['messages', { patient_id: selectedPatient.id }]
                  })
                }}
              />
            </>
          ) : (
            <Card className="h-full">
              <CardContent className="h-full flex items-center justify-center">
                <div className="text-center">
                  <div className="mx-auto h-12 w-12 flex items-center justify-center rounded-full bg-gray-100 mb-4">
                    <MessageSquare className="h-6 w-6 text-gray-400" />
                  </div>
                  <h3 className="text-lg font-medium text-gray-900 mb-2">
                    Selecione uma conversa
                  </h3>
                  <p className="text-gray-500">
                    Escolha um paciente da lista para visualizar e enviar mensagens
                  </p>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
