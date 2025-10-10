import React, { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card'
import { Button } from '../ui/button'
import { Badge } from '../ui/badge'
import { Progress } from '../ui/progress'
import {
  CheckCircle,
  XCircle,
  AlertTriangle,
  Database,
  RefreshCw,
  Activity,
  HardDrive,
  Users,
  FileText
} from 'lucide-react'
import { Alert, AlertDescription } from '../ui/alert'
import { LoadingSpinner } from './LoadingSpinner'
import { toast } from '../../hooks/use-toast'
import { createLogger } from '../../lib/logger'
import { apiClient } from '../../lib/api-client'

const logger = createLogger('DatabaseChecker')

interface DatabaseTest {
  id: string
  name: string
  description: string
  status: 'pending' | 'running' | 'success' | 'error'
  duration?: number
  error?: string
  details?: any
}

interface DatabaseStats {
  version?: string
  uptime?: string
  connections?: number
  maxConnections?: number
  size?: string
  tables?: number
  indexes?: number
  lastBackup?: string
}

interface DatabaseCheckerProps {
  onComplete: () => void
  onError: (error: string) => void
}

export function DatabaseChecker({ onComplete, onError }: DatabaseCheckerProps) {
  const [tests, setTests] = useState<DatabaseTest[]>([
    {
      id: 'connection',
      name: 'Conexão com Banco',
      description: 'Verifica se é possível conectar ao banco de dados',
      status: 'pending'
    },
    {
      id: 'tables',
      name: 'Estrutura de Tabelas',
      description: 'Verifica se todas as tabelas necessárias existem',
      status: 'pending'
    },
    {
      id: 'indexes',
      name: 'Índices de Performance',
      description: 'Verifica se os índices de busca estão criados',
      status: 'pending'
    },
    {
      id: 'permissions',
      name: 'Permissões de Usuário',
      description: 'Verifica se o usuário tem as permissões necessárias',
      status: 'pending'
    },
    {
      id: 'migrations',
      name: 'Estado das Migrações',
      description: 'Verifica se todas as migrações foram aplicadas',
      status: 'pending'
    },
    {
      id: 'performance',
      name: 'Teste de Performance',
      description: 'Executa consultas de teste para medir performance',
      status: 'pending'
    }
  ])

  const [stats, setStats] = useState<DatabaseStats>({})
  const [isChecking, setIsChecking] = useState(false)
  const [currentTestIndex, setCurrentTestIndex] = useState(0)
  const [overallProgress, setOverallProgress] = useState(0)

  useEffect(() => {
    // Auto-start database checks
    handleCheckDatabase()
  }, [])

  const updateTestStatus = (
    id: string,
    status: DatabaseTest['status'],
    duration?: number,
    error?: string,
    details?: any
  ) => {
    setTests(prev => prev.map(test =>
      test.id === id
        ? { ...test, status, duration, error, details }
        : test
    ))
  }

  const handleCheckDatabase = async () => {
    setIsChecking(true)
    setCurrentTestIndex(0)
    setOverallProgress(0)
    logger.log('Starting database checks')

    try {
      // Reset all tests to pending
      setTests(prev => prev.map(test => ({ ...test, status: 'pending' as const })))

      for (let i = 0; i < tests.length; i++) {
        const test = tests[i]
        setCurrentTestIndex(i)
        updateTestStatus(test.id, 'running')

        const startTime = Date.now()

        try {
          await executeTest(test.id)
          const duration = Date.now() - startTime
          updateTestStatus(test.id, 'success', duration)
        } catch (error) {
          const duration = Date.now() - startTime
          const errorMessage = error instanceof Error ? error.message : 'Teste falhou'
          updateTestStatus(test.id, 'error', duration, errorMessage)
          logger.error(`Database test '${test.id}' failed:`, error)
        }

        // Update progress
        const progress = Math.round(((i + 1) / tests.length) * 100)
        setOverallProgress(progress)

        // Small delay for visual feedback
        await new Promise(resolve => setTimeout(resolve, 500))
      }

      // Load database stats
      await loadDatabaseStats()

      // Check results
      const failedTests = tests.filter(t => t.status === 'error')
      if (failedTests.length > 0) {
        onError(`Testes de banco falharam: ${failedTests.map(t => t.name).join(', ')}`)
      } else {
        toast({
          title: 'Banco de Dados Verificado',
          description: 'Todos os testes passaram com sucesso.',
        })
        onComplete()
      }

    } catch (error) {
      logger.error('Database check failed:', error)
      onError('Falha na verificação do banco de dados: ' + (error as Error).message)
    } finally {
      setIsChecking(false)
    }
  }

  const executeTest = async (testId: string): Promise<void> => {
    switch (testId) {
      case 'connection':
        await testConnection()
        break
      case 'tables':
        await testTableStructure()
        break
      case 'indexes':
        await testIndexes()
        break
      case 'permissions':
        await testPermissions()
        break
      case 'migrations':
        await testMigrations()
        break
      case 'performance':
        await testPerformance()
        break
      default:
        throw new Error(`Unknown test: ${testId}`)
    }
  }

  const testConnection = async () => {
    const response = await apiClient.get('/admin/database/health')
    if (!response.ok) {
      throw new Error('Falha na conexão com o banco de dados')
    }
  }

  const testTableStructure = async () => {
    const response = await apiClient.get('/admin/database/tables')
    const data = await response.json()

    const requiredTables = [
      'users', 'patients', 'consultations', 'treatments',
      'medications', 'reports', 'audit_logs'
    ]

    const missingTables = requiredTables.filter(
      table => !data.tables.includes(table)
    )

    if (missingTables.length > 0) {
      throw new Error(`Tabelas em falta: ${missingTables.join(', ')}`)
    }

    updateTestStatus('tables', 'running', undefined, undefined, {
      totalTables: data.tables.length,
      requiredTables: requiredTables.length
    })
  }

  const testIndexes = async () => {
    const response = await apiClient.get('/admin/database/indexes')
    const data = await response.json()

    const requiredIndexes = [
      'idx_patients_cpf',
      'idx_users_email',
      'idx_consultations_date',
      'idx_treatments_patient_id'
    ]

    const missingIndexes = requiredIndexes.filter(
      index => !data.indexes.some((idx: any) => idx.name === index)
    )

    if (missingIndexes.length > 0) {
      throw new Error(`Índices em falta: ${missingIndexes.join(', ')}`)
    }

    updateTestStatus('indexes', 'running', undefined, undefined, {
      totalIndexes: data.indexes.length,
      requiredIndexes: requiredIndexes.length
    })
  }

  const testPermissions = async () => {
    const response = await apiClient.get('/admin/database/permissions')
    const data = await response.json()

    const requiredPermissions = ['SELECT', 'INSERT', 'UPDATE', 'DELETE']
    const missingPermissions = requiredPermissions.filter(
      perm => !data.permissions.includes(perm)
    )

    if (missingPermissions.length > 0) {
      throw new Error(`Permissões em falta: ${missingPermissions.join(', ')}`)
    }

    updateTestStatus('permissions', 'running', undefined, undefined, {
      permissions: data.permissions
    })
  }

  const testMigrations = async () => {
    const response = await apiClient.get('/admin/database/migrations')
    const data = await response.json()

    if (data.pendingMigrations && data.pendingMigrations.length > 0) {
      throw new Error(`${data.pendingMigrations.length} migrações pendentes`)
    }

    updateTestStatus('migrations', 'running', undefined, undefined, {
      appliedMigrations: data.appliedMigrations?.length || 0,
      pendingMigrations: data.pendingMigrations?.length || 0
    })
  }

  const testPerformance = async () => {
    const response = await apiClient.get('/admin/database/performance')
    const data = await response.json()

    // Check if average query time is reasonable (< 100ms)
    if (data.averageQueryTime > 100) {
      throw new Error(`Performance baixa: ${data.averageQueryTime}ms por consulta`)
    }

    updateTestStatus('performance', 'running', undefined, undefined, {
      averageQueryTime: data.averageQueryTime,
      slowQueries: data.slowQueries || 0
    })
  }

  const loadDatabaseStats = async () => {
    try {
      const response = await apiClient.get('/admin/database/stats')
      const data = await response.json()
      setStats(data)
    } catch (error) {
      logger.error('Failed to load database stats:', error)
    }
  }

  const getStatusIcon = (status: DatabaseTest['status']) => {
    switch (status) {
      case 'success':
        return <CheckCircle className="w-5 h-5 text-green-500" />
      case 'error':
        return <XCircle className="w-5 h-5 text-red-500" />
      case 'running':
        return <RefreshCw className="w-5 h-5 text-blue-500 animate-spin" />
      default:
        return <div className="w-5 h-5 border-2 border-gray-300 rounded-full" />
    }
  }

  const getStatusBadge = (status: DatabaseTest['status']) => {
    switch (status) {
      case 'success':
        return <Badge variant="default" className="bg-green-100 text-green-800">OK</Badge>
      case 'error':
        return <Badge variant="destructive">Erro</Badge>
      case 'running':
        return <Badge variant="default" className="bg-blue-100 text-blue-800">Testando</Badge>
      default:
        return <Badge variant="outline">Pendente</Badge>
    }
  }

  const formatDuration = (ms?: number) => {
    if (!ms) return ''
    return `${ms}ms`
  }

  return (
    <div className="space-y-6">
      {/* Progress Overview */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center space-x-2">
                <Database className="w-5 h-5" />
                <span>Verificação do Banco de Dados</span>
              </CardTitle>
              <CardDescription>
                Executando testes de conectividade e integridade
              </CardDescription>
            </div>
            <div className="text-right">
              <div className="text-2xl font-bold text-blue-600">{overallProgress}%</div>
              <div className="text-sm text-gray-600">Progresso</div>
            </div>
          </div>
          {isChecking && (
            <div className="mt-4">
              <Progress value={overallProgress} />
              <div className="text-sm text-gray-600 mt-2">
                Teste {currentTestIndex + 1} de {tests.length}:
                {tests[currentTestIndex]?.name}
              </div>
            </div>
          )}
        </CardHeader>
      </Card>

      {/* Database Stats */}
      {Object.keys(stats).length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card>
            <CardContent className="pt-4">
              <div className="flex items-center space-x-2">
                <Activity className="w-4 h-4 text-blue-500" />
                <div>
                  <div className="text-sm font-medium">Versão</div>
                  <div className="text-xs text-gray-600">{stats.version || 'N/A'}</div>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4">
              <div className="flex items-center space-x-2">
                <Users className="w-4 h-4 text-green-500" />
                <div>
                  <div className="text-sm font-medium">Conexões</div>
                  <div className="text-xs text-gray-600">
                    {stats.connections || 0}/{stats.maxConnections || 0}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4">
              <div className="flex items-center space-x-2">
                <HardDrive className="w-4 h-4 text-purple-500" />
                <div>
                  <div className="text-sm font-medium">Tamanho</div>
                  <div className="text-xs text-gray-600">{stats.size || 'N/A'}</div>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4">
              <div className="flex items-center space-x-2">
                <FileText className="w-4 h-4 text-orange-500" />
                <div>
                  <div className="text-sm font-medium">Tabelas</div>
                  <div className="text-xs text-gray-600">{stats.tables || 0}</div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Test Results */}
      <Card>
        <CardHeader>
          <CardTitle>Resultados dos Testes</CardTitle>
          <CardDescription>
            Status detalhado de cada verificação do banco de dados
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {tests.map((test, index) => (
            <div
              key={test.id}
              className={`flex items-center justify-between p-4 border rounded-lg transition-colors ${
                index === currentTestIndex && isChecking
                  ? 'bg-blue-50 border-blue-200'
                  : ''
              }`}
            >
              <div className="flex items-start space-x-3 flex-1">
                {getStatusIcon(test.status)}
                <div className="flex-1">
                  <div className="flex items-center space-x-2">
                    <h4 className="font-medium">{test.name}</h4>
                    {test.duration && (
                      <span className="text-xs text-gray-500">
                        ({formatDuration(test.duration)})
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-gray-600 mt-1">{test.description}</p>
                  {test.details && (
                    <div className="mt-2 text-xs text-gray-500">
                      {Object.entries(test.details).map(([key, value]) => (
                        <span key={key} className="mr-4">
                          {key}: {String(value)}
                        </span>
                      ))}
                    </div>
                  )}
                  {test.error && (
                    <Alert className="mt-2" variant="destructive">
                      <AlertDescription className="text-xs">{test.error}</AlertDescription>
                    </Alert>
                  )}
                </div>
              </div>
              <div className="flex-shrink-0">
                {getStatusBadge(test.status)}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      {/* Action Buttons */}
      <div className="flex flex-col sm:flex-row gap-4">
        <Button
          onClick={handleCheckDatabase}
          disabled={isChecking}
          className="flex-1"
        >
          {isChecking ? (
            <>
              <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
              Testando...
            </>
          ) : (
            <>
              <RefreshCw className="w-4 h-4 mr-2" />
              Testar Novamente
            </>
          )}
        </Button>

        <Button
          variant="outline"
          onClick={() => {
            toast({
              title: 'Logs de Banco',
              description: 'Funcionalidade em desenvolvimento.',
            })
          }}
          className="flex-1 sm:flex-none"
        >
          <FileText className="w-4 h-4 mr-2" />
          Ver Logs
        </Button>
      </div>

      {isChecking && (
        <div className="text-center py-8">
          <LoadingSpinner
            size="lg"
            text={`Executando: ${tests[currentTestIndex]?.name}...`}
            showProgress
            progress={overallProgress}
          />
        </div>
      )}
    </div>
  )
}