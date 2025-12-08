/**
 * useFlowTemplates Hook
 *
 * Custom hook for managing flow template state and operations.
 */

import { useState, useEffect, useCallback } from 'react';
import { useTemplates, type FlowTemplate } from '@/hooks/useTemplates';
import { useToast } from '@/components/ui/use-toast';
import { logger } from '@/lib/logger';
import type { TemplateFilter } from '../../TemplateManagementPage';

interface TemplateListParams {
  page: number;
  size: number;
  is_active?: boolean;
  is_draft?: boolean;
}

interface UseFlowTemplatesOptions {
  filter?: TemplateFilter;
}

export function useFlowTemplates(options: UseFlowTemplatesOptions = {}) {
  const { toast } = useToast();
  const { loading, listFlowTemplates } = useTemplates();

  const [templates, setTemplates] = useState<FlowTemplate[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  const loadTemplates = useCallback(async () => {
    try {
      setError(null);
      const params: TemplateListParams = { page, size: 10 };

      if (options.filter === 'active') params.is_active = true;
      if (options.filter === 'draft') params.is_draft = true;

      const response = await listFlowTemplates(params);
      if (response) {
        setTemplates(response.items);
        setTotalPages(response.pages);
      }
    } catch (err) {
      logger.error('Failed to load flow templates', err);
      setError('Erro ao carregar templates de flow');
      toast({
        title: 'Erro',
        description: 'Falha ao carregar templates de flow',
        variant: 'destructive',
      });
    }
  }, [page, options.filter, listFlowTemplates, toast]);

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
