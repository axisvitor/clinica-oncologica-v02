/**
 * Template Management Page
 *
 * Main page for managing flow and quiz templates.
 * Orchestrates tabs and delegates to specialized components.
 */

import React, { memo, useState } from 'react';
import { Plus, FileText, Workflow, Search, Filter } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { withErrorBoundary } from '@/components/error/ErrorBoundary';

import { FlowTemplateList } from './flows/FlowTemplateList';
import { QuizTemplateList } from './quiz/QuizTemplateList';
import { FlowDesignerDialog } from './flows/FlowDesignerDialog';
import { useFlowTemplates } from './flows/hooks/useFlowTemplates';
import { useQuizTemplates } from './quiz/hooks/useQuizTemplates';

export type TemplateFilter = 'all' | 'active' | 'draft';

const TemplateManagementPage = memo(function TemplateManagementPage() {
  // Shared state
  const [searchTerm, setSearchTerm] = useState('');
  const [activeFilter, setActiveFilter] = useState<TemplateFilter>('all');
  const [showFlowDesigner, setShowFlowDesigner] = useState(false);

  // Flow templates
  const {
    templates: flowTemplates,
    totalPages: flowTotalPages,
    page: flowPage,
    setPage: setFlowPage,
    loading: flowLoading,
    error: flowError,
    refetch: refetchFlows,
  } = useFlowTemplates({ filter: activeFilter });

  // Quiz templates
  const {
    templates: quizTemplates,
    totalPages: quizTotalPages,
    page: quizPage,
    setPage: setQuizPage,
    loading: quizLoading,
    error: quizError,
    refetch: refetchQuizzes,
  } = useQuizTemplates({ filter: activeFilter });

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
        <Button onClick={() => setShowFlowDesigner(true)}>
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
          <FlowTemplateList
            templates={filteredFlowTemplates}
            loading={flowLoading}
            error={flowError}
            page={flowPage}
            totalPages={flowTotalPages}
            onPageChange={setFlowPage}
            onRefresh={refetchFlows}
            onCreateNew={() => setShowFlowDesigner(true)}
          />
        </TabsContent>

        {/* Quiz Templates Tab */}
        <TabsContent value="quizzes" className="space-y-4">
          <QuizTemplateList
            templates={filteredQuizTemplates}
            loading={quizLoading}
            error={quizError}
            page={quizPage}
            totalPages={quizTotalPages}
            onPageChange={setQuizPage}
            onRefresh={refetchQuizzes}
          />
        </TabsContent>
      </Tabs>

      {/* Flow Designer Dialog */}
      <FlowDesignerDialog
        open={showFlowDesigner}
        onOpenChange={setShowFlowDesigner}
        onSuccess={refetchFlows}
      />
    </div>
  );
});

// Named export to satisfy react-refresh/only-export-components
const TemplateManagementPageWithErrorBoundary = withErrorBoundary(TemplateManagementPage, {
  level: 'page',
  enableReporting: true,
});

export default TemplateManagementPageWithErrorBoundary;
