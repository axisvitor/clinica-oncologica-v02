/**
 * Flow Template Card Component
 *
 * Displays individual flow template with actions (edit, version, delete).
 */

import React, { memo, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { FlowDesignerDialog } from './FlowDesignerDialog'
import { FlowTemplateVersionsDialog } from './FlowTemplateVersionsDialog'
import type { FlowTemplate } from '@/hooks/useTemplates'
import { useTemplates } from '@/hooks/useTemplates'
import { useToast } from '@/components/ui/use-toast'
import { logger } from '@/lib/logger'

interface FlowTemplateCardProps {
  template: FlowTemplate
}

export const FlowTemplateCard = memo<FlowTemplateCardProps>(({ template }) => {
  const { toast } = useToast()
  const { deleteFlowTemplate } = useTemplates()
  const [showEditor, setShowEditor] = useState(false)
  const [showVersions, setShowVersions] = useState(false)
  const [editMode, setEditMode] = useState<'edit' | 'version' | null>(null)

  const handleEdit = () => {
    setEditMode('edit')
    setShowEditor(true)
  }

  const handleNewVersion = () => {
    setEditMode('version')
    setShowEditor(true)
  }

  const handleDelete = async () => {
    try {
      const success = await deleteFlowTemplate(template.id, true)
      if (success) {
        toast({ title: 'Template desativado' })
      }
    } catch (error) {
      logger.error('Failed to delete template', error)
      toast({
        title: 'Erro',
        description: 'Falha ao desativar template',
        variant: 'destructive',
      })
    }
  }

  const stepsCount = Array.isArray(template.steps)
    ? template.steps.length
    : Object.keys(template.steps || {}).length

  return (
    <>
      <Card className="hover:shadow-md transition-shadow">
        <CardHeader>
          <div className="flex items-start justify-between">
            <div>
              <CardTitle className="text-lg">{template.template_name}</CardTitle>
              <CardDescription className="mt-1">{template.kind_key}</CardDescription>
            </div>
            <div className="flex gap-2">
              {template.is_draft && <Badge variant="secondary">Rascunho</Badge>}
              {template.is_active && <Badge>Ativo</Badge>}
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground line-clamp-2">
              {template.description || 'Sem descrição'}
            </p>
            <div className="text-sm text-muted-foreground">
              <div>Versão: {template.version_number}</div>
              <div>Steps: {stepsCount}</div>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={handleEdit}>
                Editar
              </Button>
              <Button variant="outline" size="sm" onClick={handleNewVersion}>
                Nova Versão
              </Button>
              <Button variant="outline" size="sm" onClick={() => setShowVersions(true)}>
                Versões
              </Button>
              <Button variant="outline" size="sm" onClick={handleDelete}>
                Desativar
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <FlowDesignerDialog
        open={showEditor}
        onOpenChange={setShowEditor}
        template={editMode === 'edit' ? template : undefined}
        createNewVersion={editMode === 'version' ? template : undefined}
        onSuccess={() => {
          setShowEditor(false)
          setEditMode(null)
        }}
      />

      <FlowTemplateVersionsDialog
        open={showVersions}
        onOpenChange={setShowVersions}
        template={template}
      />
    </>
  )
})

FlowTemplateCard.displayName = 'FlowTemplateCard'
