/**
 * PatientAISummary Component
 *
 * AI-powered patient summary generation for doctor consultations.
 * Uses Gemini 2.5 Flash for fast, cost-effective summary generation.
 */

import React, { useState } from 'react';
import { format, subDays } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import {
  Brain,
  Calendar,
  Download,
  Clock,
  AlertTriangle,
  CheckCircle,
  TrendingUp,
  MessageSquare,
  ChevronDown,
  ChevronUp,
  FileText,
  Loader2,
} from 'lucide-react';
import { createLogger } from '@/utils/logger';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { usePatientSummaryManager } from '@/hooks/usePatientSummary';
import type { PatientSummaryResponse, SeverityLevel } from '@/types/api';

const logger = createLogger('PatientAISummary');

interface PatientAISummaryProps {
  patientId: string;
  patientName?: string;
}

// Define section keys type
type SectionKey = 'overview' | 'quiz' | 'concerns' | 'engagement' | 'compliance' | 'recommendations';

// Severity badge colors
const severityColors: Record<SeverityLevel, string> = {
  low: 'bg-green-100 text-green-800',
  medium: 'bg-yellow-100 text-yellow-800',
  high: 'bg-orange-100 text-orange-800',
  critical: 'bg-red-100 text-red-800',
};

export function PatientAISummary({ patientId, patientName }: PatientAISummaryProps) {
  const [startDate, setStartDate] = useState(format(subDays(new Date(), 30), 'yyyy-MM-dd'));
  const [endDate, setEndDate] = useState(format(new Date(), 'yyyy-MM-dd'));
  const [expandedSections, setExpandedSections] = useState<Record<SectionKey, boolean>>({
    overview: true,
    quiz: false,
    concerns: false,
    engagement: false,
    compliance: false,
    recommendations: true,
  });
  const [currentSummary, setCurrentSummary] = useState<PatientSummaryResponse | null>(null);

  const {
    summaries,
    isLoading,
    generateSummary,
    isGenerating,
    exportToPdf,
    isExporting,
  } = usePatientSummaryManager(patientId);

  const toggleSection = (section: SectionKey) => {
    setExpandedSections((prev) => ({ ...prev, [section]: !prev[section] }));
  };

  const handleGenerate = async () => {
    try {
      const summary = await generateSummary(startDate, endDate, false);
      setCurrentSummary(summary);
    } catch (error) {
      logger.error('Failed to generate summary', error instanceof Error ? error : undefined);
    }
  };

  const handleExport = async () => {
    if (currentSummary) {
      await exportToPdf(currentSummary.summary_id);
    }
  };

  const displaySummary = currentSummary || (summaries.length > 0 ? summaries[0] : null);

  return (
    <div className="space-y-6">
      {/* Header Card - Date Selection and Generate */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Brain className="h-5 w-5 text-purple-600" />
            Resumo Inteligente do Paciente
          </CardTitle>
          <CardDescription>
            Gere um resumo automatizado com IA para otimizar sua consulta
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col sm:flex-row gap-4 items-end">
            <div className="flex-1 grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium text-gray-700 mb-1 block">
                  Data Inicial
                </label>
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="w-full px-3 py-2 border rounded-md focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                />
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700 mb-1 block">
                  Data Final
                </label>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="w-full px-3 py-2 border rounded-md focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                />
              </div>
            </div>
            <div className="flex gap-2">
              <Button
                onClick={handleGenerate}
                disabled={isGenerating}
                className="bg-purple-600 hover:bg-purple-700"
              >
                {isGenerating ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Gerando...
                  </>
                ) : (
                  <>
                    <Brain className="mr-2 h-4 w-4" />
                    Gerar Resumo
                  </>
                )}
              </Button>
              {displaySummary && (
                <Button
                  variant="outline"
                  onClick={handleExport}
                  disabled={isExporting}
                >
                  {isExporting ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Download className="h-4 w-4" />
                  )}
                </Button>
              )}
            </div>
          </div>

          {/* Quick Date Presets */}
          <div className="flex gap-2 mt-4">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setStartDate(format(subDays(new Date(), 7), 'yyyy-MM-dd'));
                setEndDate(format(new Date(), 'yyyy-MM-dd'));
              }}
            >
              Última Semana
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setStartDate(format(subDays(new Date(), 30), 'yyyy-MM-dd'));
                setEndDate(format(new Date(), 'yyyy-MM-dd'));
              }}
            >
              Último Mês
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setStartDate(format(subDays(new Date(), 90), 'yyyy-MM-dd'));
                setEndDate(format(new Date(), 'yyyy-MM-dd'));
              }}
            >
              Últimos 3 Meses
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Summary Content */}
      {displaySummary ? (
        <div className="space-y-4">
          {/* Summary Meta */}
          <div className="flex items-center justify-between text-sm text-gray-500">
            <span className="flex items-center gap-2">
              <Calendar className="h-4 w-4" />
              Período: {format(new Date(displaySummary.start_date), 'dd/MM/yyyy', { locale: ptBR })} -{' '}
              {format(new Date(displaySummary.end_date), 'dd/MM/yyyy', { locale: ptBR })}
            </span>
            <span className="flex items-center gap-2">
              <Clock className="h-4 w-4" />
              Gerado em {format(new Date(displaySummary.generated_at), "dd/MM 'às' HH:mm", { locale: ptBR })}
              {displaySummary.from_cache && (
                <Badge variant="outline" className="ml-2">
                  Cache
                </Badge>
              )}
            </span>
          </div>

          {/* Overview Section */}
          <CollapsibleSection
            title="Visão Geral"
            icon={<FileText className="h-4 w-4" />}
            isOpen={expandedSections.overview}
            onToggle={() => toggleSection('overview')}
          >
            <p className="text-gray-700 whitespace-pre-wrap leading-relaxed">
              {displaySummary.content.overview}
            </p>
          </CollapsibleSection>

          {/* Quiz Findings */}
          <CollapsibleSection
            title="Achados dos Questionários"
            icon={<CheckCircle className="h-4 w-4" />}
            badge={`${displaySummary.content.quiz_findings.total_completed} completados`}
            isOpen={expandedSections.quiz}
            onToggle={() => toggleSection('quiz')}
          >
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-gray-50 p-3 rounded-lg">
                  <p className="text-sm text-gray-500">Questionários Completados</p>
                  <p className="text-2xl font-bold text-gray-900">
                    {displaySummary.content.quiz_findings.total_completed}
                  </p>
                </div>
                <div className="bg-gray-50 p-3 rounded-lg">
                  <p className="text-sm text-gray-500">Perguntas Respondidas</p>
                  <p className="text-2xl font-bold text-gray-900">
                    {displaySummary.content.quiz_findings.total_questions_answered}
                  </p>
                </div>
              </div>

              {displaySummary.content.quiz_findings.key_findings.length > 0 && (
                <div>
                  <h4 className="font-medium mb-2">Principais Achados</h4>
                  <ul className="list-disc list-inside space-y-1 text-gray-700">
                    {displaySummary.content.quiz_findings.key_findings.map((finding, i) => (
                      <li key={i}>{finding}</li>
                    ))}
                  </ul>
                </div>
              )}

              {displaySummary.content.quiz_findings.concerning_responses.length > 0 && (
                <div className="bg-yellow-50 border border-yellow-200 p-3 rounded-lg">
                  <h4 className="font-medium text-yellow-800 mb-2 flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4" />
                    Respostas Preocupantes
                  </h4>
                  <ul className="list-disc list-inside space-y-1 text-yellow-700">
                    {displaySummary.content.quiz_findings.concerning_responses.map((resp, i) => (
                      <li key={i}>{resp}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </CollapsibleSection>

          {/* Health Concerns */}
          <CollapsibleSection
            title="Preocupações de Saúde"
            icon={<AlertTriangle className="h-4 w-4" />}
            badge={
              displaySummary.content.health_concerns.length > 0
                ? `${displaySummary.content.health_concerns.length} itens`
                : undefined
            }
            isOpen={expandedSections.concerns}
            onToggle={() => toggleSection('concerns')}
          >
            {displaySummary.content.health_concerns.length > 0 ? (
              <div className="space-y-3">
                {displaySummary.content.health_concerns.map((concern, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg"
                  >
                    <Badge className={severityColors[concern.severity]}>
                      {concern.severity.toUpperCase()}
                    </Badge>
                    <div className="flex-1">
                      <p className="text-gray-900">{concern.concern}</p>
                      {concern.detected_date && (
                        <p className="text-sm text-gray-500 mt-1">
                          Detectado em {concern.detected_date}
                          {concern.source && ` • Fonte: ${concern.source}`}
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-gray-500 italic">
                Nenhuma preocupação de saúde identificada no período.
              </p>
            )}
          </CollapsibleSection>

          {/* Engagement Metrics */}
          <CollapsibleSection
            title="Métricas de Engajamento"
            icon={<MessageSquare className="h-4 w-4" />}
            isOpen={expandedSections.engagement}
            onToggle={() => toggleSection('engagement')}
          >
            <div className="space-y-4">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <MetricCard
                  label="Taxa de Resposta"
                  value={`${Math.round(displaySummary.content.engagement_metrics.response_rate * 100)}%`}
                  progress={displaySummary.content.engagement_metrics.response_rate * 100}
                />
                <MetricCard
                  label="Tempo Médio de Resposta"
                  value={formatResponseTime(displaySummary.content.engagement_metrics.avg_response_time_minutes)}
                />
                <MetricCard
                  label="Mensagens Enviadas"
                  value={displaySummary.content.engagement_metrics.total_messages_sent.toString()}
                />
                <MetricCard
                  label="Mensagens Recebidas"
                  value={displaySummary.content.engagement_metrics.total_messages_received.toString()}
                />
              </div>
              <div>
                <div className="flex justify-between mb-1">
                  <span className="text-sm font-medium">Score de Engajamento</span>
                  <span className="text-sm text-gray-600">
                    {Math.round(displaySummary.content.engagement_metrics.engagement_score)}/100
                  </span>
                </div>
                <Progress
                  value={displaySummary.content.engagement_metrics.engagement_score}
                  className="h-2"
                />
              </div>
            </div>
          </CollapsibleSection>

          {/* Treatment Compliance */}
          <CollapsibleSection
            title="Adesão ao Tratamento"
            icon={<TrendingUp className="h-4 w-4" />}
            isOpen={expandedSections.compliance}
            onToggle={() => toggleSection('compliance')}
          >
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-gray-50 p-4 rounded-lg">
                  <p className="text-sm text-gray-500 mb-1">Score de Adesão</p>
                  <div className="flex items-center gap-2">
                    <span className="text-3xl font-bold text-gray-900">
                      {Math.round(displaySummary.content.treatment_compliance.adherence_score * 100)}%
                    </span>
                    <Progress
                      value={displaySummary.content.treatment_compliance.adherence_score * 100}
                      className="h-2 flex-1"
                    />
                  </div>
                </div>
                <div className="bg-gray-50 p-4 rounded-lg">
                  <p className="text-sm text-gray-500 mb-1">Interações Perdidas</p>
                  <p className="text-3xl font-bold text-gray-900">
                    {displaySummary.content.treatment_compliance.missed_interactions}
                  </p>
                </div>
              </div>
              {displaySummary.content.treatment_compliance.notes && (
                <p className="text-gray-700">
                  {displaySummary.content.treatment_compliance.notes}
                </p>
              )}
            </div>
          </CollapsibleSection>

          {/* Recommendations */}
          <CollapsibleSection
            title="Recomendações"
            icon={<Brain className="h-4 w-4" />}
            badge={`${displaySummary.content.recommendations.length} itens`}
            isOpen={expandedSections.recommendations}
            onToggle={() => toggleSection('recommendations')}
            highlight
          >
            <ul className="space-y-2">
              {displaySummary.content.recommendations.map((rec, i) => (
                <li
                  key={i}
                  className="flex items-start gap-3 p-3 bg-purple-50 rounded-lg"
                >
                  <span className="flex-shrink-0 w-6 h-6 rounded-full bg-purple-600 text-white text-sm flex items-center justify-center">
                    {i + 1}
                  </span>
                  <span className="text-gray-800">{rec}</span>
                </li>
              ))}
            </ul>
          </CollapsibleSection>

          {/* Meta Info */}
          {displaySummary.token_usage && (
            <div className="text-xs text-gray-400 flex items-center gap-4 justify-end">
              <span>Modelo: {displaySummary.model_used}</span>
              <span>Tokens: {displaySummary.token_usage}</span>
              <span>Tempo: {displaySummary.generation_time_ms}ms</span>
            </div>
          )}
        </div>
      ) : isLoading ? (
        <Card>
          <CardContent className="py-12 text-center">
            <Loader2 className="h-8 w-8 animate-spin mx-auto text-purple-600 mb-4" />
            <p className="text-gray-600">Carregando resumos...</p>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="py-12 text-center">
            <Brain className="h-12 w-12 mx-auto text-gray-300 mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">
              Nenhum resumo disponível
            </h3>
            <p className="text-gray-500 mb-4">
              Selecione um período e clique em "Gerar Resumo" para criar um resumo inteligente do paciente.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Historical Summaries */}
      {summaries.length > 1 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Resumos Anteriores</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {summaries.slice(1).map((summary) => (
                <button
                  key={summary.summary_id}
                  onClick={() => setCurrentSummary(summary)}
                  className="w-full text-left p-3 bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors"
                >
                  <div className="flex justify-between items-center">
                    <span className="text-sm font-medium">
                      {format(new Date(summary.start_date), 'dd/MM/yyyy')} -{' '}
                      {format(new Date(summary.end_date), 'dd/MM/yyyy')}
                    </span>
                    <span className="text-xs text-gray-500">
                      {format(new Date(summary.generated_at), "dd/MM 'às' HH:mm")}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// Helper Components
interface CollapsibleSectionProps {
  title: string;
  icon: React.ReactNode;
  badge?: string;
  isOpen: boolean;
  onToggle: () => void;
  highlight?: boolean;
  children: React.ReactNode;
}

function CollapsibleSection({
  title,
  icon,
  badge,
  isOpen,
  onToggle,
  highlight,
  children,
}: CollapsibleSectionProps) {
  return (
    <Card className={highlight ? 'border-purple-200 bg-purple-50/50' : ''}>
      <CardHeader
        className="cursor-pointer hover:bg-gray-50 transition-colors"
        onClick={onToggle}
      >
        <div className="flex items-center justify-between">
          <CardTitle className="text-base flex items-center gap-2">
            {icon}
            {title}
            {badge && (
              <Badge variant="secondary" className="ml-2">
                {badge}
              </Badge>
            )}
          </CardTitle>
          {isOpen ? (
            <ChevronUp className="h-4 w-4 text-gray-500" />
          ) : (
            <ChevronDown className="h-4 w-4 text-gray-500" />
          )}
        </div>
      </CardHeader>
      {isOpen && (
        <CardContent className="pt-0">{children}</CardContent>
      )}
    </Card>
  );
}

interface MetricCardProps {
  label: string;
  value: string;
  progress?: number;
}

function MetricCard({ label, value, progress }: MetricCardProps) {
  return (
    <div className="bg-gray-50 p-3 rounded-lg">
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p className="text-lg font-bold text-gray-900">{value}</p>
      {progress !== undefined && (
        <Progress value={progress} className="h-1 mt-2" />
      )}
    </div>
  );
}

function formatResponseTime(minutes: number): string {
  if (minutes === 0) return 'N/A';
  if (minutes < 60) return `${Math.round(minutes)} min`;
  const hours = minutes / 60;
  if (hours < 24) return `${hours.toFixed(1)}h`;
  return `${Math.round(hours / 24)} dias`;
}

export default PatientAISummary;
