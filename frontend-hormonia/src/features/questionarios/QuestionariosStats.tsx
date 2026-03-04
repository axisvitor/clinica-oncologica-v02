import React from 'react'
import { FileText, Check, Users, TrendingUp } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'

/**
 * Props for QuestionariosStats component
 */
interface QuestionariosStatsProps {
  /** Total number of questionnaire templates */
  totalTemplates: number
  /** Number of active templates */
  activeTemplates: number
  /** Total responses across all questionnaires */
  totalResponses: number
  /** Average completion rate as a percentage */
  averageCompletionRate: number
}

/**
 * Statistics cards component displaying questionnaire metrics
 *
 * @component
 * @example
 * ```tsx
 * <QuestionariosStats
 *   totalTemplates={10}
 *   activeTemplates={8}
 *   totalResponses={150}
 *   averageCompletionRate={85.5}
 * />
 * ```
 */
export const QuestionariosStats = React.memo<QuestionariosStatsProps>(
  ({ totalTemplates, activeTemplates, totalResponses, averageCompletionRate }) => {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mb-6 sm:mb-8">
        <Card>
          <CardContent className="p-4 sm:p-6">
            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-2 sm:gap-0">
              <FileText className="h-6 w-6 sm:h-8 sm:w-8 text-blue-500" />
              <div className="sm:ml-4">
                <p className="text-xl sm:text-2xl font-bold">{totalTemplates}</p>
                <p className="text-xs text-muted-foreground">Total de Questionários</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 sm:p-6">
            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-2 sm:gap-0">
              <Check className="h-6 w-6 sm:h-8 sm:w-8 text-green-500" />
              <div className="sm:ml-4">
                <p className="text-xl sm:text-2xl font-bold">{activeTemplates}</p>
                <p className="text-xs text-muted-foreground">Ativos</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 sm:p-6">
            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-2 sm:gap-0">
              <Users className="h-6 w-6 sm:h-8 sm:w-8 text-purple-500" />
              <div className="sm:ml-4">
                <p className="text-xl sm:text-2xl font-bold">{totalResponses}</p>
                <p className="text-xs text-muted-foreground">Total de Respostas</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 sm:p-6">
            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-2 sm:gap-0">
              <TrendingUp className="h-6 w-6 sm:h-8 sm:w-8 text-orange-500" />
              <div className="sm:ml-4">
                <p className="text-xl sm:text-2xl font-bold">{averageCompletionRate.toFixed(1)}%</p>
                <p className="text-xs text-muted-foreground">Taxa de Conclusão</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }
)

QuestionariosStats.displayName = 'QuestionariosStats'
