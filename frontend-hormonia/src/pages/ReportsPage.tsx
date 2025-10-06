import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Plus, Download, Eye, Calendar, Filter, FileText, Trash2, RefreshCw } from 'lucide-react'
import { apiClient } from '../lib/api-client'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { LoadingSpinner } from '../components/ui/loading-spinner'
import { ReportCard } from '../components/reports/ReportCard'
import { ReportGenerator } from '../components/reports/ReportGenerator'
import { ReportPreviewModal } from '../components/reports/ReportPreviewModal'
import { useToast } from '@/components/ui/use-toast'
import { useAuth } from '../hooks/useAuth'
import { createLogger } from '../lib/logger'

const logger = createLogger('ReportsPage')
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Label } from '@/components/ui/label'

export function ReportsPage() {
  const [currentPage, setCurrentPage] = useState(1)
  const [showFilters, setShowFilters] = useState(false)
  const [showGenerateDialog, setShowGenerateDialog] = useState(false)
  const [showPreviewModal, setShowPreviewModal] = useState(false)
  const [previewReportId, setPreviewReportId] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [typeFilter, setTypeFilter] = useState<string>('')
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [reportToDelete, setReportToDelete] = useState<string | null>(null)
  const [downloading, setDownloading] = useState<string | null>(null)
  const { toast } = useToast()
  const { user, token } = useAuth()

  const { data: reportsData, isLoading, refetch } = useQuery({
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

      if (statusFilter) {
        params['status'] = statusFilter
      }

      if (typeFilter) {
        params['type'] = typeFilter
      }

      return apiClient.reports.list(params)
    }
  })

  const handleViewReport = (reportId: string) => {
    setPreviewReportId(reportId)
    setShowPreviewModal(true)
  }

  const handleDownloadReport = async (reportId: string) => {
    try {
      setDownloading(reportId)

      // Make direct request to download endpoint to get blob
      const response = await fetch(`${apiClient.getBaseURL()}/api/v1/reports/${reportId}/download`, {
        method: 'GET',
        headers: {
          ['Authorization']: `Bearer ${token}`
        }
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
    } catch (error: any) {
      logger.error('Download error', { reportId, error })
      toast({
        title: 'Erro no download',
        description: error.message || 'Não foi possível baixar o relatório.',
        variant: 'destructive'
      })
    } finally {
      setDownloading(null)
    }
  }

  const getReportsStats = () => {
    const reports = reportsData?.items || []
    return {
      total: reports.length,
      completed: reports.filter(r => r.status === 'completed').length,
      generating: reports.filter(r => r.status === 'generating').length,
      failed: reports.filter(r => r.status === 'failed').length
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
          <div className="flex items-center space-x-4">
            <div className="flex-1 relative">
              <Input
                placeholder="Buscar relatórios..."
                className="pl-4"
              />
            </div>
            <Button
              variant="outline"
              onClick={() => setShowFilters(!showFilters)}
            >
              <Filter className="mr-2 h-4 w-4" />
              Filtros
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Reports Grid */}
      <div>
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <LoadingSpinner size="lg" />
          </div>
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
            {reportsData?.items?.map((report: any) => (
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
