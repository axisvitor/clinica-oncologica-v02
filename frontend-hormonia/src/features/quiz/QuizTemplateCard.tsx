import React from 'react'
import { FileText, Play, Eye, Edit, Trash2 } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

interface QuizTemplate {
  id: string
  name: string
  description?: string
  questions: unknown[]
  is_active: boolean
  created_at: string
}

interface QuizTemplateCardProps {
  template: QuizTemplate
  onStart?: (templateId: string) => void
  onPreview?: (templateId: string) => void
  onEdit?: (templateId: string) => void
  onDelete?: (templateId: string) => void
  showAdminActions?: boolean
}

export function QuizTemplateCard({
  template,
  onStart,
  onPreview,
  onEdit,
  onDelete,
  showAdminActions = false
}: QuizTemplateCardProps) {
  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="flex items-center space-x-2">
            <FileText className="h-5 w-5 text-blue-600" />
            <div>
              <CardTitle className="text-lg">{template.name}</CardTitle>
              {template.description && (
                <CardDescription className="mt-1">
                  {template.description}
                </CardDescription>
              )}
            </div>
          </div>
          <Badge variant={template.is_active ? "default" : "secondary"}>
            {template.is_active ? 'Ativo' : 'Inativo'}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <div className="flex items-center justify-between text-sm text-gray-600">
            <span>{template.questions?.length || 0} perguntas</span>
            {template.created_at && (
              <span>
                Criado em {new Date(template.created_at).toLocaleDateString('pt-BR')}
              </span>
            )}
          </div>

          <div className="flex space-x-2">
            {showAdminActions ? (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onEdit?.(template.id)}
                  className="flex-1"
                >
                  <Edit className="mr-2 h-4 w-4" />
                  Editar
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onPreview?.(template.id)}
                >
                  <Eye className="h-4 w-4" />
                </Button>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={() => onDelete?.(template.id)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </>
            ) : (
              <>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onPreview?.(template.id)}
                  className="flex-1"
                >
                  <Eye className="mr-2 h-4 w-4" />
                  Visualizar
                </Button>
                <Button
                  size="sm"
                  onClick={() => onStart?.(template.id)}
                  disabled={!template.is_active}
                  className="flex-1"
                >
                  <Play className="mr-2 h-4 w-4" />
                  Iniciar
                </Button>
              </>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
