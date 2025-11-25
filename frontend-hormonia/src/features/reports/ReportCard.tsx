import React from 'react'
import { formatDistanceToNow } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import { FileText, Download, Eye, Clock, CheckCircle, AlertCircle, Loader2 } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import type { Report } from '@/lib/api-client/types'

interface ReportCardProps {
  report: Report
  onView?: (reportId: string) => void
  onDownload?: (reportId: string) => void
  downloading?: boolean
}

export function ReportCard({ report, onView, onDownload, downloading = false }: ReportCardProps) {
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return CheckCircle
      case 'generating':
        return Clock
      case 'failed':
        return AlertCircle
      default:
        return Clock
    }
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'completed':
        return <Badge className="bg-green-100 text-green-800">Concluído</Badge>
      case 'generating':
        return <Badge className="bg-yellow-100 text-yellow-800">Gerando</Badge>
      case 'failed':
        return <Badge className="bg-red-100 text-red-800">Falhou</Badge>
      default:
        return <Badge variant="outline">{status}</Badge>
    }
  }

  const getReportTypeLabel = (type: string) => {
    switch (type) {
      case 'monthly':
        return 'Relatório Mensal'
      case 'quarterly':
        return 'Relatório Trimestral'
      case 'treatment_progress':
        return 'Progresso do Tratamento'
      case 'engagement':
        return 'Relatório de Engajamento'
      case 'custom':
        return 'Relatório Personalizado'
      default:
        return type
    }
  }

  const StatusIcon = getStatusIcon(report.status)

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="flex items-center space-x-3">
            <div className="flex items-center justify-center w-10 h-10 bg-blue-100 rounded-lg">
              <FileText className="h-5 w-5 text-blue-600" />
            </div>
            <div>
              <CardTitle className="text-lg">
                {report.name || getReportTypeLabel(report.report_type)}
              </CardTitle>
              <CardDescription>
                {report.patient_id ? `Paciente: ${report.patient_id}` : 'Relatório Geral'}
              </CardDescription>
            </div>
          </div>
          {getStatusBadge(report.status)}
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <div className="flex items-center space-x-2 text-sm text-gray-600">
            <StatusIcon className="h-4 w-4" />
            <span>
              {report.status === 'completed' && report.generated_at
                ? `Concluído ${formatDistanceToNow(new Date(report.generated_at), {
                    addSuffix: true,
                    locale: ptBR
                  })}`
                : `Criado ${formatDistanceToNow(new Date(report.created_at), {
                    addSuffix: true,
                    locale: ptBR
                  })}`}
            </span>
          </div>
          
          <div className="flex space-x-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => onView?.(report.id)}
              disabled={report.status !== 'completed'}
              className="flex-1"
            >
              <Eye className="mr-2 h-4 w-4" />
              Visualizar
            </Button>
            <Button
              size="sm"
              onClick={() => onDownload?.(report.id)}
              disabled={report.status !== 'completed' || downloading}
              className="flex-1"
            >
              {downloading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Baixando...
                </>
              ) : (
                <>
                  <Download className="mr-2 h-4 w-4" />
                  Download
                </>
              )}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
