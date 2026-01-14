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

export interface InteractiveElement {
  type: 'button' | 'input' | 'select' | 'checkbox' | 'radio';
  id: string;
  label?: string;
  value?: string;
  options?: Array<{ label: string; value: string }>;
  required?: boolean;
  validation?: {
    pattern?: string;
    min?: number;
    max?: number;
    message?: string;
  };
}

export interface FlowTemplateStep {
  step_number?: number;
  intent: string;
  ai_instructions?: string;
  personalization_hints?: string[];
  interactive_elements?: InteractiveElement[];
  message_type?: string;
  base_content?: string;
}

export interface FullTemplate {
  version: string;
  author?: string;
  created_at?: string;
  updated_at?: string;
  steps: FlowTemplateStep[];
  metadata?: Record<string, unknown>;
}

export interface FlowTemplateMetadata {
  flow_type: string;
  humanization_level: string;
  version: string;
  full_template?: FullTemplate;
}

export interface FlowTemplateCreate {
  flow_kind_id?: string;
  kind_key?: string;
  display_name: string;
  template_name?: string;
  description?: string;
  version_number?: number;
  steps: FlowTemplateStep[] | Record<string, FlowTemplateStep>; // Array (preferred) or dict (legacy)
  metadata?: FlowTemplateMetadata;
  is_active?: boolean;
  is_draft?: boolean;
}

export interface FlowTemplateUpdate {
  template_name?: string;
  description?: string;
  steps?: FlowTemplateStep[] | Record<string, FlowTemplateStep>; // Array (preferred) or dict (legacy)
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
  steps: FlowTemplateStep[] | Record<string, FlowTemplateStep>; // Array (preferred) or dict (legacy)
  metadata?: FlowTemplateMetadata | Record<string, unknown>;
  is_active: boolean;
  is_draft: boolean;
  published_at?: string;
  created_at: string;
  updated_at: string;
}

export interface FlowTemplateVersionList {
  data: FlowTemplate[];
  kind_key?: string;
  total: number;
}

export interface TemplateVersionCompareResult {
  version1: FlowTemplate;
  version2: FlowTemplate;
  diff: string;
  changes: string[];
  total_changes: number;
}

export interface QuizQuestionOption {
  text?: string;
  value?: string | number | boolean;
  score?: number;
}

export interface QuizValidationRule {
  type: 'required' | 'min' | 'max' | 'pattern' | 'custom';
  value?: unknown;
  message?: string;
}

export interface QuizQuestionMetadata {
  category?: string;
  tags?: string[];
  weight?: number;
  display_order?: number;
  conditional_logic?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface QuizQuestion {
  id: string;
  type: 'scale' | 'multiple_choice' | 'open_text' | 'yes_no';
  text: string;
  category?: string;
  required?: boolean;
  options?: QuizQuestionOption[];
  validation_rules?: QuizValidationRule[];
  metadata?: QuizQuestionMetadata;
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

// ==================== Hook ====================

export function useTemplates() {
  const [loading, setLoading] = useState(false);
  const { toast } = useToast();

  // ==================== Flow Templates ====================

  const createFlowTemplate = useCallback(async (data: FlowTemplateCreate): Promise<FlowTemplate | null> => {
    setLoading(true);
    try {
      const payload = {
        ...data,
        template_name: data.template_name || data.display_name,
      };
      const response = await apiClient.post<FlowTemplate>('/api/v2/templates/flows', payload);

      toast({
        title: 'Template criado',
        description: `Template "${data.display_name}" criado com sucesso!`,
      });

      return response;
    } catch (error: unknown) {
      const errorMessage = error && typeof error === 'object' && 'response' in error
        ? ((error.response as { data?: { detail?: string } })?.data?.detail) || 'Ocorreu um erro ao criar o template'
        : 'Ocorreu um erro ao criar o template';
      toast({
        title: 'Erro ao criar template',
        description: errorMessage,
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
      const response = await apiClient.get<PaginatedResponse<FlowTemplate>>('/api/v2/templates/flows', params || undefined);

      return response;
    } catch (error: unknown) {
      const errorMessage = error && typeof error === 'object' && 'response' in error
        ? ((error.response as { data?: { detail?: string } })?.data?.detail) || 'Ocorreu um erro ao listar templates'
        : 'Ocorreu um erro ao listar templates';
      toast({
        title: 'Erro ao listar templates',
        description: errorMessage,
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
      const response = await apiClient.get<FlowTemplate>(`/api/v2/templates/flows/${templateId}`);
      return response;
    } catch (error: unknown) {
      const errorMessage = error && typeof error === 'object' && 'response' in error
        ? ((error.response as { data?: { detail?: string } })?.data?.detail) || 'Template não encontrado'
        : 'Template não encontrado';
      toast({
        title: 'Erro ao buscar template',
        description: errorMessage,
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
      const response = await apiClient.put<FlowTemplate>(`/api/v2/templates/flows/${templateId}`, data);

      toast({
        title: 'Template atualizado',
        description: 'Template atualizado com sucesso!',
      });

      return response;
    } catch (error: unknown) {
      const errorMessage = error && typeof error === 'object' && 'response' in error
        ? ((error.response as { data?: { detail?: string } })?.data?.detail) || 'Ocorreu um erro ao atualizar o template'
        : 'Ocorreu um erro ao atualizar o template';
      toast({
        title: 'Erro ao atualizar template',
        description: errorMessage,
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
      await apiClient.delete(`/api/v2/templates/flows/${templateId}`, { soft_delete: softDelete });

      toast({
        title: 'Template removido',
        description: softDelete ? 'Template desativado com sucesso' : 'Template deletado permanentemente',
      });

      return true;
    } catch (error: unknown) {
      const errorMessage = error && typeof error === 'object' && 'response' in error
        ? ((error.response as { data?: { detail?: string } })?.data?.detail) || 'Ocorreu um erro ao remover o template'
        : 'Ocorreu um erro ao remover o template';
      toast({
        title: 'Erro ao remover template',
        description: errorMessage,
        variant: 'destructive',
      });
      return false;
    } finally {
      setLoading(false);
    }
  }, [toast]);

  const listFlowTemplateVersions = useCallback(async (
    templateId: string
  ): Promise<FlowTemplateVersionList | null> => {
    setLoading(true);
    try {
      const response = await apiClient.get<FlowTemplateVersionList>(
        `/api/v2/templates/flows/${templateId}/versions`
      );
      return response;
    } catch (error: unknown) {
      const errorMessage = error && typeof error === 'object' && 'response' in error
        ? ((error.response as { data?: { detail?: string } })?.data?.detail) || 'Erro ao listar versões'
        : 'Erro ao listar versões';
      toast({
        title: 'Erro ao listar versões',
        description: errorMessage,
        variant: 'destructive',
      });
      return null;
    } finally {
      setLoading(false);
    }
  }, [toast]);

  const compareFlowTemplateVersions = useCallback(async (
    templateId: string,
    compareWithId: string
  ): Promise<TemplateVersionCompareResult | null> => {
    setLoading(true);
    try {
      const response = await apiClient.post<TemplateVersionCompareResult>(
        `/api/v2/templates/flows/${templateId}/versions/compare`,
        undefined,
        { compare_with_id: compareWithId }
      );
      return response;
    } catch (error: unknown) {
      const errorMessage = error && typeof error === 'object' && 'response' in error
        ? ((error.response as { data?: { detail?: string } })?.data?.detail) || 'Erro ao comparar versões'
        : 'Erro ao comparar versões';
      toast({
        title: 'Erro ao comparar versões',
        description: errorMessage,
        variant: 'destructive',
      });
      return null;
    } finally {
      setLoading(false);
    }
  }, [toast]);

  const rollbackFlowTemplateVersion = useCallback(async (
    templateId: string,
    reason?: string,
    setAsActive?: boolean
  ): Promise<FlowTemplate | null> => {
    setLoading(true);
    try {
      const response = await apiClient.post<FlowTemplate>(
        `/api/v2/templates/flows/${templateId}/rollback`,
        { reason, set_as_active: setAsActive }
      );
      toast({
        title: 'Rollback realizado',
        description: 'Nova versão criada a partir do rollback',
      });
      return response;
    } catch (error: unknown) {
      const errorMessage = error && typeof error === 'object' && 'response' in error
        ? ((error.response as { data?: { detail?: string } })?.data?.detail) || 'Erro no rollback'
        : 'Erro no rollback';
      toast({
        title: 'Erro no rollback',
        description: errorMessage,
        variant: 'destructive',
      });
      return null;
    } finally {
      setLoading(false);
    }
  }, [toast]);

  const publishFlowTemplateVersion = useCallback(async (
    templateId: string,
    setAsActive?: boolean
  ): Promise<FlowTemplate | null> => {
    setLoading(true);
    try {
      const response = await apiClient.post<FlowTemplate>(
        `/api/v2/templates/flows/${templateId}/publish`,
        undefined,
        { set_as_active: setAsActive }
      );
      toast({
        title: 'Versão publicada',
        description: setAsActive ? 'Versão definida como ativa' : 'Versão publicada',
      });
      return response;
    } catch (error: unknown) {
      const errorMessage = error && typeof error === 'object' && 'response' in error
        ? ((error.response as { data?: { detail?: string } })?.data?.detail) || 'Erro ao publicar versão'
        : 'Erro ao publicar versão';
      toast({
        title: 'Erro ao publicar',
        description: errorMessage,
        variant: 'destructive',
      });
      return null;
    } finally {
      setLoading(false);
    }
  }, [toast]);

  // ==================== Quiz Templates ====================

  const createQuizTemplate = useCallback(async (data: QuizTemplateCreate): Promise<QuizTemplate | null> => {
    setLoading(true);
    try {
      const response = await apiClient.post<QuizTemplate>('/api/v2/templates/quiz', data);

      toast({
        title: 'Quiz criado',
        description: `Quiz "${data.name}" criado com sucesso!`,
      });

      return response;
    } catch (error: unknown) {
      const errorMessage = error && typeof error === 'object' && 'response' in error
        ? ((error.response as { data?: { detail?: string } })?.data?.detail) || 'Ocorreu um erro ao criar o quiz'
        : 'Ocorreu um erro ao criar o quiz';
      toast({
        title: 'Erro ao criar quiz',
        description: errorMessage,
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
      const response = await apiClient.get<PaginatedResponse<QuizTemplate>>('/api/v2/templates/quiz', params || undefined);

      return response;
    } catch (error: unknown) {
      const errorMessage = error && typeof error === 'object' && 'response' in error
        ? ((error.response as { data?: { detail?: string } })?.data?.detail) || 'Ocorreu um erro ao listar quizzes'
        : 'Ocorreu um erro ao listar quizzes';
      toast({
        title: 'Erro ao listar quizzes',
        description: errorMessage,
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
      const response = await apiClient.get<QuizTemplate>(`/api/v2/templates/quiz/${quizId}`);
      return response;
    } catch (error: unknown) {
      const errorMessage = error && typeof error === 'object' && 'response' in error
        ? ((error.response as { data?: { detail?: string } })?.data?.detail) || 'Quiz não encontrado'
        : 'Quiz não encontrado';
      toast({
        title: 'Erro ao buscar quiz',
        description: errorMessage,
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
      const response = await apiClient.put<QuizTemplate>(`/api/v2/templates/quiz/${quizId}`, data);

      toast({
        title: 'Quiz atualizado',
        description: 'Quiz atualizado com sucesso!',
      });

      return response;
    } catch (error: unknown) {
      const errorMessage = error && typeof error === 'object' && 'response' in error
        ? ((error.response as { data?: { detail?: string } })?.data?.detail) || 'Ocorreu um erro ao atualizar o quiz'
        : 'Ocorreu um erro ao atualizar o quiz';
      toast({
        title: 'Erro ao atualizar quiz',
        description: errorMessage,
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
      await apiClient.delete(`/api/v2/templates/quiz/${quizId}`, { soft_delete: softDelete });

      toast({
        title: 'Quiz removido',
        description: softDelete ? 'Quiz desativado com sucesso' : 'Quiz deletado permanentemente',
      });

      return true;
    } catch (error: unknown) {
      const errorMessage = error && typeof error === 'object' && 'response' in error
        ? ((error.response as { data?: { detail?: string } })?.data?.detail) || 'Ocorreu um erro ao remover o quiz'
        : 'Ocorreu um erro ao remover o quiz';
      toast({
        title: 'Erro ao remover quiz',
        description: errorMessage,
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
    listFlowTemplateVersions,
    compareFlowTemplateVersions,
    rollbackFlowTemplateVersion,
    publishFlowTemplateVersion,
    // Quiz templates
    createQuizTemplate,
    listQuizTemplates,
    getQuizTemplate,
    updateQuizTemplate,
    deleteQuizTemplate,
  };
}
