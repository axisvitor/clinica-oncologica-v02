/**
 * Template Management Page
 *
 * Admin page for managing flow and quiz templates with full CRUD operations.
 * Integrates FlowDesigner with the database-backed template API.
 */

import React, { useState, useEffect, memo, useCallback } from 'react';
import { Plus, FileText, Workflow, Search, Filter, AlertTriangle, RefreshCw, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { FlowDesigner } from '@/features/flow-designer/FlowDesigner';
import { QuizTemplateCard } from '@/features/quiz/QuizTemplateCard';
import { useTemplates, FlowTemplate, QuizTemplate, FlowTemplateStep, FlowTemplateCreate, QuizTemplateUpdate, QuizQuestion, QuizQuestionOption } from '@/hooks/useTemplates';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/use-toast';
import { withErrorBoundary } from '@/components/error/ErrorBoundary';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { logger } from '@/lib/logger';

// Import FlowDesign type from flow-designer
import type { FlowDesign, FlowNode, FlowConnection } from '@/lib/types/flow-designer';

// Template list params type
interface TemplateListParams {
  page: number;
  size: number;
  is_active?: boolean;
  is_draft?: boolean;
}

// Filter type
type TemplateFilter = 'all' | 'active' | 'draft';

// Loading skeleton for template cards
const TemplateCardSkeleton = memo(() => (
  <Card>
    <CardHeader>
      <div className="flex items-start justify-between">
        <div className="space-y-2">
          <Skeleton className="h-5 w-32" />
          <Skeleton className="h-4 w-24" />
        </div>
        <div className="flex gap-2">
          <Skeleton className="h-5 w-16" />
        </div>
      </div>
    </CardHeader>
    <CardContent>
      <div className="space-y-4">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-3/4" />
        <div className="space-y-2">
          <Skeleton className="h-3 w-20" />
          <Skeleton className="h-3 w-16" />
        </div>
        <div className="flex gap-2">
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
        </div>
      </div>
    </CardContent>
  </Card>
))

TemplateCardSkeleton.displayName = 'TemplateCardSkeleton'

function TemplateManagementPage() {
  const { toast } = useToast()
  const {
    loading,
    listFlowTemplates,
    listQuizTemplates,
    createFlowTemplate,
    updateFlowTemplate,
    deleteFlowTemplate,
    updateQuizTemplate,
    deleteQuizTemplate,
  } = useTemplates();

  // State
  const [flowTemplates, setFlowTemplates] = useState<FlowTemplate[]>([]);
  const [quizTemplates, setQuizTemplates] = useState<QuizTemplate[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [activeFilter, setActiveFilter] = useState<TemplateFilter>('all');
  const [showFlowDesigner, setShowFlowDesigner] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<FlowTemplate | null>(null);

  // Quiz edit state
  const [showQuizEditor, setShowQuizEditor] = useState(false);
  const [editingQuiz, setEditingQuiz] = useState<QuizTemplate | null>(null);
  const [quizFormData, setQuizFormData] = useState<{
    name: string;
    version: string;
    description: string;
    category: string;
    is_active: boolean;
    questions: QuizQuestion[];
  }>({
    name: '',
    version: '',
    description: '',
    category: '',
    is_active: true,
    questions: [],
  });
  const [isQuizSaving, setIsQuizSaving] = useState(false);

  const [flowError, setFlowError] = useState<string | null>(null);
  const [quizError, setQuizError] = useState<string | null>(null);

  // Flow versioning controls
  const [flowVersionNumber, setFlowVersionNumber] = useState<number>(1);
  const [flowIsDraft, setFlowIsDraft] = useState<boolean>(false);
  const [flowIsActive, setFlowIsActive] = useState<boolean>(true);

  // Pagination
  const [flowPage, setFlowPage] = useState(1);
  const [quizPage, setQuizPage] = useState(1);
  const [flowTotalPages, setFlowTotalPages] = useState(1);
  const [quizTotalPages, setQuizTotalPages] = useState(1);

  // Load templates effect is placed after callbacks definitions

  const loadFlowTemplates = useCallback(async () => {
    try {
      setFlowError(null)
      const params: TemplateListParams = { page: flowPage, size: 10 };

      if (activeFilter === 'active') params.is_active = true;
      if (activeFilter === 'draft') params.is_draft = true;

      const response = await listFlowTemplates(params);
      if (response) {
        setFlowTemplates(response.items);
        setFlowTotalPages(response.pages);
      }
    } catch (error) {
      logger.error('Failed to load flow templates', error)
      setFlowError('Erro ao carregar templates de flow')
      toast({
        title: 'Erro',
        description: 'Falha ao carregar templates de flow',
        variant: 'destructive'
      })
    }
  }, [flowPage, activeFilter, listFlowTemplates, toast]);

  const loadQuizTemplates = useCallback(async () => {
    try {
      setQuizError(null)
      const params: TemplateListParams = { page: quizPage, size: 10 };

      if (activeFilter === 'active') params.is_active = true;

      const response = await listQuizTemplates(params);
      if (response) {
        setQuizTemplates(response.items);
        setQuizTotalPages(response.pages);
      }
    } catch (error) {
      logger.error('Failed to load quiz templates', error)
      setQuizError('Erro ao carregar templates de quiz')
      toast({
        title: 'Erro',
        description: 'Falha ao carregar templates de quiz',
        variant: 'destructive'
      })
    }
  }, [quizPage, activeFilter, listQuizTemplates, toast]);

  // Load templates
  useEffect(() => {
    loadFlowTemplates();
    loadQuizTemplates();
  }, [flowPage, quizPage, activeFilter, loadFlowTemplates, loadQuizTemplates]);

  // Filter templates by search
  const filteredFlowTemplates = flowTemplates.filter(
    (t) =>
      t.template_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      t.kind_key.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const filteredQuizTemplates = quizTemplates.filter(
    (t) =>
      t.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      t.category.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // Valid message types based on backend enum
  const VALID_MESSAGE_TYPES = ['text', 'image', 'audio', 'video', 'document'];

  // Handle Flow Designer save
  const handleFlowSave = async (design: FlowDesign) => {
    // Convert FlowDesign to API format as array of FlowTemplateStep
    const steps: FlowTemplateStep[] = design.nodes.map((node: FlowNode, index: number): FlowTemplateStep => {
      const messageType = node.type || 'text';
      const config = node.data.config || {};

      // Validate message type
      if (!VALID_MESSAGE_TYPES.includes(messageType)) {
        logger.warn(`Invalid message_type '${messageType}', defaulting to 'text'`);
      }

      return {
        step_number: index + 1,
        intent: node.data.label || 'unknown',
        ai_instructions: (config['aiInstructions'] as string) || '',
        message_type: VALID_MESSAGE_TYPES.includes(messageType) ? messageType : 'text',
        base_content: (config['content'] as string) || node.data.description || '',
        personalization_hints: (config['personalizationHints'] as string[]) || [],
      };
    });

    // Extract values from metadata with fallbacks
    const flowCategory = design.metadata?.category || 'custom_flow';

    const templateData: FlowTemplateCreate = {
      kind_key: flowCategory,
      display_name: design.name || 'Novo Flow',
      description: design.description || '',
      version_number: flowVersionNumber,
      steps,
      metadata: {
        flow_type: flowCategory,
        humanization_level: 'high',
        version: `${flowVersionNumber}.0.0`,
      },
      is_active: flowIsActive,
      is_draft: flowIsDraft,
    };

    if (editingTemplate) {
      // Update existing - include status fields
      const updated = await updateFlowTemplate(editingTemplate.id, {
        steps,
        template_name: design.name,
        description: design.description,
        is_active: flowIsActive,
        is_draft: flowIsDraft,
      });

      if (updated) {
        loadFlowTemplates();
        setShowFlowDesigner(false);
        setEditingTemplate(null);
      }
    } else {
      // Create new
      const created = await createFlowTemplate(templateData);

      if (created) {
        loadFlowTemplates();
        setShowFlowDesigner(false);
      }
    }
  };

  // Handle template delete
  const handleDeleteFlow = async (templateId: string) => {
    const success = await deleteFlowTemplate(templateId, true) // soft delete
    if (success) {
      loadFlowTemplates()
      toast({ title: 'Template desativado' })
    }
  };

  const handleDeleteQuiz = async (quizId: string) => {
    const success = await deleteQuizTemplate(quizId, true) // soft delete
    if (success) {
      loadQuizTemplates()
      toast({ title: 'Quiz desativado' })
    }
  };

  const handleEditQuiz = (quizId: string) => {
    const quiz = quizTemplates.find(q => q.id === quizId);
    if (!quiz) {
      toast({
        title: 'Erro',
        description: 'Quiz não encontrado',
        variant: 'destructive',
      });
      return;
    }

    setEditingQuiz(quiz);
    setQuizFormData({
      name: quiz.name,
      version: quiz.version,
      description: quiz.description || '',
      category: quiz.category,
      is_active: quiz.is_active,
      questions: quiz.questions || [],
    });
    setShowQuizEditor(true);
  };

  const handleQuizSave = async () => {
    if (!editingQuiz) return;

    setIsQuizSaving(true);
    try {
      const updateData: QuizTemplateUpdate = {
        name: quizFormData.name,
        version: quizFormData.version,
        description: quizFormData.description,
        category: quizFormData.category,
        is_active: quizFormData.is_active,
        questions: quizFormData.questions,
      };

      const updated = await updateQuizTemplate(editingQuiz.id, updateData);
      if (updated) {
        loadQuizTemplates();
        setShowQuizEditor(false);
        setEditingQuiz(null);
        toast({
          title: 'Quiz atualizado',
          description: `"${quizFormData.name}" foi atualizado com sucesso.`,
        });
      }
    } catch (error) {
      logger.error('Failed to update quiz', error);
      toast({
        title: 'Erro ao atualizar',
        description: 'Não foi possível salvar as alterações.',
        variant: 'destructive',
      });
    } finally {
      setIsQuizSaving(false);
    }
  };

  const handleQuizQuestionUpdate = (index: number, field: keyof QuizQuestion, value: unknown) => {
    const updatedQuestions = [...quizFormData.questions];
    const existingQuestion = updatedQuestions[index];
    if (!existingQuestion) return;
    updatedQuestions[index] = {
      ...existingQuestion,
      [field]: value,
    };
    setQuizFormData(prev => ({ ...prev, questions: updatedQuestions }));
  };

  const handleAddQuizQuestion = () => {
    const newQuestion: QuizQuestion = {
      id: `q${Date.now()}`,
      type: 'multiple_choice',
      text: '',
      required: true,
      options: [
        { text: 'Opção 1', value: 'opt1' },
        { text: 'Opção 2', value: 'opt2' },
      ],
    };
    setQuizFormData(prev => ({
      ...prev,
      questions: [...prev.questions, newQuestion],
    }));
  };

  const handleRemoveQuizQuestion = (index: number) => {
    setQuizFormData(prev => ({
      ...prev,
      questions: prev.questions.filter((_, i) => i !== index),
    }));
  };

  const handleQuestionOptionUpdate = (questionIndex: number, optionIndex: number, field: keyof QuizQuestionOption, value: unknown) => {
    const updatedQuestions = [...quizFormData.questions];
    const question = updatedQuestions[questionIndex];
    if (!question) return;
    if (question.options) {
      const existingOption = question.options[optionIndex];
      if (!existingOption) return;
      question.options[optionIndex] = {
        ...existingOption,
        [field]: value,
      };
    }
    setQuizFormData(prev => ({ ...prev, questions: updatedQuestions }));
  };

  const handleAddQuestionOption = (questionIndex: number) => {
    const updatedQuestions = [...quizFormData.questions];
    const question = updatedQuestions[questionIndex];
    if (!question) return;
    if (!question.options) {
      question.options = [];
    }
    question.options.push({
      text: `Opção ${question.options.length + 1}`,
      value: `opt${question.options.length + 1}`,
    });
    setQuizFormData(prev => ({ ...prev, questions: updatedQuestions }));
  };

  const handleRemoveQuestionOption = (questionIndex: number, optionIndex: number) => {
    const updatedQuestions = [...quizFormData.questions];
    const question = updatedQuestions[questionIndex];
    if (!question) return;
    if (question.options) {
      question.options = question.options.filter((_, i) => i !== optionIndex);
    }
    setQuizFormData(prev => ({ ...prev, questions: updatedQuestions }));
  };

  const handleCreateNewFlowVersion = (template: FlowTemplate) => {
    // Create new version based on existing template
    // Set editing template temporarily to prefill designer, but mark as new version
    const newVersionTemplate = {
      ...template,
      id: '', // Clear ID to create new
      version_number: (template.version_number || 1) + 1,
      is_draft: true,
      is_active: false,
    };

    setEditingTemplate(newVersionTemplate as FlowTemplate);
    setFlowVersionNumber((template.version_number || 1) + 1);
    setFlowIsDraft(true);
    setFlowIsActive(false);
    setShowFlowDesigner(true);

    toast({
      title: 'Nova Versão',
      description: `Criando versão ${(template.version_number || 1) + 1} baseada no template '${template.template_name}'`,
    });
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Gerenciamento de Templates</h1>
          <p className="text-muted-foreground mt-1">
            Crie e gerencie templates de flows e quizzes
          </p>
        </div>
        <Button onClick={() => {
          setEditingTemplate(null);
          setFlowVersionNumber(1);
          setFlowIsDraft(false);
          setFlowIsActive(true);
          setShowFlowDesigner(true);
        }}>
          <Plus className="h-4 w-4 mr-2" />
          Novo Template
        </Button>
      </div>

      {/* Search and Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Buscar templates..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
              />
            </div>
            <Select value={activeFilter} onValueChange={(v: TemplateFilter) => setActiveFilter(v)}>
              <SelectTrigger className="w-[180px]">
                <Filter className="h-4 w-4 mr-2" />
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todos</SelectItem>
                <SelectItem value="active">Ativos</SelectItem>
                <SelectItem value="draft">Rascunhos</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Tabs */}
      <Tabs defaultValue="flows" className="space-y-4">
        <TabsList>
          <TabsTrigger value="flows" className="flex items-center gap-2">
            <Workflow className="h-4 w-4" />
            Flow Templates ({flowTemplates.length})
          </TabsTrigger>
          <TabsTrigger value="quizzes" className="flex items-center gap-2">
            <FileText className="h-4 w-4" />
            Quiz Templates ({quizTemplates.length})
          </TabsTrigger>
        </TabsList>

        {/* Flow Templates Tab */}
        <TabsContent value="flows" className="space-y-4">
          {flowError ? (
            <Card>
              <CardContent className="text-center py-12">
                <AlertTriangle className="h-12 w-12 mx-auto text-red-500 mb-4" />
                <p className="text-red-600 mb-4">{flowError}</p>
                <Button onClick={loadFlowTemplates} variant="outline">
                  <RefreshCw className="h-4 w-4 mr-2" />
                  Tentar Novamente
                </Button>
              </CardContent>
            </Card>
          ) : loading ? (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {Array.from({ length: 6 }, (_, i) => (
                <TemplateCardSkeleton key={i} />
              ))}
            </div>
          ) : filteredFlowTemplates.length === 0 ? (
            <Card>
              <CardContent className="text-center py-12">
                <Workflow className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                <p className="text-muted-foreground">Nenhum template encontrado</p>
                <Button onClick={() => setShowFlowDesigner(true)} className="mt-4">
                  Criar Primeiro Template
                </Button>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {filteredFlowTemplates.map((template) => (
                <Card key={template.id} className="hover:shadow-md transition-shadow">
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <div>
                        <CardTitle className="text-lg">{template.template_name}</CardTitle>
                        <CardDescription className="mt-1">
                          {template.kind_key}
                        </CardDescription>
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
                        <div>Steps: {Array.isArray(template.steps) ? template.steps.length : Object.keys(template.steps || {}).length}</div>
                      </div>
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setEditingTemplate(template);
                            setFlowVersionNumber(template.version_number || 1);
                            setFlowIsDraft(template.is_draft || false);
                            setFlowIsActive(template.is_active || false);
                            setShowFlowDesigner(true);
                          }}
                        >
                          Editar
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleCreateNewFlowVersion(template)}
                        >
                          Nova Versão
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleDeleteFlow(template.id)}
                        >
                          Desativar
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          {/* Pagination */}
          {flowTotalPages > 1 && (
            <div className="flex justify-center gap-2 mt-6">
              <Button
                variant="outline"
                onClick={() => setFlowPage((p) => Math.max(1, p - 1))}
                disabled={flowPage === 1}
              >
                Anterior
              </Button>
              <span className="flex items-center px-4">
                Página {flowPage} de {flowTotalPages}
              </span>
              <Button
                variant="outline"
                onClick={() => setFlowPage((p) => Math.min(flowTotalPages, p + 1))}
                disabled={flowPage === flowTotalPages}
              >
                Próxima
              </Button>
            </div>
          )}
        </TabsContent>

        {/* Quiz Templates Tab */}
        <TabsContent value="quizzes" className="space-y-4">
          {quizError ? (
            <Card>
              <CardContent className="text-center py-12">
                <AlertTriangle className="h-12 w-12 mx-auto text-red-500 mb-4" />
                <p className="text-red-600 mb-4">{quizError}</p>
                <Button onClick={loadQuizTemplates} variant="outline">
                  <RefreshCw className="h-4 w-4 mr-2" />
                  Tentar Novamente
                </Button>
              </CardContent>
            </Card>
          ) : loading ? (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {Array.from({ length: 6 }, (_, i) => (
                <TemplateCardSkeleton key={i} />
              ))}
            </div>
          ) : filteredQuizTemplates.length === 0 ? (
            <Card>
              <CardContent className="text-center py-12">
                <FileText className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                <p className="text-muted-foreground">Nenhum quiz encontrado</p>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {filteredQuizTemplates.map((quiz) => (
                <QuizTemplateCard
                  key={quiz.id}
                  template={quiz}
                  onPreview={() => logger.debug('Preview quiz', quiz.id)}
                  onEdit={handleEditQuiz}
                  onDelete={handleDeleteQuiz}
                  showAdminActions={true}
                />
              ))}
            </div>
          )}

          {/* Pagination */}
          {quizTotalPages > 1 && (
            <div className="flex justify-center gap-2 mt-6">
              <Button
                variant="outline"
                onClick={() => setQuizPage((p) => Math.max(1, p - 1))}
                disabled={quizPage === 1}
              >
                Anterior
              </Button>
              <span className="flex items-center px-4">
                Página {quizPage} de {quizTotalPages}
              </span>
              <Button
                variant="outline"
                onClick={() => setQuizPage((p) => Math.min(quizTotalPages, p + 1))}
                disabled={quizPage === quizTotalPages}
              >
                Próxima
              </Button>
            </div>
          )}
        </TabsContent>
      </Tabs>

      {/* Flow Designer Dialog */}
      <Dialog open={showFlowDesigner} onOpenChange={setShowFlowDesigner}>
        <DialogContent className="max-w-[95vw] max-h-[95vh] p-0">
          <DialogHeader className="p-6 pb-0">
            <DialogTitle>
              {editingTemplate ? 'Editar Flow Template' : 'Criar Novo Flow Template'}
            </DialogTitle>
            <DialogDescription>
              Use o designer visual para criar ou editar seu flow template
            </DialogDescription>
          </DialogHeader>

          {/* Version Controls */}
          <div className="px-6 py-4 border-b space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Número da Versão</label>
                <Input
                  type="number"
                  min="1"
                  value={flowVersionNumber}
                  onChange={(e) => setFlowVersionNumber(parseInt(e.target.value) || 1)}
                  placeholder="1"
                />
                <p className="text-xs text-muted-foreground">
                  Versão do template (ex: 1, 2, 3...)
                </p>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">Status</label>
                <div className="flex items-center space-x-4">
                  <label className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      checked={flowIsDraft}
                      onChange={(e) => setFlowIsDraft(e.target.checked)}
                      className="rounded border-gray-300"
                    />
                    <span className="text-sm">Rascunho</span>
                  </label>
                  <label className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      checked={flowIsActive}
                      onChange={(e) => setFlowIsActive(e.target.checked)}
                      className="rounded border-gray-300"
                    />
                    <span className="text-sm">Ativo</span>
                  </label>
                </div>
                <p className="text-xs text-muted-foreground">
                  Marque como rascunho para edições futuras
                </p>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">Informações</label>
                <div className="text-xs text-muted-foreground space-y-1">
                  <p>• Versão: {flowVersionNumber}.0.0</p>
                  <p>• Estado: {flowIsDraft ? 'Rascunho' : 'Publicado'}</p>
                  <p>• Status: {flowIsActive ? 'Ativo' : 'Inativo'}</p>
                </div>
              </div>
            </div>
          </div>

          <div className="h-[65vh] p-6">
            <FlowDesigner
              initialDesign={editingTemplate ? convertTemplateToDesign(editingTemplate) as FlowDesign : undefined}
              onSave={handleFlowSave}
              className="h-full"
            />
          </div>
        </DialogContent>
      </Dialog>

      {/* Quiz Editor Dialog */}
      <Dialog open={showQuizEditor} onOpenChange={(open) => {
        if (!open) {
          setShowQuizEditor(false);
          setEditingQuiz(null);
        }
      }}>
        <DialogContent className="max-w-[95vw] sm:max-w-4xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              Editar Quiz: {editingQuiz?.name}
            </DialogTitle>
            <DialogDescription>
              Modifique as informações e perguntas do quiz
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-6 py-4">
            {/* Basic Info */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="quiz-name">Nome do Quiz</Label>
                <Input
                  id="quiz-name"
                  value={quizFormData.name}
                  onChange={(e) => setQuizFormData(prev => ({ ...prev, name: e.target.value }))}
                  placeholder="Nome do questionário"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="quiz-version">Versão</Label>
                <Input
                  id="quiz-version"
                  value={quizFormData.version}
                  onChange={(e) => setQuizFormData(prev => ({ ...prev, version: e.target.value }))}
                  placeholder="1.0"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="quiz-category">Categoria</Label>
                <Input
                  id="quiz-category"
                  value={quizFormData.category}
                  onChange={(e) => setQuizFormData(prev => ({ ...prev, category: e.target.value }))}
                  placeholder="Categoria do quiz"
                />
              </div>
              <div className="flex items-center space-x-2 pt-6">
                <Switch
                  id="quiz-active"
                  checked={quizFormData.is_active}
                  onCheckedChange={(checked) => setQuizFormData(prev => ({ ...prev, is_active: checked }))}
                />
                <Label htmlFor="quiz-active">Quiz Ativo</Label>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="quiz-description">Descrição</Label>
              <Textarea
                id="quiz-description"
                value={quizFormData.description}
                onChange={(e) => setQuizFormData(prev => ({ ...prev, description: e.target.value }))}
                placeholder="Descrição do questionário"
                rows={3}
              />
            </div>

            {/* Questions */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <Label className="text-lg font-semibold">Perguntas ({quizFormData.questions.length})</Label>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleAddQuizQuestion}
                >
                  <Plus className="h-4 w-4 mr-2" />
                  Adicionar Pergunta
                </Button>
              </div>

              {quizFormData.questions.map((question, qIndex) => (
                <Card key={question.id} className="p-4">
                  <div className="space-y-4">
                    <div className="flex items-start justify-between">
                      <span className="text-sm font-medium text-muted-foreground">
                        Pergunta {qIndex + 1}
                      </span>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => handleRemoveQuizQuestion(qIndex)}
                        className="text-red-500 hover:text-red-700"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>Texto da Pergunta</Label>
                        <Input
                          value={question.text}
                          onChange={(e) => handleQuizQuestionUpdate(qIndex, 'text', e.target.value)}
                          placeholder="Digite a pergunta"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>Tipo</Label>
                        <Select
                          value={question.type}
                          onValueChange={(value) => handleQuizQuestionUpdate(qIndex, 'type', value)}
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="multiple_choice">Múltipla Escolha</SelectItem>
                            <SelectItem value="open_text">Texto Aberto</SelectItem>
                            <SelectItem value="scale">Escala</SelectItem>
                            <SelectItem value="yes_no">Sim/Não</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>

                    <div className="flex items-center space-x-2">
                      <Switch
                        checked={question.required ?? true}
                        onCheckedChange={(checked) => handleQuizQuestionUpdate(qIndex, 'required', checked)}
                      />
                      <Label>Obrigatória</Label>
                    </div>

                    {/* Options for multiple choice */}
                    {question.type === 'multiple_choice' && (
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <Label>Opções</Label>
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => handleAddQuestionOption(qIndex)}
                          >
                            <Plus className="h-3 w-3 mr-1" />
                            Opção
                          </Button>
                        </div>
                        {question.options?.map((option, oIndex) => (
                          <div key={oIndex} className="flex items-center gap-2">
                            <Input
                              value={option.text}
                              onChange={(e) => handleQuestionOptionUpdate(qIndex, oIndex, 'text', e.target.value)}
                              placeholder={`Opção ${oIndex + 1}`}
                              className="flex-1"
                            />
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              onClick={() => handleRemoveQuestionOption(qIndex, oIndex)}
                              className="text-red-500"
                              disabled={(question.options?.length ?? 0) <= 2}
                            >
                              <Trash2 className="h-3 w-3" />
                            </Button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </Card>
              ))}

              {quizFormData.questions.length === 0 && (
                <Card className="p-8 text-center">
                  <p className="text-muted-foreground">Nenhuma pergunta ainda. Clique em "Adicionar Pergunta" para começar.</p>
                </Card>
              )}
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setShowQuizEditor(false);
                setEditingQuiz(null);
              }}
              disabled={isQuizSaving}
            >
              Cancelar
            </Button>
            <Button
              onClick={handleQuizSave}
              disabled={isQuizSaving || !quizFormData.name}
            >
              {isQuizSaving ? (
                <>
                  <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                  Salvando...
                </>
              ) : (
                'Salvar Alterações'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// Helper function to convert template to FlowDesign format
function convertTemplateToDesign(template: FlowTemplate): Partial<FlowDesign> {
  // Handle both array and dict formats for steps
  let stepsArray: FlowTemplateStep[] = [];

  if (Array.isArray(template.steps)) {
    stepsArray = template.steps;
  } else if (template.steps && typeof template.steps === 'object') {
    // Convert dict to array
    stepsArray = Object.values(template.steps) as FlowTemplateStep[];
  }

  const nodes: FlowNode[] = stepsArray.map((step: FlowTemplateStep, index: number) => ({
    id: `node-${index}`,
    type: (step.message_type || 'message') as import('@/lib/types/flow-designer').FlowNodeType,
    position: { x: 100 + index * 250, y: 100 },
    data: {
      label: step.intent || 'Message',
      description: step.base_content || '',
      config: {
        content: step.base_content || '',
        aiInstructions: step.ai_instructions || '',
        personalizationHints: step.personalization_hints || [],
      },
    },
  }));

  const connections: FlowConnection[] = nodes.slice(0, -1).map((node, index) => ({
    id: `conn-${index}`,
    source: node.id,
    target: nodes[index + 1]?.id || '',
  }));

  return {
    id: template.id,
    name: template.template_name,
    description: template.description || '',
    version: String(template.version_number || 1),
    nodes,
    connections,
    variables: [],
    metadata: {
      author: 'system',
      tags: [template.kind_key],
      category: template.kind_key,
      complexity_level: 'simple',
    },
    created_at: template.created_at || new Date().toISOString(),
    updated_at: template.updated_at || new Date().toISOString(),
  };
}

// Export with error boundary for production safety
export default withErrorBoundary(memo(TemplateManagementPage), {
  level: 'page',
  enableReporting: true
})
