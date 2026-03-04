/**
 * Quiz Template List Component
 *
 * Displays a grid of quiz template cards with pagination and error handling.
 */

import React, { memo, useState } from 'react'
import { FileText } from 'lucide-react'
import { QuizTemplateCard } from '@/features/quiz/QuizTemplateCard'
import { QuizEditorDialog } from './QuizEditorDialog'
import { TemplateListFrame } from '../utils/TemplateListFrame'
import type { QuizTemplate } from '@/hooks/useTemplates'
import { logger } from '@/lib/logger'

interface QuizTemplateListProps {
  templates: QuizTemplate[]
  loading: boolean
  error: string | null
  page: number
  totalPages: number
  onPageChange: (page: number) => void
  onRefresh: () => void
}

export const QuizTemplateList = memo<QuizTemplateListProps>(
  ({ templates, loading, error, page, totalPages, onPageChange, onRefresh }) => {
    const [editingQuiz, setEditingQuiz] = useState<QuizTemplate | null>(null)

    const handleEdit = (quizId: string) => {
      const quiz = templates.find((q) => q.id === quizId)
      if (quiz) {
        setEditingQuiz(quiz)
      }
    }

    const handleDelete = async (quizId: string) => {
      logger.debug('Delete quiz', quizId)
      onRefresh()
    }

    return (
      <TemplateListFrame
        error={error}
        loading={loading}
        isEmpty={templates.length === 0}
        emptyIcon={FileText}
        emptyMessage="Nenhum quiz encontrado"
        onRefresh={onRefresh}
        page={page}
        totalPages={totalPages}
        onPageChange={onPageChange}
        footer={
          <QuizEditorDialog
            quiz={editingQuiz}
            onClose={() => setEditingQuiz(null)}
            onSuccess={() => {
              setEditingQuiz(null)
              onRefresh()
            }}
          />
        }
      >
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {templates.map((quiz) => (
            <QuizTemplateCard
              key={quiz.id}
              template={quiz}
              onPreview={() => logger.debug('Preview quiz', quiz.id)}
              onEdit={handleEdit}
              onDelete={handleDelete}
              showAdminActions={true}
            />
          ))}
        </div>
      </TemplateListFrame>
    )
  }
)

QuizTemplateList.displayName = 'QuizTemplateList'
