/// <reference types="vite/client" />

import React, { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { apiClient } from '../../lib/api-client'

interface Paciente {
  id: string
  nome: string
  cpf: string
  data_nascimento: string
  telefone: string
  email: string
}

interface Consulta {
  id: string
  data_consulta: string
  diagnostico?: string
  observacoes?: string
  medico_nome?: string
}

export default function ProntuarioView() {
  const { pacienteId } = useParams<{ pacienteId: string }>()
  const navigate = useNavigate()
  const [paciente, setPaciente] = useState<Paciente | null>(null)
  const [consultas, setConsultas] = useState<Consulta[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchProntuario = useCallback(async () => {
    try {
      setLoading(true)

      // Fetch paciente data from backend
      const p = await apiClient.patients.get(pacienteId as string)
      const mappedPaciente: Paciente = {
        id: p.id,
        nome: p.name,
        cpf: p.cpf || '',
        data_nascimento: p.birth_date || '',
        telefone: p.phone || '',
        email: p.email || ''
      }
      setPaciente(mappedPaciente)

      // Fetch timeline as a proxy for consultations/history
      try {
        const timeline = await apiClient.patients.timeline(pacienteId as string)
        const mappedConsultas: Consulta[] = (timeline.events || []).map((e) => ({
          id: e.id || `${Date.now()}-${Math.random()}`,
          data_consulta: e.created_at || new Date().toISOString(),
          diagnostico: e.title || e.event_type,
          observacoes: e.description,
          medico_nome: ''
        }))
        setConsultas(mappedConsultas)
      } catch {
        setConsultas([])
      }

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro desconhecido')
    } finally {
      setLoading(false)
    }
  }, [pacienteId])

  useEffect(() => {
    if (pacienteId) {
      fetchProntuario()
    }
  }, [pacienteId, fetchProntuario])

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('pt-BR')
  }

  const calculateAge = (birthDate?: string) => {
    const today = new Date()
    const birth = birthDate ? new Date(birthDate) : new Date()
    let age = today.getFullYear() - birth.getFullYear()
    const monthDiff = today.getMonth() - birth.getMonth()
    if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birth.getDate())) {
      age--
    }
    return age
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Carregando prontuário...</p>
        </div>
      </div>
    )
  }

  if (error || !paciente) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-600">{error || 'Paciente não encontrado'}</p>
          <button
            onClick={() => navigate('/medico/pacientes')}
            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Voltar para lista
          </button>
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
              <h1 className="text-2xl font-bold text-gray-900">Prontuário Médico</h1>
              <p className="text-sm text-gray-600">Visualização completa do paciente</p>
            </div>
            <button
              onClick={() => navigate('/medico/pacientes')}
              className="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors"
            >
              Voltar
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Paciente Info */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Dados do Paciente</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <p className="text-sm text-gray-600">Nome Completo</p>
              <p className="text-lg font-medium text-gray-900">{paciente.nome}</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">CPF</p>
              <p className="text-lg font-medium text-gray-900">{paciente.cpf || '-'}</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Data de Nascimento</p>
              <p className="text-lg font-medium text-gray-900">
                {paciente.data_nascimento ? formatDate(paciente.data_nascimento) : '-'} ({calculateAge(paciente.data_nascimento)} anos)
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Telefone</p>
              <p className="text-lg font-medium text-gray-900">{paciente.telefone || '-'}</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Email</p>
              <p className="text-lg font-medium text-gray-900">{paciente.email || '-'}</p>
            </div>
          </div>
        </div>

        {/* Consultas History */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Histórico de Consultas</h2>

          {consultas.length === 0 ? (
            <div className="text-center py-8">
              <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <p className="mt-2 text-gray-500">Nenhuma consulta registrada</p>
            </div>
          ) : (
            <div className="space-y-4">
              {consultas.map((consulta) => (
                <div key={consulta.id} className="border border-gray-200 rounded-lg p-4">
                  <div className="flex justify-between items-start mb-2">
                    <div>
                      <p className="font-medium text-gray-900">
                        Consulta - {formatDate(consulta.data_consulta)}
                      </p>
                      <p className="text-sm text-gray-600">Dr(a). {consulta.medico_nome}</p>
                    </div>
                  </div>

                  <div className="mt-3">
                    <p className="text-sm text-gray-600 font-medium">Diagnóstico:</p>
                    <p className="text-gray-900 mt-1">{consulta.diagnostico}</p>
                  </div>

                  {consulta.observacoes && (
                    <div className="mt-3">
                      <p className="text-sm text-gray-600 font-medium">Observações:</p>
                      <p className="text-gray-900 mt-1">{consulta.observacoes}</p>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  )
}