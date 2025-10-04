/// <reference types="vite/client" />

import React, { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useMedicoAuth } from '../../contexts/MedicoAuthContext'
import { ChevronDown, Phone, Mail, Calendar, User, FileText } from 'lucide-react'

interface Paciente {
  id: number
  nome: string
  cpf: string
  data_nascimento: string
  telefone: string
  email: string
}

export default function PacientesList() {
  const navigate = useNavigate()
  const { state } = useMedicoAuth()
  const [pacientes, setPacientes] = useState<Paciente[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [expandedCards, setExpandedCards] = useState<Set<number>>(new Set())

  useEffect(() => {
    fetchPacientes()
  }, [])

  const fetchPacientes = async () => {
    try {
      setLoading(true)
      const apiUrl = import.meta.env['VITE_API_URL']
      const response = await fetch(`${apiUrl}/api/pacientes`, {
        headers: {
          'Authorization': `Bearer ${state.token}`,
        },
      })

      if (!response.ok) {
        throw new Error('Erro ao buscar pacientes')
      }

      const data = await response.json()
      setPacientes(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro desconhecido')
    } finally {
      setLoading(false)
    }
  }

  const filteredPacientes = pacientes.filter(paciente =>
    paciente.nome.toLowerCase().includes(searchTerm.toLowerCase()) ||
    paciente.cpf.includes(searchTerm)
  )

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('pt-BR')
  }

  const calculateAge = (birthDate: string) => {
    const today = new Date()
    const birth = new Date(birthDate)
    let age = today.getFullYear() - birth.getFullYear()
    const monthDiff = today.getMonth() - birth.getMonth()
    if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birth.getDate())) {
      age--
    }
    return age
  }

  const getInitials = (name: string) => {
    const names = name.split(' ').filter(n => n.length > 0)
    if (names.length >= 2) {
      const first = names[0]?.[0] || ''
      const last = names[names.length - 1]?.[0] || ''
      return `${first}${last}`.toUpperCase()
    }
    return name.substring(0, 2).toUpperCase()
  }

  const getAvatarColor = (id: number) => {
    const colors = [
      'bg-blue-500',
      'bg-green-500',
      'bg-yellow-500',
      'bg-red-500',
      'bg-indigo-500',
      'bg-pink-500',
      'bg-teal-500',
      'bg-orange-500'
    ]
    return colors[id % colors.length]
  }

  const toggleCard = (id: number) => {
    setExpandedCards(prev => {
      const newSet = new Set(prev)
      if (newSet.has(id)) {
        newSet.delete(id)
      } else {
        newSet.add(id)
      }
      return newSet
    })
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Carregando pacientes...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Meus Pacientes</h1>
              <p className="text-sm text-gray-600">Lista de pacientes ativos</p>
            </div>
            <button
              onClick={() => navigate('/medico/dashboard')}
              className="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors"
            >
              Voltar
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Search */}
        <div className="mb-6">
          <input
            type="text"
            placeholder="Buscar por nome ou CPF..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4">
            <p className="text-red-800">{error}</p>
          </div>
        )}

        {/* Pacientes Cards Grid */}
        {filteredPacientes.length === 0 ? (
          <div className="bg-white rounded-lg shadow p-12 text-center">
            <User className="mx-auto h-12 w-12 text-gray-400" />
            <h3 className="mt-4 text-lg font-medium text-gray-900">Nenhum paciente encontrado</h3>
            <p className="mt-2 text-sm text-gray-500">
              {searchTerm ? 'Tente ajustar sua busca' : 'Ainda não há pacientes cadastrados'}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredPacientes.map((paciente) => {
              const isExpanded = expandedCards.has(paciente.id)
              const age = calculateAge(paciente.data_nascimento)

              return (
                <div
                  key={paciente.id}
                  className="bg-white rounded-lg shadow-md hover:shadow-xl transition-all duration-300 overflow-hidden border border-gray-200 hover:border-blue-300"
                >
                  {/* Card Header - Always Visible */}
                  <div
                    className="p-6 cursor-pointer select-none"
                    onClick={() => toggleCard(paciente.id)}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-center space-x-4 flex-1">
                        {/* Avatar */}
                        <div className={`${getAvatarColor(paciente.id)} w-14 h-14 rounded-full flex items-center justify-center text-white font-bold text-lg flex-shrink-0`}>
                          {getInitials(paciente.nome)}
                        </div>

                        {/* Name and Age */}
                        <div className="flex-1 min-w-0">
                          <h3 className="text-lg font-semibold text-gray-900 truncate">
                            {paciente.nome}
                          </h3>
                          <p className="text-sm text-gray-500 flex items-center mt-1">
                            <Calendar className="w-4 h-4 mr-1" />
                            {age} anos
                          </p>
                        </div>
                      </div>

                      {/* Expand/Collapse Icon */}
                      <ChevronDown
                        className={`w-5 h-5 text-gray-400 transition-transform duration-300 flex-shrink-0 ml-2 ${
                          isExpanded ? 'transform rotate-180' : ''
                        }`}
                      />
                    </div>

                    {/* Quick Action Button - Collapsed View */}
                    {!isExpanded && (
                      <div className="mt-4">
                        <Link
                          to={`/medico/prontuario/${paciente.id}`}
                          className="inline-flex items-center text-sm text-blue-600 hover:text-blue-800 font-medium"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <FileText className="w-4 h-4 mr-1" />
                          Ver Prontuário
                        </Link>
                      </div>
                    )}
                  </div>

                  {/* Expanded Content */}
                  <div
                    className={`transition-all duration-300 ease-in-out ${
                      isExpanded ? 'max-h-96 opacity-100' : 'max-h-0 opacity-0'
                    } overflow-hidden`}
                  >
                    <div className="px-6 pb-6 space-y-3 border-t border-gray-100 pt-4">
                      {/* Email */}
                      <div className="flex items-start">
                        <Mail className="w-4 h-4 text-gray-400 mr-3 mt-0.5 flex-shrink-0" />
                        <div className="flex-1 min-w-0">
                          <p className="text-xs text-gray-500 uppercase tracking-wide">Email</p>
                          <p className="text-sm text-gray-900 truncate">{paciente.email}</p>
                        </div>
                      </div>

                      {/* Phone */}
                      <div className="flex items-start">
                        <Phone className="w-4 h-4 text-gray-400 mr-3 mt-0.5 flex-shrink-0" />
                        <div className="flex-1">
                          <p className="text-xs text-gray-500 uppercase tracking-wide">Telefone</p>
                          <p className="text-sm text-gray-900">{paciente.telefone}</p>
                        </div>
                      </div>

                      {/* CPF */}
                      <div className="flex items-start">
                        <User className="w-4 h-4 text-gray-400 mr-3 mt-0.5 flex-shrink-0" />
                        <div className="flex-1">
                          <p className="text-xs text-gray-500 uppercase tracking-wide">CPF</p>
                          <p className="text-sm text-gray-900">{paciente.cpf}</p>
                        </div>
                      </div>

                      {/* Birth Date */}
                      <div className="flex items-start">
                        <Calendar className="w-4 h-4 text-gray-400 mr-3 mt-0.5 flex-shrink-0" />
                        <div className="flex-1">
                          <p className="text-xs text-gray-500 uppercase tracking-wide">Data de Nascimento</p>
                          <p className="text-sm text-gray-900">{formatDate(paciente.data_nascimento)}</p>
                        </div>
                      </div>

                      {/* Action Button - Expanded View */}
                      <div className="pt-3">
                        <Link
                          to={`/medico/prontuario/${paciente.id}`}
                          className="block w-full text-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
                          onClick={(e) => e.stopPropagation()}
                        >
                          Ver Prontuário Completo
                        </Link>
                      </div>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {/* Stats */}
        <div className="mt-6 bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-600">
            Total de pacientes: <span className="font-semibold">{filteredPacientes.length}</span>
          </p>
        </div>
      </main>
    </div>
  )
}