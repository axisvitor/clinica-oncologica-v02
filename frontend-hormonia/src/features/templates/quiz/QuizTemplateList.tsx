/**
 * Quiz Template List Component
 *
 * Displays a grid of quiz template cards with pagination and error handling.
 */

import React, { memo } from 'react';
import { AlertTriangle, RefreshCw, FileText } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { QuizTemplateCard } from '@/features/quiz/QuizTemplateCard';
import { TemplateCardSkeleton } from '../utils/TemplateCardSkeleton';
import { QuizEditorDialog } from './QuizEditorDialog';
import type { QuizTemplate } from '@/hooks/useTemplates';
import { logger } from '@/lib/logger';
import { useState } from 'react';

interface QuizTemplateListProps {
  templates: QuizTemplate[];
  loading: boolean;
  error: string | null;
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  onRefresh: () => void;
}

export const QuizTemplateList = memo<QuizTemplateListProps>(({
  templates,
  loading,
  error,
  page,
  totalPages,
  onPageChange,
  onRefresh,
}) => {
  const [editingQuiz, setEditingQuiz] = useState<QuizTemplate | null>(null);

  const handleEdit = (quizId: string) => {
    const quiz = templates.find((q) => q.id === quizId);
    if (quiz) {
      setEditingQuiz(quiz);
    }
  };

  const handleDelete = async (quizId: string) => {
    // Delegate to parent via refresh
    logger.debug('Delete quiz', quizId);
    onRefresh();
  };

  // Error state
  if (error) {
    return (
      <Card>
        <CardContent className="text-center py-12">
          <AlertTriangle className="h-12 w-12 mx-auto text-red-500 mb-4" />
          <p className="text-red-600 mb-4">{error}</p>
          <Button onClick={onRefresh} variant="outline">
            <RefreshCw className="h-4 w-4 mr-2" />
            Tentar Novamente
          </Button>
        </CardContent>
      </Card>
    );
  }

  // Loading state
  if (loading) {
    return (
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }, (_, i) => (
          <TemplateCardSkeleton key={i} />
        ))}
      </div>
    );
  }

  // Empty state
  if (templates.length === 0) {
    return (
      <Card>
        <CardContent className="text-center py-12">
          <FileText className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
          <p className="text-muted-foreground">Nenhum quiz encontrado</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      {/* Template Grid */}
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

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center gap-2 mt-6">
          <Button
            variant="outline"
            onClick={() => onPageChange(Math.max(1, page - 1))}
            disabled={page === 1}
          >
            Anterior
          </Button>
          <span className="flex items-center px-4">
            Página {page} de {totalPages}
          </span>
          <Button
            variant="outline"
            onClick={() => onPageChange(Math.min(totalPages, page + 1))}
            disabled={page === totalPages}
          >
            Próxima
          </Button>
        </div>
      )}

      {/* Editor Dialog */}
      <QuizEditorDialog
        quiz={editingQuiz}
        onClose={() => setEditingQuiz(null)}
        onSuccess={() => {
          setEditingQuiz(null);
          onRefresh();
        }}
      />
    </>
  );
});

QuizTemplateList.displayName = 'QuizTemplateList';
