/**
 * Alerts Panel Component for Healthcare Metrics Dashboard
 *
 * Displays active alerts with severity-based styling, acknowledgment actions,
 * and real-time updates for healthcare system monitoring.
 */
import React, { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  AlertTriangle, Clock, CheckCircle, Filter,
  AlertCircle, Info, Zap, Heart
} from 'lucide-react';

interface AlertType {
  id: string;
  title: string;
  description: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  category: 'system' | 'healthcare' | 'security' | 'performance' | 'data_integrity' | 'ai_service';
  created_at: string;
  current_value?: number;
  threshold_value?: number;
  source: string;
  metadata: Record<string, unknown>;
}

interface AlertsPanelProps {
  alerts: AlertType[];
  onAcknowledge: (alertId: string) => Promise<void>;
  userRole: 'doctor' | 'admin';
}

export const AlertsPanel: React.FC<AlertsPanelProps> = ({
  alerts,
  onAcknowledge,
  userRole
}) => {
  const [selectedSeverity, setSelectedSeverity] = useState<string>('all');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [acknowledging, setAcknowledging] = useState<Set<string>>(new Set());

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'critical':
        return <AlertTriangle className="w-4 h-4 text-red-600" />;
      case 'high':
        return <AlertCircle className="w-4 h-4 text-orange-600" />;
      case 'medium':
        return <Info className="w-4 h-4 text-yellow-600" />;
      case 'low':
        return <Info className="w-4 h-4 text-blue-600" />;
      default:
        return <Info className="w-4 h-4 text-gray-600" />;
    }
  };

  const getSeverityBadge = (severity: string) => {
    const variants = {
      critical: 'bg-red-100 text-red-800 hover:bg-red-200',
      high: 'bg-orange-100 text-orange-800 hover:bg-orange-200',
      medium: 'bg-yellow-100 text-yellow-800 hover:bg-yellow-200',
      low: 'bg-blue-100 text-blue-800 hover:bg-blue-200'
    };

    return (
      <Badge className={variants[severity as keyof typeof variants] || variants.low}>
        {severity.toUpperCase()}
      </Badge>
    );
  };

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'healthcare':
        return <Heart className="w-4 h-4" />;
      case 'ai_service':
        return <Zap className="w-4 h-4" />;
      case 'performance':
        return <Clock className="w-4 h-4" />;
      default:
        return <AlertTriangle className="w-4 h-4" />;
    }
  };

  const getCategoryLabel = (category: string) => {
    const labels = {
      system: 'Sistema',
      healthcare: 'Saúde',
      security: 'Segurança',
      performance: 'Performance',
      data_integrity: 'Dados',
      ai_service: 'IA'
    };
    return labels[category as keyof typeof labels] || category;
  };

  const formatTimeAgo = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);

    if (diffInSeconds < 60) {
      return 'há poucos segundos';
    } else if (diffInSeconds < 3600) {
      const minutes = Math.floor(diffInSeconds / 60);
      return `há ${minutes} minuto${minutes > 1 ? 's' : ''}`;
    } else if (diffInSeconds < 86400) {
      const hours = Math.floor(diffInSeconds / 3600);
      return `há ${hours} hora${hours > 1 ? 's' : ''}`;
    } else {
      const days = Math.floor(diffInSeconds / 86400);
      return `há ${days} dia${days > 1 ? 's' : ''}`;
    }
  };

  const handleAcknowledge = async (alertId: string) => {
    setAcknowledging(prev => new Set(prev).add(alertId));
    try {
      await onAcknowledge(alertId);
    } finally {
      setAcknowledging(prev => {
        const next = new Set(prev);
        next.delete(alertId);
        return next;
      });
    }
  };

  const filteredAlerts = alerts.filter(alert => {
    if (selectedSeverity !== 'all' && alert.severity !== selectedSeverity) {
      return false;
    }
    if (selectedCategory !== 'all' && alert.category !== selectedCategory) {
      return false;
    }
    // Role-based filtering
    if (userRole === 'doctor' && alert.category === 'system') {
      return false;
    }
    return true;
  });

  const criticalAlerts = filteredAlerts.filter(alert => alert.severity === 'critical');
  const highAlerts = filteredAlerts.filter(alert => alert.severity === 'high');

  return (
    <div className="space-y-6">
      {/* Alert Summary */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-2xl font-bold text-red-600">
                  {criticalAlerts.length}
                </div>
                <div className="text-sm text-muted-foreground">Críticos</div>
              </div>
              <AlertTriangle className="w-8 h-8 text-red-600" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-2xl font-bold text-orange-600">
                  {highAlerts.length}
                </div>
                <div className="text-sm text-muted-foreground">Alta Prioridade</div>
              </div>
              <AlertCircle className="w-8 h-8 text-orange-600" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-2xl font-bold text-blue-600">
                  {filteredAlerts.length}
                </div>
                <div className="text-sm text-muted-foreground">Total Ativo</div>
              </div>
              <AlertTriangle className="w-8 h-8 text-blue-600" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-2xl font-bold text-green-600">
                  {alerts.length - filteredAlerts.length}
                </div>
                <div className="text-sm text-muted-foreground">Filtrados</div>
              </div>
              <Filter className="w-8 h-8 text-green-600" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <Filter className="w-5 h-5" />
            <span>Filtros</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-4">
            <div className="flex items-center space-x-2">
              <label className="text-sm font-medium">Severidade:</label>
              <select
                value={selectedSeverity}
                onChange={(e) => setSelectedSeverity(e.target.value)}
                className="px-3 py-1 border rounded-md text-sm"
              >
                <option value="all">Todas</option>
                <option value="critical">Crítica</option>
                <option value="high">Alta</option>
                <option value="medium">Média</option>
                <option value="low">Baixa</option>
              </select>
            </div>

            <div className="flex items-center space-x-2">
              <label className="text-sm font-medium">Categoria:</label>
              <select
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
                className="px-3 py-1 border rounded-md text-sm"
              >
                <option value="all">Todas</option>
                <option value="healthcare">Saúde</option>
                <option value="ai_service">IA</option>
                <option value="performance">Performance</option>
                <option value="system">Sistema</option>
                <option value="security">Segurança</option>
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Active Alerts */}
      <Card>
        <CardHeader>
          <CardTitle>Alertas Ativos</CardTitle>
          <CardDescription>
            {filteredAlerts.length} alertas requerem atenção
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {filteredAlerts.length === 0 ? (
            <div className="flex items-center justify-center py-8 text-muted-foreground">
              <CheckCircle className="w-8 h-8 mr-2" />
              <span>Nenhum alerta ativo</span>
            </div>
          ) : (
            filteredAlerts
              .sort((a, b) => {
                // Sort by severity first (critical > high > medium > low)
                const severityOrder = { critical: 4, high: 3, medium: 2, low: 1 };
                const severityDiff = (severityOrder[b.severity as keyof typeof severityOrder] || 0) -
                                  (severityOrder[a.severity as keyof typeof severityOrder] || 0);
                if (severityDiff !== 0) return severityDiff;

                // Then by creation time (newest first)
                return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
              })
              .map((alert) => (
                <Alert key={alert.id} className="relative">
                  <div className="flex items-start space-x-3">
                    <div className="flex-shrink-0 mt-1">
                      {getSeverityIcon(alert.severity)}
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center space-x-2 mb-2">
                            <h4 className="font-semibold text-sm">{alert.title}</h4>
                            {getSeverityBadge(alert.severity)}
                            <Badge variant="outline" className="text-xs">
                              <div className="flex items-center space-x-1">
                                {getCategoryIcon(alert.category)}
                                <span>{getCategoryLabel(alert.category)}</span>
                              </div>
                            </Badge>
                          </div>

                          <AlertDescription className="text-sm mb-3">
                            {alert.description}
                          </AlertDescription>

                          <div className="flex items-center space-x-4 text-xs text-muted-foreground">
                            <span className="flex items-center space-x-1">
                              <Clock className="w-3 h-3" />
                              <span>{formatTimeAgo(alert.created_at)}</span>
                            </span>

                            <span>Fonte: {alert.source}</span>

                            {alert.current_value !== undefined && alert.threshold_value !== undefined && (
                              <span className="bg-gray-100 px-2 py-1 rounded">
                                {alert.current_value.toFixed(2)} / {alert.threshold_value.toFixed(2)}
                              </span>
                            )}
                          </div>

                          {/* Alert Metadata */}
                          {Object.keys(alert.metadata).length > 0 && (
                            <div className="mt-2 pt-2 border-t">
                              <div className="text-xs text-muted-foreground">
                                {Object.entries(alert.metadata).map(([key, value]) => (
                                  <div key={key} className="inline-block mr-3">
                                    <span className="font-medium">{key}:</span> {String(value)}
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>

                        <div className="flex-shrink-0 ml-4">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleAcknowledge(alert.id)}
                            disabled={acknowledging.has(alert.id)}
                            className="text-xs"
                          >
                            {acknowledging.has(alert.id) ? (
                              <div className="flex items-center space-x-1">
                                <div className="w-3 h-3 border-2 border-gray-300 border-t-blue-600 rounded-full animate-spin" />
                                <span>Processando...</span>
                              </div>
                            ) : (
                              <div className="flex items-center space-x-1">
                                <CheckCircle className="w-3 h-3" />
                                <span>Confirmar</span>
                              </div>
                            )}
                          </Button>
                        </div>
                      </div>
                    </div>
                  </div>
                </Alert>
              ))
          )}
        </CardContent>
      </Card>
    </div>
  );
};
