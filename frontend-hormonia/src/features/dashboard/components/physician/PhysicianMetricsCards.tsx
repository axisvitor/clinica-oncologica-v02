import React from 'react'
import { Activity, TriangleAlert as AlertTriangle, TrendingUp, Users } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

interface PhysicianMetricsCardsProps {
  riskCounts: {
    critical: number
    high: number
    medium: number
    low: number
  }
}

export function PhysicianMetricsCards({ riskCounts }: PhysicianMetricsCardsProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
      <Card className="border-l-4 border-l-red-500 dark:bg-red-950/20">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium flex items-center justify-between">
            <span>Crítico</span>
            <AlertTriangle className="h-4 w-4 text-red-500" />
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-3xl font-bold">{riskCounts['critical']}</p>
          <p className="text-xs text-muted-foreground mt-1">Requer atenção imediata</p>
        </CardContent>
      </Card>

      <Card className="border-l-4 border-l-orange-500 dark:bg-orange-950/20">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium flex items-center justify-between">
            <span>Alto</span>
            <TrendingUp className="h-4 w-4 text-orange-500" />
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-3xl font-bold">{riskCounts['high']}</p>
          <p className="text-xs text-muted-foreground mt-1">Monitoramento próximo</p>
        </CardContent>
      </Card>

      <Card className="border-l-4 border-l-yellow-500 dark:bg-yellow-950/20">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium flex items-center justify-between">
            <span>Médio</span>
            <Activity className="h-4 w-4 text-yellow-500" />
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-3xl font-bold">{riskCounts['medium']}</p>
          <p className="text-xs text-muted-foreground mt-1">Acompanhamento regular</p>
        </CardContent>
      </Card>

      <Card className="border-l-4 border-l-green-500 dark:bg-green-950/20">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium flex items-center justify-between">
            <span>Baixo</span>
            <Users className="h-4 w-4 text-green-500" />
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-3xl font-bold">{riskCounts['low']}</p>
          <p className="text-xs text-muted-foreground mt-1">Estável</p>
        </CardContent>
      </Card>
    </div>
  )
}
