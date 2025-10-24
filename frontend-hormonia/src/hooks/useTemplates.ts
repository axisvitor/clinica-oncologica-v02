/**
 * useTemplates Hook
 *
 * React hook for managing flow and quiz templates via the CRUD API.
 * Provides functions to create, read, update, and delete templates.
 */

import { useState, useCallback } from 'react';
import { useToast } from '@/components/ui/use-toast';
import { apiClient } from '@/lib/api-client';

// ==================== Types ====================

export interface FlowTemplateStep {
  intent: string;
  ai_instructions?: string;
  personalization_hints?: string[];
  interactive_elements?: any;
  message_type?: string;
  base_content?: string;
}

export interface FlowTemplateMetadata {
  flow_type: string;
  humanization_level: string;
  version: string;
  full_template?: any;
}

export interface FlowTemplateCreate {
  flow_kind_id?: string;
  kind_key?: string;
  display_name: string;
  description?: string;
  version_number?: number;
  steps: Record<string, FlowTemplateStep>;
  metadata?: FlowTemplateMetadata;
  is_active?: boolean;
  is_draft?: boolean;
}

export interface FlowTemplateUpdate {
  template_name?: string;
  description?: string;
  steps?: Record<string, FlowTemplateStep>;
  metadata?: FlowTemplateMetadata;
  is_active?: boolean;
  is_draft?: boolean;
}

export interface FlowTemplate {
  id: string;
  flow_kind_id: string;
  kind_key: string;
  display_name: string;
  version_number: number;
  template_name: string;
  description?: string;
  steps: Record<string, any>;
  metadata?: any;
  is_active: boolean;
  is_draft: boolean;
  published_at?: string;
  created_at: string;
  updated_at: string;
}

export interface QuizQuestion {
  id: string;
  type: 'scale' | 'multiple_choice' | 'open_text' | 'yes_no';
  text: string;
  category?: string;
  required?: boolean;
  options?: Array<{
    text: string;
    value?: any;
    score?: number;
  }>;
  validation_rules?: any[];
  metadata?: any;
}

export interface QuizTemplateCreate {
  name: string;
  version?: string;
  description?: string;
  questions: QuizQuestion[];
  category?: string;
  tags?: string[];
  passing_score?: number;
  time_limit_minutes?: number;
  randomize_questions?: boolean;
  is_active?: boolean;
}

export interface QuizTemplateUpdate {
  name?: string;
  version?: string;
  description?: string;
  questions?: QuizQuestion[];
  category?: string;
  tags?: string[];
  passing_score?: number;
  time_limit_minutes?: number;
  randomize_questions?: boolean;
  is_active?: boolean;
}

export interface QuizTemplate {
  id: string;
  name: string;
  version: string;
  description?: string;
  questions: QuizQuestion[];
  category: string;
  tags: string[];
  passing_score: number;
  time_limit_minutes: number;
  randomize_questions: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// Import and re-export PaginatedResponse from shared types
import type { PaginatedResponse as SharedPaginatedResponse } from '@/types/shared'
export type PaginatedResponse<T> = SharedPaginatedResponse<T>

// Legacy interface for backward compatibility (deprecated)
interface _PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  total_pages: number;
}

// ==================== Hook ====================

export function useTemplates() {
  const [loading, setLoading] = useState(false);
  const { toast } = useToast();

  // ==================== Flow Templates ====================

  const createFlowTemplate = useCallback(async (data: FlowTemplateCreate): Promise<FlowTemplate | null> => {
    setLoading(true);
    try {
      const response = await apiClient.post<FlowTemplate>('/api/v1/templates/flows', data);

      toast({
        title: 'Template criado',
        description: `Template "${data.display_name}" criado com sucesso!`,
      });

      return response;
    } catch (error: any) {
      toast({
        title: 'Erro ao criar template',
        description: error.response?.data?.detail || 'Ocorreu um erro ao criar o template',
        variant: 'destructive',
      });
      return null;
    } finally {
      setLoading(false);
    }
  }, [toast]);

  const listFlowTemplates = useCallback(async (params?: {
    is_active?: boolean;
    is_draft?: boolean;
    kind_key?: string;
    page?: number;
    size?: number;
  }): Promise<PaginatedResponse<FlowTemplate> | null> => {
    setLoading(true);
    try {
      const response = await apiClient.get<PaginatedResponse<FlowTemplate>>('/api/v1/templates/flows', params || undefined);

      return response;
    } catch (error: any) {
      toast({
        title: 'Erro ao listar templates',
        description: error.response?.data?.detail || 'Ocorreu um erro ao listar templates',
        variant: 'destructive',
      });
      return null;
    } finally {
      setLoading(false);
    }
  }, [toast]);

  const getFlowTemplate = useCallback(async (templateId: string): Promise<FlowTemplate | null> => {
    setLoading(true);
    try {
      const response = await apiClient.get<FlowTemplate>(`/api/v1/templates/flows/${templateId}`);
      return response;
    } catch (error: any) {
      toast({
        title: 'Erro ao buscar template',
        description: error.response?.data?.detail || 'Template não encontrado',
        variant: 'destructive',
      });
      return null;
    } finally {
      setLoading(false);
    }
  }, [toast]);

  const updateFlowTemplate = useCallback(async (
    templateId: string,
    data: FlowTemplateUpdate
  ): Promise<FlowTemplate | null> => {
    setLoading(true);
    try {
      const response = await apiClient.put<FlowTemplate>(`/api/v1/templates/flows/${templateId}`, data);

      toast({
        title: 'Template atualizado',
        description: 'Template atualizado com sucesso!',
      });

      return response;
    } catch (error: any) {
      toast({
        title: 'Erro ao atualizar template',
        description: error.response?.data?.detail || 'Ocorreu um erro ao atualizar o template',
        variant: 'destructive',
      });
      return null;
    } finally {
      setLoading(false);
    }
  }, [toast]);

  const deleteFlowTemplate = useCallback(async (
    templateId: string,
    softDelete: boolean = true
  ): Promise<boolean> => {
    setLoading(true);
    try {
      await apiClient.delete(`/api/v1/templates/flows/${templateId}`, { soft_delete: softDelete });

      toast({
        title: 'Template removido',
        description: softDelete ? 'Template desativado com sucesso' : 'Template deletado permanentemente',
      });

      return true;
    } catch (error: any) {
      toast({
        title: 'Erro ao remover template',
        description: error.response?.data?.detail || 'Ocorreu um erro ao remover o template',
        variant: 'destructive',
      });
      return false;
    } finally {
      setLoading(false);
    }
  }, [toast]);

  // ==================== Quiz Templates ====================

  const createQuizTemplate = useCallback(async (data: QuizTemplateCreate): Promise<QuizTemplate | null> => {
    setLoading(true);
    try {
      const response = await apiClient.post<QuizTemplate>('/api/v1/templates/quiz', data);

      toast({
        title: 'Quiz criado',
        description: `Quiz "${data.name}" criado com sucesso!`,
      });

      return response;
    } catch (error: any) {
      toast({
        title: 'Erro ao criar quiz',
        description: error.response?.data?.detail || 'Ocorreu um erro ao criar o quiz',
        variant: 'destructive',
      });
      return null;
    } finally {
      setLoading(false);
    }
  }, [toast]);

  const listQuizTemplates = useCallback(async (params?: {
    is_active?: boolean;
    category?: string;
    page?: number;
    size?: number;
  }): Promise<PaginatedResponse<QuizTemplate> | null> => {
    setLoading(true);
    try {
      const response = await apiClient.get<PaginatedResponse<QuizTemplate>>('/api/v1/templates/quiz', params || undefined);

      return response;
    } catch (error: any) {
      toast({
        title: 'Erro ao listar quizzes',
        description: error.response?.data?.detail || 'Ocorreu um erro ao listar quizzes',
        variant: 'destructive',
      });
      return null;
    } finally {
      setLoading(false);
    }
  }, [toast]);

  const getQuizTemplate = useCallback(async (quizId: string): Promise<QuizTemplate | null> => {
    setLoading(true);
    try {
      const response = await apiClient.get<QuizTemplate>(`/api/v1/templates/quiz/${quizId}`);
      return response;
    } catch (error: any) {
      toast({
        title: 'Erro ao buscar quiz',
        description: error.response?.data?.detail || 'Quiz não encontrado',
        variant: 'destructive',
      });
      return null;
    } finally {
      setLoading(false);
    }
  }, [toast]);

  const updateQuizTemplate = useCallback(async (
    quizId: string,
    data: QuizTemplateUpdate
  ): Promise<QuizTemplate | null> => {
    setLoading(true);
    try {
      const response = await apiClient.put<QuizTemplate>(`/api/v1/templates/quiz/${quizId}`, data);

      toast({
        title: 'Quiz atualizado',
        description: 'Quiz atualizado com sucesso!',
      });

      return response;
    } catch (error: any) {
      toast({
        title: 'Erro ao atualizar quiz',
        description: error.response?.data?.detail || 'Ocorreu um erro ao atualizar o quiz',
        variant: 'destructive',
      });
      return null;
    } finally {
      setLoading(false);
    }
  }, [toast]);

  const deleteQuizTemplate = useCallback(async (
    quizId: string,
    softDelete: boolean = true
  ): Promise<boolean> => {
    setLoading(true);
    try {
      await apiClient.delete(`/api/v1/templates/quiz/${quizId}`, { soft_delete: softDelete });

      toast({
        title: 'Quiz removido',
        description: softDelete ? 'Quiz desativado com sucesso' : 'Quiz deletado permanentemente',
      });

      return true;
    } catch (error: any) {
      toast({
        title: 'Erro ao remover quiz',
        description: error.response?.data?.detail || 'Ocorreu um erro ao remover o quiz',
        variant: 'destructive',
      });
      return false;
    } finally {
      setLoading(false);
    }
  }, [toast]);

  return {
    loading,
    // Flow templates
    createFlowTemplate,
    listFlowTemplates,
    getFlowTemplate,
    updateFlowTemplate,
    deleteFlowTemplate,
    // Quiz templates
    createQuizTemplate,
    listQuizTemplates,
    getQuizTemplate,
    updateQuizTemplate,
    deleteQuizTemplate,
  };
}
