import React from 'react'
import { FileText, Play, Eye } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

interface QuizTemplate {
  id: string
  name: string
  description?: string
  questions: any[]
  is_active: boolean
  created_at: string
}

interface QuizTemplateCardProps {
  template: QuizTemplate
  onStart?: (templateId: string) => void
  onPreview?: (templateId: string) => void
}

export function QuizTemplateCard({ template, onStart, onPreview }: QuizTemplateCardProps) {
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
            <span>
              Criado em {new Date(template.created_at).toLocaleDateString('pt-BR')}
            </span>
          </div>
          
          <div className="flex space-x-2">
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
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
