/**
 * Template Management Page
 *
 * Admin page for managing flow and quiz templates with full CRUD operations.
 * Integrates FlowDesigner with the database-backed template API.
 */

import React, { useState, useEffect, memo, useCallback } from 'react';
import { Plus, FileText, Workflow, Search, Filter, AlertTriangle, RefreshCw } from 'lucide-react';
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
import { FlowDesigner } from '@/components/flow-designer/FlowDesigner';
import { QuizTemplateCard } from '@/components/quiz/QuizTemplateCard';
import { useTemplates, FlowTemplate, QuizTemplate } from '@/hooks/useTemplates';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/components/ui/use-toast';
import { withErrorBoundary } from '@/components/error/ErrorBoundary';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

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
    deleteQuizTemplate,
  } = useTemplates();

  // State
  const [flowTemplates, setFlowTemplates] = useState<FlowTemplate[]>([]);
  const [quizTemplates, setQuizTemplates] = useState<QuizTemplate[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [activeFilter, setActiveFilter] = useState<'all' | 'active' | 'draft'>('all');
  const [showFlowDesigner, setShowFlowDesigner] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<FlowTemplate | null>(null);
  
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
      const params: any = { page: flowPage, size: 10 };

      if (activeFilter === 'active') params.is_active = true;
      if (activeFilter === 'draft') params.is_draft = true;

      const response = await listFlowTemplates(params);
      if (response) {
        setFlowTemplates(response.items);
        setFlowTotalPages(response.pages);
      }
    } catch (error) {
      console.error('Failed to load flow templates:', error)
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
      const params: any = { page: quizPage, size: 10 };

      if (activeFilter === 'active') params.is_active = true;

      const response = await listQuizTemplates(params);
      if (response) {
        setQuizTemplates(response.items);
        setQuizTotalPages(response.pages);
      }
    } catch (error) {
      console.error('Failed to load quiz templates:', error)
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
  const handleFlowSave = async (design: any) => {
    // Convert FlowDesign to API format as array
    const steps: any[] = design.nodes.map((node: any, index: number) => {
      const messageType = node.type || 'text';
      
      // Validate message type
      if (!VALID_MESSAGE_TYPES.includes(messageType)) {
        console.warn(`Invalid message_type '${messageType}', defaulting to 'text'`);
      }

      return {
        step_number: index + 1,
        intent: node.data.label || 'unknown',
        ai_instructions: node.data.aiInstructions || '',
        message_type: VALID_MESSAGE_TYPES.includes(messageType) ? messageType : 'text',
        base_content: node.data.content || '',
        personalization_hints: node.data.personalizationHints || [],
      };
    });

    const templateData = {
      kind_key: design.metadata?.flowType || 'custom_flow',
      display_name: design.metadata?.name || 'Novo Flow',
      description: design.metadata?.description || '',
      version_number: flowVersionNumber,
      steps,
      metadata: {
        flow_type: design.metadata?.flowType || 'custom_flow',
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
        template_name: design.metadata?.name,
        description: design.metadata?.description,
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

  const handleEditQuiz = (_quizId: string) => {
    toast({
      title: 'Edição de Quiz',
      description: 'Funcionalidade de edição será implementada em breve. Por favor, use a página de Questionários.',
    });
    // TODO: Implement quiz edit dialog similar to QuestionariosPage
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
            <Select value={activeFilter} onValueChange={(v: any) => setActiveFilter(v)}>
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
                  onPreview={() => console.warn('Preview', quiz.id)}
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
              initialDesign={editingTemplate ? convertTemplateToDesign(editingTemplate) : undefined}
              onSave={handleFlowSave}
              className="h-full"
            />
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// Helper function to convert template to FlowDesign format
function convertTemplateToDesign(template: FlowTemplate): any {
  // Handle both array and dict formats for steps
  let stepsArray: any[] = [];
  
  if (Array.isArray(template.steps)) {
    stepsArray = template.steps;
  } else if (template.steps && typeof template.steps === 'object') {
    // Convert dict to array
    stepsArray = Object.values(template.steps);
  }

  const nodes = stepsArray.map((step: any, index) => ({
    id: `node-${index}`,
    type: step.message_type || 'text',
    position: { x: 100 + index * 250, y: 100 },
    data: {
      label: step.intent || 'Message',
      content: step.base_content || '',
      aiInstructions: step.ai_instructions || '',
      personalizationHints: step.personalization_hints || [],
    },
  }));

  const connections = nodes.slice(0, -1).map((node, index) => ({
    id: `conn-${index}`,
    source: node.id,
    target: nodes[index + 1]?.id || '',
    type: 'default',
  }));

  return {
    id: template.id,
    name: template.template_name,
    description: template.description,
    nodes,
    connections,
    metadata: {
      name: template.template_name,
      flowType: template.kind_key,
      description: template.description,
      version: String(template.version_number),
    },
  };
}

// Export with error boundary for production safety
export default withErrorBoundary(memo(TemplateManagementPage), {
  level: 'page',
  enableReporting: true
})
