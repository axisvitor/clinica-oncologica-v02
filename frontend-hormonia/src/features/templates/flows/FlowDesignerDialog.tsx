/**
 * Flow Designer Dialog Component
 *
 * Modal dialog wrapping FlowDesigner with version controls and save logic.
 */

import React, { memo, useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { FlowDesigner } from '@/features/flow-designer/FlowDesigner';
import { useTemplates, type FlowTemplate } from '@/hooks/useTemplates';
import { useToast } from '@/components/ui/use-toast';
import { convertTemplateToDesign, convertDesignToTemplate } from '../utils/templateConverters';
import type { FlowDesign } from '@/types/flow-designer';

interface FlowDesignerDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  template?: FlowTemplate;
  createNewVersion?: FlowTemplate;
  onSuccess?: () => void;
}

export const FlowDesignerDialog = memo<FlowDesignerDialogProps>(({
  open,
  onOpenChange,
  template,
  createNewVersion,
  onSuccess,
}) => {
  const { toast } = useToast();
  const { createFlowTemplate, updateFlowTemplate } = useTemplates();

  // Version controls
  const [versionNumber, setVersionNumber] = useState<number>(1);
  const [isDraft, setIsDraft] = useState<boolean>(false);
  const [isActive, setIsActive] = useState<boolean>(true);
  const [changelog, setChangelog] = useState<string>('');

  // Initialize version controls when template changes
  useEffect(() => {
    if (createNewVersion) {
      setVersionNumber((createNewVersion.version_number || 1) + 1);
      setIsDraft(true);
      setIsActive(false);
      setChangelog('');
    } else if (template) {
      setVersionNumber(template.version_number || 1);
      setIsDraft(template.is_draft || false);
      setIsActive(template.is_active || false);
      setChangelog(template.description || '');
    } else {
      setVersionNumber(1);
      setIsDraft(false);
      setIsActive(true);
      setChangelog('');
    }
  }, [template, createNewVersion]);

  const handleSave = async (design: FlowDesign) => {
    try {
      if (createNewVersion && !changelog.trim()) {
        toast({
          title: 'Changelog obrigatorio',
          description: 'Informe o motivo da nova versao antes de salvar',
          variant: 'destructive',
        });
        return;
      }

      const templateDescription = createNewVersion
        ? changelog.trim()
        : design.description;
      const templateData = convertDesignToTemplate(design, {
        versionNumber,
        isDraft,
        isActive,
        description: templateDescription,
      });

      if (template && !createNewVersion) {
        // Update existing
        const updated = await updateFlowTemplate(template.id, {
          ...templateData,
          template_name: design.name,
          description: templateDescription,
        });

        if (updated) {
          toast({ title: 'Template atualizado com sucesso' });
          onSuccess?.();
          onOpenChange(false);
        }
      } else {
        // Create new
        const created = await createFlowTemplate(templateData);

        if (created) {
          if (createNewVersion) {
            toast({
              title: 'Nova Versão Criada',
              description: `Versão ${versionNumber} criada com sucesso`,
            });
          } else {
            toast({ title: 'Template criado com sucesso' });
          }
          onSuccess?.();
          onOpenChange(false);
        }
      }
    } catch {
      toast({
        title: 'Erro',
        description: 'Falha ao salvar template',
        variant: 'destructive',
      });
    }
  };

  const initialDesign: FlowDesign | undefined = template
    ? convertTemplateToDesign(template)
    : createNewVersion
    ? convertTemplateToDesign(createNewVersion)
    : undefined;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-[95vw] max-h-[95vh] p-0">
        <DialogHeader className="p-6 pb-0">
          <DialogTitle>
            {template
              ? 'Editar Flow Template'
              : createNewVersion
              ? `Nova Versão - ${createNewVersion.template_name}`
              : 'Criar Novo Flow Template'}
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
                value={versionNumber}
                onChange={(e) => setVersionNumber(parseInt(e.target.value) || 1)}
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
                    checked={isDraft}
                    onChange={(e) => setIsDraft(e.target.checked)}
                    className="rounded border-gray-300"
                  />
                  <span className="text-sm">Rascunho</span>
                </label>
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={isActive}
                    onChange={(e) => setIsActive(e.target.checked)}
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
                <p>• Versão: {versionNumber}.0.0</p>
                <p>• Estado: {isDraft ? 'Rascunho' : 'Publicado'}</p>
                <p>• Status: {isActive ? 'Ativo' : 'Inativo'}</p>
              </div>
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">Changelog</label>
            <Textarea
              value={changelog}
              onChange={(e) => setChangelog(e.target.value)}
              placeholder="Resumo das alteracoes desta versao"
            />
            <p className="text-xs text-muted-foreground">
              Usado como descricao da versao e auditoria
            </p>
          </div>
        </div>

        <div className="h-[65vh] p-6">
          <FlowDesigner
            initialDesign={initialDesign}
            onSave={handleSave}
            className="h-full"
          />
        </div>
      </DialogContent>
    </Dialog>
  );
});

FlowDesignerDialog.displayName = 'FlowDesignerDialog';
