import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Plus, Download, Eye, Calendar, Filter, FileText } from 'lucide-react'
import { apiClient } from '@/lib/api-client'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { ReportsSkeleton } from '@/features/reports/ReportsSkeleton'
import { ReportCard } from '@/features/reports/ReportCard'
import { ReportGenerator } from '@/features/reports/ReportGenerator'
import { useToast } from '@/components/ui/use-toast'
import { createLogger } from '@/lib/logger'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'

const logger = createLogger('ReportsPage')


export function ReportsPage() {
  const currentPage = 1
  const [showFilters, setShowFilters] = useState(false)
  const [showGenerateDialog, setShowGenerateDialog] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [typeFilter, setTypeFilter] = useState<string>('all')
  const [downloading, setDownloading] = useState<string | null>(null)
  const { toast } = useToast()

  const { data: reportsData, isLoading } = useQuery({
    queryKey: ['reports', { page: currentPage, size: 20, search: searchQuery, status: statusFilter, type: typeFilter }],
    queryFn: async () => {
      // Build query parameters from filters
      const params: Record<string, string | number> = {
        page: currentPage,
        size: 20
      }

      if (searchQuery.trim()) {
        params['search'] = searchQuery.trim()
      }

      if (statusFilter && statusFilter !== 'all') {
        params['status'] = statusFilter
      }

      if (typeFilter && typeFilter !== 'all') {
        params['type'] = typeFilter
      }

      return apiClient.reports.list(params)
    }
  })

  const handleViewReport = (reportId: string) => {
    toast({ title: 'Visualização de relatório', description: `Preview do relatório ${reportId} em breve.` })
  }

  const handleDownloadReport = async (reportId: string) => {
    try {
      setDownloading(reportId)

      // Make direct request to download endpoint to get blob
      const response = await fetch(`${apiClient.getBaseURL()}/api/v2/reports/${reportId}/download`, {
        method: 'GET',
        headers: {
          ...apiClient.getSessionHeaders(),
        },
        credentials: 'include'
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ message: 'Download failed' }))
        throw new Error(errorData.message || 'Download failed')
      }

      // Get content type and filename from headers
      const contentType = response.headers.get('content-type') || 'application/octet-stream'
      const contentDisposition = response.headers.get('content-disposition')

      // Extract filename from content-disposition header or generate default
      let filename = `report-${reportId}-${Date.now()}`
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename[^;=\n]*=(['"]?)([^'"\n]*\.[^'"\n]*)\1?/)
        if (filenameMatch && filenameMatch[2]) {
          filename = filenameMatch[2]
        }
      } else {
        // Determine file extension based on content type
        if (contentType.includes('pdf')) {
          filename += '.pdf'
        } else if (contentType.includes('excel') || contentType.includes('spreadsheetml')) {
          filename += '.xlsx'
        } else if (contentType.includes('csv')) {
          filename += '.csv'
        } else if (contentType.includes('json')) {
          filename += '.json'
        } else {
          filename += '.txt'
        }
      }

      // Get blob from response
      const blob = await response.blob()

      // Create download link
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()

      // Cleanup
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)

      toast({
        title: 'Download concluído',
        description: `Relatório ${filename} baixado com sucesso.`,
      })
    } catch (error: unknown) {
      logger.error('Download error', { reportId, error })
      const errorMessage = error instanceof Error ? error.message : 'Não foi possível baixar o relatório.'
      toast({
        title: 'Erro no download',
        description: errorMessage,
        variant: 'destructive'
      })
    } finally {
      setDownloading(null)
    }
  }

  const getReportsStats = () => {
    const reports = reportsData?.items || []
    return {
      total: reportsData?.total || 0,
      completed: reports.filter((r) => r.status === 'completed').length,
      generating: reports.filter((r) => r.status === 'generating').length,
      failed: reports.filter((r) => r.status === 'failed').length
    }
  }

  const stats = getReportsStats()

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Relatórios</h1>
          <p className="text-gray-600">
            Gere e gerencie relatórios médicos detalhados
          </p>
        </div>
        <Button onClick={() => setShowGenerateDialog(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Novo Relatório
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Total de Relatórios
            </CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.total}</div>
            <p className="text-xs text-muted-foreground">
              Relatórios no sistema
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Concluídos
            </CardTitle>
            <Download className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.completed}</div>
            <p className="text-xs text-muted-foreground">
              Prontos para download
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Em Processamento
            </CardTitle>
            <Calendar className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.generating}</div>
            <p className="text-xs text-muted-foreground">
              Sendo gerados
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Com Erro
            </CardTitle>
            <Eye className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats.failed}</div>
            <p className="text-xs text-muted-foreground">
              Falharam na geração
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="space-y-4">
            <div className="flex items-center space-x-4">
              <div className="flex-1 relative">
                <Input
                  name="searchQuery"
                  placeholder="Buscar relatórios..."
                  className="pl-4"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
              <Button
                variant="outline"
                onClick={() => setShowFilters(!showFilters)}
                className={showFilters ? 'bg-muted' : ''}
              >
                <Filter className="mr-2 h-4 w-4" />
                Filtros
              </Button>
            </div>

            {showFilters && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Status</label>
                  <Select name="statusFilter" value={statusFilter} onValueChange={setStatusFilter}>
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Selecione o status" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">Todos os status</SelectItem>
                      <SelectItem value="completed">Concluídos</SelectItem>
                      <SelectItem value="generating">Processando</SelectItem>
                      <SelectItem value="failed">Falharam</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Tipo</label>
                  <Select name="typeFilter" value={typeFilter} onValueChange={setTypeFilter}>
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="Selecione o tipo" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">Todos os tipos</SelectItem>
                      <SelectItem value="monthly">Relatório Mensal</SelectItem>
                      <SelectItem value="quarterly">Relatório Trimestral</SelectItem>
                      <SelectItem value="treatment_progress">Progresso do Tratamento</SelectItem>
                      <SelectItem value="engagement">Engajamento</SelectItem>
                      <SelectItem value="custom">Personalizado</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Reports Grid */}
      <div>
        {isLoading ? (
          <ReportsSkeleton />
        ) : reportsData?.items?.length === 0 ? (
          <Card>
            <CardContent className="pt-6">
              <div className="text-center py-8">
                <Calendar className="mx-auto h-12 w-12 text-gray-400 mb-4" />
                <p className="text-gray-500">Nenhum relatório encontrado</p>
                <p className="text-sm text-gray-400">
                  Crie seu primeiro relatório clicando no botão acima
                </p>
              </div>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {reportsData?.items?.map((report) => (
              <ReportCard
                key={report.id}
                report={report}
                onView={handleViewReport}
                onDownload={handleDownloadReport}
                downloading={downloading === report.id}
              />
            ))}
          </div>
        )}
      </div>

      {/* Generate Report Dialog */}
      <ReportGenerator
        open={showGenerateDialog}
        onOpenChange={setShowGenerateDialog}
      />
    </div>
  )
}
