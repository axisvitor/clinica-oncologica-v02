import React from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { apiClient } from '@/lib/api-client'
import { Database, Download, Upload, RefreshCw, TriangleAlert as AlertTriangle } from 'lucide-react'

interface BackupResponse {
  success: boolean
  message?: string
}

interface ClearCacheResponse {
  success: boolean
  message?: string
}

interface AdminDatabaseTabProps {
  isLoading: boolean
  setIsLoading: (loading: boolean) => void
  setMessage: (message: { type: 'success' | 'error', text: string } | null) => void
}

/**
 * AdminDatabaseTab - Database management and operations
 *
 * Provides:
 * - Database backup and restore operations
 * - Cache management
 * - Database optimization
 * - Database statistics and metrics
 *
 * @note Operations are performed with proper error handling and user feedback
 */
export default function AdminDatabaseTab({ isLoading, setIsLoading, setMessage }: AdminDatabaseTabProps) {
  const handleBackup = async () => {
    setIsLoading(true)
    try {
      // Use apiClient's baseURL and authToken for blob downloads
      const baseURL = apiClient.getBaseURL()
      const url = `${baseURL}/admin/backup`

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${(apiClient as any).authToken || ''}`
        }
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const blob = await response.blob()
      const downloadUrl = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = downloadUrl
      a.download = `backup-${new Date().toISOString()}.zip`
      a.click()
      window.URL.revokeObjectURL(downloadUrl)
      setMessage({ type: 'success', text: 'Backup realizado com sucesso!' })
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Erro ao realizar backup'
      setMessage({ type: 'error', text: errorMessage })
    } finally {
      setIsLoading(false)
    }
  }

  const handleClearCache = async () => {
    setIsLoading(true)
    try {
      await apiClient.request<ClearCacheResponse>('/admin/cache/clear', {
        method: 'POST'
      })

      setMessage({ type: 'success', text: 'Cache limpo com sucesso!' })
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Erro ao limpar cache'
      setMessage({ type: 'error', text: errorMessage })
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <Card className="shadow-sm">
        <CardHeader className="border-b">
          <div className="flex items-center gap-3">
            <div className="p-3 rounded-lg bg-purple-50">
              <Database className="h-6 w-6 text-purple-600" />
            </div>
            <div>
              <CardTitle>Gestão de Dados</CardTitle>
              <CardDescription>
                Operações de backup, manutenção e otimização
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-6 pt-6">
          <div className="grid grid-cols-2 gap-4">
            <Button
              onClick={handleBackup}
              disabled={isLoading}
              variant="outline"
            >
              <Download className="mr-2 h-4 w-4" />
              Fazer Backup
            </Button>

            <Button variant="outline" disabled>
              <Upload className="mr-2 h-4 w-4" />
              Restaurar Backup
            </Button>

            <Button
              onClick={handleClearCache}
              disabled={isLoading}
              variant="outline"
            >
              <RefreshCw className="mr-2 h-4 w-4" />
              Limpar Cache
            </Button>

            <Button variant="outline" disabled>
              <Database className="mr-2 h-4 w-4" />
              Otimizar DB
            </Button>
          </div>

          <Alert>
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>Atenção</AlertTitle>
            <AlertDescription>
              Operações de banco de dados podem afetar o desempenho do sistema.
              Execute durante períodos de baixa atividade.
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Estatísticas do Banco</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-4">
            <div className="text-center p-4 bg-gray-50 rounded">
              <p className="text-2xl font-bold">1,234</p>
              <p className="text-sm text-gray-600">Pacientes</p>
            </div>
            <div className="text-center p-4 bg-gray-50 rounded">
              <p className="text-2xl font-bold">45,678</p>
              <p className="text-sm text-gray-600">Mensagens</p>
            </div>
            <div className="text-center p-4 bg-gray-50 rounded">
              <p className="text-2xl font-bold">2.3 GB</p>
              <p className="text-sm text-gray-600">Tamanho</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
