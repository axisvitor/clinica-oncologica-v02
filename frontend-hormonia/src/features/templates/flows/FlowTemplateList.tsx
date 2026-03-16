/**
 * Flow Template List Component
 *
 * Displays a grid of flow template cards with pagination and error handling.
 */

import React, { memo } from 'react'
import { Workflow } from 'lucide-react'
import { FlowTemplateCard } from './FlowTemplateCard'
import { TemplateListFrame } from '../utils/TemplateListFrame'
import type { FlowTemplate } from '@/hooks/useTemplates'

interface FlowTemplateListProps {
  templates: FlowTemplate[]
  loading: boolean
  error: string | null
  page: number
  totalPages: number
  onPageChange: (page: number) => void
  onRefresh: () => void
  onCreateNew?: () => void
}

export const FlowTemplateList = memo<FlowTemplateListProps>(
  ({ templates, loading, error, page, totalPages, onPageChange, onRefresh, onCreateNew }) => {
    return (
      <TemplateListFrame
        error={error}
        loading={loading}
        isEmpty={templates.length === 0}
        emptyIcon={Workflow}
        emptyMessage="Nenhum template encontrado"
        emptyActionLabel="Criar Primeiro Template"
        onEmptyAction={onCreateNew}
        onRefresh={onRefresh}
        page={page}
        totalPages={totalPages}
        onPageChange={onPageChange}
      >
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {templates.map((template) => (
            <FlowTemplateCard key={template.id} template={template} />
          ))}
        </div>
      </TemplateListFrame>
    )
  }
)

FlowTemplateList.displayName = 'FlowTemplateList'
