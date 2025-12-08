import React from 'react'
import { MoreHorizontal, Eye, Edit, Trash2, BarChart3, Calendar, Users, TrendingUp, Clock } from 'lucide-react'
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger
} from '@/components/ui/dropdown-menu'

/**
 * Quiz template interface
 */
import { QuizTemplate } from '@/types/api'

/**
 * Props for QuestionarioCard component
 */
interface QuestionarioCardProps {
  /** Quiz template data */
  template: QuizTemplate
  /** Handler for delete action */
  onDelete: (id: string) => void
  /** Handler for edit action */
  onEdit: (template: QuizTemplate) => void
}

/**
 * Get status badge color based on active state
 */
const getStatusColor = (isActive: boolean) => {
  return isActive ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
}

/**
 * Get type badge info based on template name
 */
const getTypeFromName = (name: string) => {
  const lowerName = name.toLowerCase()
  if (lowerName.includes('medical') || lowerName.includes('oncolog') || lowerName.includes('sintoma')) {
    return { label: 'Médico', color: 'bg-blue-100 text-blue-800' }
  }
  return { label: 'Bem-estar', color: 'bg-purple-100 text-purple-800' }
}

/**
 * Card component displaying a single questionnaire template
 * Shows template information, statistics, and action menu
 *
 * @component
 * @example
 * ```tsx
 * <QuestionarioCard
 *   template={template}
 *   onDelete={handleDelete}
 *   onEdit={handleEdit}
 * />
 * ```
 */
export const QuestionarioCard = React.memo<QuestionarioCardProps>(({
  template,
  onDelete,
  onEdit
}) => {
  const analytics = template.analytics || {}
  const typeInfo = getTypeFromName(template.name)

  return (
    <Card className="hover:shadow-md transition-shadow duration-200 flex flex-col h-full">
      <CardHeader className="pb-3 px-4 sm:px-6">
        <div className="flex items-start justify-between gap-2">
          <div className="space-y-2 flex-1 min-w-0">
            <CardTitle className="text-base sm:text-lg leading-tight break-words">
              {template.name}
            </CardTitle>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="secondary" className={getStatusColor(template.is_active)}>
                {template.is_active ? 'Ativo' : 'Inativo'}
              </Badge>
              <Badge variant="outline" className={typeInfo.color}>
                {typeInfo.label}
              </Badge>
            </div>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm" className="h-8 w-8 p-0">
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>Ações</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem>
                <Eye className="h-4 w-4 mr-2" />
                Visualizar
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onEdit(template)}>
                <Edit className="h-4 w-4 mr-2" />
                Editar
              </DropdownMenuItem>
              <DropdownMenuItem>
                <BarChart3 className="h-4 w-4 mr-2" />
                Relatórios
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                className="text-destructive"
                onClick={() => onDelete(template.id)}
              >
                <Trash2 className="h-4 w-4 mr-2" />
                Desativar
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </CardHeader>

      <CardContent className="space-y-3 sm:space-y-4 px-4 sm:px-6 flex-1">
        <div className="text-sm text-muted-foreground space-y-1">
          <p>{template.questions?.length || 0} pergunta(s)</p>
          <p>Versão {template.version}</p>
        </div>

        <Separator />

        {/* Statistics */}
        <div className="grid grid-cols-2 gap-3 sm:gap-4 text-sm">
          <div className="space-y-1">
            <div className="flex items-center gap-1">
              <Users className="h-4 w-4 text-muted-foreground flex-shrink-0" />
              <span className="font-medium">{analytics.total_responses || 0}</span>
            </div>
            <p className="text-xs text-muted-foreground">Respostas</p>
          </div>
          <div className="space-y-1">
            <div className="flex items-center gap-1">
              <TrendingUp className="h-4 w-4 text-muted-foreground flex-shrink-0" />
              <span className="font-medium">{(analytics.completion_rate || 0).toFixed(1)}%</span>
            </div>
            <p className="text-xs text-muted-foreground">Taxa de Conclusão</p>
          </div>
        </div>

        {analytics.average_completion_time && (
          <div className="text-sm">
            <div className="flex items-center gap-1">
              <Clock className="h-4 w-4 text-muted-foreground flex-shrink-0" />
              <span className="font-medium">{Math.round(analytics.average_completion_time)} min</span>
            </div>
            <p className="text-xs text-muted-foreground mt-1">Tempo Médio</p>
          </div>
        )}
      </CardContent>

      <CardFooter className="pt-0 px-4 sm:px-6 pb-4 sm:pb-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between w-full gap-2 sm:gap-0 text-xs text-muted-foreground">
          <div className="flex items-center gap-1">
            <Calendar className="h-3 w-3 flex-shrink-0" />
            <span>{new Date(template.created_at).toLocaleDateString('pt-BR')}</span>
          </div>
          <span className="sm:text-right">v{template.version}</span>
        </div>
      </CardFooter>
    </Card>
  )
})

QuestionarioCard.displayName = 'QuestionarioCard'
