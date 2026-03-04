import React from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useMedicoAuth } from '@/app/providers/MedicoAuthContext'
import { useMedicoDashboardStats } from '@/hooks/api/useMedicoDashboardStats'
import { Skeleton } from '@/components/ui/skeleton'
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert'
import { createLogger } from '@/lib/logger'

const logger = createLogger('MedicoDashboard')

export default function MedicoDashboard() {
  const navigate = useNavigate()
  const { medico, signOut } = useMedicoAuth()
  const {
    data: stats,
    isLoading,
    error,
  } = useMedicoDashboardStats({
    refetchInterval: 120000, // 2 minutes
  })

  const handleLogout = async () => {
    try {
      logger.info('Logging out medico')
      await signOut()
      logger.info('Medico logged out successfully')
      navigate('/medico/login')
    } catch (error) {
      logger.error('Logout failed', { error })
      // Still navigate to login page even on error
      navigate('/medico/login')
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Dashboard Médico</h1>
              <p className="text-sm text-gray-600">Dr(a). {medico?.full_name}</p>
              <p className="text-xs text-gray-500">CRM: {medico?.crm}</p>
            </div>
            <button
              onClick={handleLogout}
              className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
            >
              Sair
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {/* Card: Pacientes */}
          <Link
            to="/medico/pacientes"
            className="bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition-shadow"
          >
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-gray-900">Meus Pacientes</h3>
                <p className="text-sm text-gray-600 mt-1">Visualizar lista completa</p>
              </div>
              <svg
                className="h-12 w-12 text-blue-600"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"
                />
              </svg>
            </div>
          </Link>

          {/* Card: Prontuários */}
          <div className="bg-white rounded-lg shadow-md p-6">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-gray-900">Prontuários</h3>
                <p className="text-sm text-gray-600 mt-1">Acessar prontuários</p>
              </div>
              <svg
                className="h-12 w-12 text-green-600"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
            </div>
          </div>

          {/* Card: Agenda */}
          <div className="bg-white rounded-lg shadow-md p-6">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-gray-900">Agenda</h3>
                <p className="text-sm text-gray-600 mt-1">Consultas e procedimentos</p>
              </div>
              <svg
                className="h-12 w-12 text-purple-600"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
                />
              </svg>
            </div>
          </div>
        </div>

        {/* Quick Stats */}
        <div className="mt-8 bg-white rounded-lg shadow-md p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Estatísticas Rápidas</h2>

          {isLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="text-center">
                  <Skeleton className="h-10 w-20 mx-auto mb-2" />
                  <Skeleton className="h-4 w-32 mx-auto" />
                </div>
              ))}
            </div>
          ) : error ? (
            <Alert variant="destructive">
              <AlertTitle>Erro ao carregar estatísticas</AlertTitle>
              <AlertDescription>
                {error instanceof Error ? error.message : 'Erro desconhecido'}
              </AlertDescription>
            </Alert>
          ) : stats ? (
            <>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="text-center">
                  <p className="text-3xl font-bold text-blue-600">
                    {stats.overview.total_patients}
                  </p>
                  <p className="text-sm text-gray-600">Pacientes Ativos</p>
                </div>
                <div className="text-center">
                  <p className="text-3xl font-bold text-green-600">
                    {stats.overview.active_treatments}
                  </p>
                  <p className="text-sm text-gray-600">Tratamentos Ativos</p>
                </div>
                <div className="text-center">
                  <p className="text-3xl font-bold text-purple-600">
                    {stats.overview.pending_reviews}
                  </p>
                  <p className="text-sm text-gray-600">Pendências</p>
                </div>
                <div className="text-center">
                  <p className="text-3xl font-bold text-orange-600">
                    {stats.overview.new_alerts_today}
                  </p>
                  <p className="text-sm text-gray-600">Alertas Hoje</p>
                </div>
              </div>

              {/* Engagement Section */}
              {stats.engagement_metrics && (
                <div className="mt-6 pt-6 border-t border-gray-200">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">Engajamento</h3>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="text-center">
                      <p className="text-2xl font-bold text-blue-600">
                        {stats.engagement_metrics.messages_today}
                      </p>
                      <p className="text-sm text-gray-600">Mensagens Hoje</p>
                    </div>
                    <div className="text-center">
                      <p className="text-2xl font-bold text-green-600">
                        {stats.engagement_metrics.response_rate_7d.toFixed(0)}%
                      </p>
                      <p className="text-sm text-gray-600">Taxa de Resposta (7d)</p>
                    </div>
                    <div className="text-center">
                      <p className="text-2xl font-bold text-purple-600">
                        {stats.engagement_metrics.avg_response_time_hours.toFixed(1)}h
                      </p>
                      <p className="text-sm text-gray-600">Tempo Médio</p>
                    </div>
                    <div className="text-center">
                      <p className="text-2xl font-bold text-indigo-600">
                        {stats.engagement_metrics.quizzes_completed_7d}
                      </p>
                      <p className="text-sm text-gray-600">Questionários (7d)</p>
                    </div>
                  </div>
                </div>
              )}

              {/* Alerts Section */}
              {stats.alerts_summary && (
                <div className="mt-6 pt-6 border-t border-gray-200">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">Alertas</h3>
                  <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                    <div className="text-center">
                      <p className="text-2xl font-bold text-gray-900">
                        {stats.alerts_summary.unacknowledged}
                      </p>
                      <p className="text-sm text-gray-600">Não Reconhecidos</p>
                    </div>
                    <div className="text-center">
                      <p className="text-2xl font-bold text-red-600">
                        {stats.alerts_summary.by_severity.critical}
                      </p>
                      <p className="text-sm text-gray-600">Críticos</p>
                    </div>
                    <div className="text-center">
                      <p className="text-2xl font-bold text-orange-600">
                        {stats.alerts_summary.by_severity.high}
                      </p>
                      <p className="text-sm text-gray-600">Altos</p>
                    </div>
                    <div className="text-center">
                      <p className="text-2xl font-bold text-yellow-600">
                        {stats.alerts_summary.by_severity.medium}
                      </p>
                      <p className="text-sm text-gray-600">Médios</p>
                    </div>
                    <div className="text-center">
                      <p className="text-2xl font-bold text-green-600">
                        {stats.alerts_summary.by_severity.low}
                      </p>
                      <p className="text-sm text-gray-600">Baixos</p>
                    </div>
                  </div>
                </div>
              )}

              {/* Timestamp */}
              <div className="mt-4 pt-4 border-t border-gray-200 text-sm text-gray-500 text-center">
                Última atualização: {new Date(stats.last_updated).toLocaleString('pt-BR')}
              </div>
            </>
          ) : null}
        </div>
      </main>
    </div>
  )
}
