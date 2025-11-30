/**
 * Flow Template List Component
 *
 * Displays a grid of flow template cards with pagination and error handling.
 */

import React, { memo } from 'react';
import { AlertTriangle, RefreshCw, Workflow } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { FlowTemplateCard } from './FlowTemplateCard';
import { TemplateCardSkeleton } from '../utils/TemplateCardSkeleton';
import type { FlowTemplate } from '@/hooks/useTemplates';

interface FlowTemplateListProps {
  templates: FlowTemplate[];
  loading: boolean;
  error: string | null;
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  onRefresh: () => void;
  onCreateNew: () => void;
}

export const FlowTemplateList = memo<FlowTemplateListProps>(({
  templates,
  loading,
  error,
  page,
  totalPages,
  onPageChange,
  onRefresh,
  onCreateNew,
}) => {
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
          <Workflow className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
          <p className="text-muted-foreground">Nenhum template encontrado</p>
          <Button onClick={onCreateNew} className="mt-4">
            Criar Primeiro Template
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      {/* Template Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {templates.map((template) => (
          <FlowTemplateCard key={template.id} template={template} />
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
    </>
  );
});

FlowTemplateList.displayName = 'FlowTemplateList';
