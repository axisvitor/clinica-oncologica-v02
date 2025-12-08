/**
 * useQuizTemplates Hook
 *
 * Custom hook for managing quiz template state and operations.
 */

import { useState, useEffect, useCallback } from 'react';
import { useTemplates, type QuizTemplate } from '@/hooks/useTemplates';
import { useToast } from '@/components/ui/use-toast';
import { logger } from '@/lib/logger';
import type { TemplateFilter } from '../../TemplateManagementPage';

interface TemplateListParams {
  page: number;
  size: number;
  is_active?: boolean;
}

interface UseQuizTemplatesOptions {
  filter?: TemplateFilter;
}

export function useQuizTemplates(options: UseQuizTemplatesOptions = {}) {
  const { toast } = useToast();
  const { loading, listQuizTemplates } = useTemplates();

  const [templates, setTemplates] = useState<QuizTemplate[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  const loadTemplates = useCallback(async () => {
    try {
      setError(null);
      const params: TemplateListParams = { page, size: 10 };

      if (options.filter === 'active') params.is_active = true;

      const response = await listQuizTemplates(params);
      if (response) {
        setTemplates(response.items);
        setTotalPages(response.pages);
      }
    } catch (err) {
      logger.error('Failed to load quiz templates', err);
      setError('Erro ao carregar templates de quiz');
      toast({
        title: 'Erro',
        description: 'Falha ao carregar templates de quiz',
        variant: 'destructive',
      });
    }
  }, [page, options.filter, listQuizTemplates, toast]);

  useEffect(() => {
    loadTemplates();
  }, [loadTemplates]);

  return {
    templates,
    loading,
    error,
    page,
    totalPages,
    setPage,
    refetch: loadTemplates,
  };
}
