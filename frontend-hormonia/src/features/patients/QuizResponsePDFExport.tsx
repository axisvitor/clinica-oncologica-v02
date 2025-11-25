import React, { useRef } from 'react'
import { Button } from '@/components/ui/button'
import { FileDown } from 'lucide-react'
import { toast } from '@/components/ui/use-toast'
import type { QuizResponseWithContext, QuizAnalysisResponse } from '@/types/quiz'

interface QuizResponsePDFExportProps {
  responses: QuizResponseWithContext[]
  analysis?: QuizAnalysisResponse
  patientName: string
  className?: string
}

export function QuizResponsePDFExport({ 
  responses, 
  analysis, 
  patientName,
  className 
}: QuizResponsePDFExportProps) {
  const printRef = useRef<HTMLDivElement>(null)

  const handleExport = () => {
    // Create a new window for printing
    const printWindow = window.open('', '_blank')
    if (!printWindow) {
      toast({
        title: 'Permita pop-ups para exportar',
        description: 'Ative pop-ups temporariamente para baixar o PDF.',
      })
      return
    }

    // Format date
    const formatDate = (dateString: string) => {
      const date = new Date(dateString)
      return date.toLocaleDateString('pt-BR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      })
    }

    // Build HTML content
    const htmlContent = `
      <!DOCTYPE html>
      <html>
        <head>
          <meta charset="UTF-8">
          <title>Respostas de Quiz - ${patientName}</title>
          <style>
            body {
              font-family: Arial, sans-serif;
              margin: 20px;
              color: #333;
            }
            h1 {
              color: #1e40af;
              border-bottom: 2px solid #1e40af;
              padding-bottom: 10px;
            }
            h2 {
              color: #3b82f6;
              margin-top: 30px;
            }
            .header {
              margin-bottom: 30px;
            }
            .info-row {
              display: flex;
              justify-content: space-between;
              margin: 5px 0;
            }
            .analysis-section {
              background: #f3f4f6;
              padding: 15px;
              border-radius: 8px;
              margin: 20px 0;
            }
            .risk-badge {
              display: inline-block;
              padding: 4px 12px;
              border-radius: 4px;
              font-weight: bold;
              font-size: 12px;
            }
            .risk-critical { background: #fee2e2; color: #991b1b; }
            .risk-high { background: #fed7aa; color: #9a3412; }
            .risk-medium { background: #fef3c7; color: #92400e; }
            .risk-low { background: #d1fae5; color: #065f46; }
            table {
              width: 100%;
              border-collapse: collapse;
              margin-top: 20px;
            }
            th, td {
              border: 1px solid #d1d5db;
              padding: 12px;
              text-align: left;
            }
            th {
              background: #f3f4f6;
              font-weight: bold;
            }
            tr:nth-child(even) {
              background: #f9fafb;
            }
            .concern-list, .recommendation-list {
              margin: 10px 0;
              padding-left: 20px;
            }
            .concern-list li {
              color: #ea580c;
              margin: 5px 0;
            }
            .recommendation-list li {
              color: #2563eb;
              margin: 5px 0;
            }
            @media print {
              body { margin: 0; }
              .no-print { display: none; }
            }
          </style>
        </head>
        <body>
          <div class="header">
            <h1>Respostas de Quiz - ${patientName}</h1>
            <div class="info-row">
              <span><strong>Data de Exportação:</strong> ${new Date().toLocaleDateString('pt-BR')}</span>
              <span><strong>Total de Respostas:</strong> ${responses.length}</span>
            </div>
          </div>

          ${analysis ? `
            <div class="analysis-section">
              <h2>Análise de IA</h2>
              <div class="info-row">
                <span><strong>Template:</strong> ${analysis.template_name} (v${analysis.template_version})</span>
                ${analysis.risk_level ? `
                  <span class="risk-badge risk-${analysis.risk_level}">
                    RISCO: ${analysis.risk_level.toUpperCase()}
                  </span>
                ` : ''}
              </div>
              
              ${analysis.risk_score !== undefined && analysis.risk_score !== null ? `
                <div class="info-row">
                  <span><strong>Pontuação de Risco:</strong> ${analysis.risk_score.toFixed(1)}/100</span>
                  ${analysis.sentiment_score !== undefined && analysis.sentiment_score !== null ? `
                    <span><strong>Sentimento:</strong> ${analysis.sentiment_score.toFixed(2)}</span>
                  ` : ''}
                </div>
              ` : ''}

              ${analysis.key_concerns && analysis.key_concerns.length > 0 ? `
                <div>
                  <h3>Preocupações Identificadas:</h3>
                  <ul class="concern-list">
                    ${analysis.key_concerns.map(concern => `<li>${concern}</li>`).join('')}
                  </ul>
                </div>
              ` : ''}

              ${analysis.recommendations && analysis.recommendations.length > 0 ? `
                <div>
                  <h3>Recomendações:</h3>
                  <ul class="recommendation-list">
                    ${analysis.recommendations.map(rec => `<li>${rec}</li>`).join('')}
                  </ul>
                </div>
              ` : ''}
            </div>
          ` : ''}

          <h2>Respostas Detalhadas</h2>
          <table>
            <thead>
              <tr>
                <th>Pergunta</th>
                <th>Resposta</th>
                <th>Tipo</th>
                <th>Template</th>
                <th>Data</th>
              </tr>
            </thead>
            <tbody>
              ${responses.map(response => `
                <tr>
                  <td>${response.question_text}</td>
                  <td>
                    ${response.response_value}
                    ${response.other_text ? `<br><small><em>Outro: ${response.other_text}</em></small>` : ''}
                  </td>
                  <td>${response.response_type}</td>
                  <td>${response.template_name || 'N/A'}</td>
                  <td>${formatDate(response.responded_at)}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>

          <script>
            window.onload = function() {
              window.print();
            }
          </script>
        </body>
      </html>
    `

    printWindow.document.write(htmlContent)
    printWindow.document.close()
  }

  return (
    <>
      <Button 
        onClick={handleExport} 
        variant="outline"
        className={className}
      >
        <FileDown className="mr-2 h-4 w-4" />
        Exportar PDF
      </Button>
      
      {/* Hidden div for reference (not used in this implementation) */}
      <div ref={printRef} style={{ display: 'none' }} />
    </>
  )
}

