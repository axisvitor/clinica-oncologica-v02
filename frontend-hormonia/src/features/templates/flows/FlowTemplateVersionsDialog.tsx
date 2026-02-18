/**
 * Flow Template Versions Dialog
 *
 * Lists versions, compares diffs, and supports rollback/publish.
 */

import React, { useEffect, useMemo, useState } from 'react'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { useTemplates, type FlowTemplate, type FlowTemplateVersionList } from '@/hooks/useTemplates'

interface FlowTemplateVersionsDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  template: FlowTemplate
}

export function FlowTemplateVersionsDialog({ open, onOpenChange, template }: FlowTemplateVersionsDialogProps) {
  const {
    listFlowTemplateVersions,
    compareFlowTemplateVersions,
    rollbackFlowTemplateVersion,
    publishFlowTemplateVersion
  } = useTemplates()

  const [versions, setVersions] = useState<FlowTemplateVersionList | null>(null)
  const [leftVersionId, setLeftVersionId] = useState<string>('')
  const [rightVersionId, setRightVersionId] = useState<string>('')
  const [diff, setDiff] = useState<string>('')
  const [changes, setChanges] = useState<string[]>([])
  const [rollbackReason, setRollbackReason] = useState<string>('')
  const [setAsActive, setSetAsActive] = useState<boolean>(false)
  const [isLoading, setIsLoading] = useState<boolean>(false)

  useEffect(() => {
    if (!open) return

    const loadVersions = async () => {
      setIsLoading(true)
      const data = await listFlowTemplateVersions(template.id)
      setVersions(data)
      const versionList = data?.data ?? []
      const [firstVersion, secondVersion] = versionList
      if (firstVersion) {
        setLeftVersionId(firstVersion.id)
        if (secondVersion) {
          setRightVersionId(secondVersion.id)
        }
      }
      setIsLoading(false)
    }

    loadVersions()
  }, [open, template.id, listFlowTemplateVersions])

  const versionOptions = useMemo(() => versions?.data || [], [versions])

  const handleCompare = async () => {
    if (!leftVersionId || !rightVersionId || leftVersionId === rightVersionId) return
    setIsLoading(true)
    const result = await compareFlowTemplateVersions(leftVersionId, rightVersionId)
    if (result) {
      setDiff(result.diff)
      setChanges(result.changes || [])
    }
    setIsLoading(false)
  }

  const handleRollback = async () => {
    if (!leftVersionId) return
    await rollbackFlowTemplateVersion(leftVersionId, rollbackReason, setAsActive)
  }

  const handlePublish = async () => {
    if (!leftVersionId) return
    await publishFlowTemplateVersion(leftVersionId, setAsActive)
  }

  const renderDiff = (content: string) => {
    if (!content) return <p className="text-sm text-muted-foreground">Sem alteracoes para mostrar</p>

    return (
      <pre className="text-xs whitespace-pre-wrap rounded-md bg-muted p-3">
        {content.split('\n').map((line, idx) => {
          const colorClass = line.startsWith('+')
            ? 'text-green-700'
            : line.startsWith('-')
            ? 'text-red-700'
            : 'text-muted-foreground'
          return (
            <div key={`${idx}-${line.slice(0, 12)}`} className={colorClass}>
              {line}
            </div>
          )
        })}
      </pre>
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl">
        <DialogHeader>
          <DialogTitle>Versoes do Template</DialogTitle>
          <DialogDescription>
            Compare versoes, publique rascunhos ou faca rollback
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-4">
            <div className="min-w-[200px]">
              <Select value={leftVersionId} onValueChange={setLeftVersionId}>
                <SelectTrigger>
                  <SelectValue placeholder="Versao base" />
                </SelectTrigger>
                <SelectContent>
                  {versionOptions.map((version) => (
                    <SelectItem key={version.id} value={version.id}>
                      v{version.version_number} {version.is_active ? '(ativa)' : ''}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="min-w-[200px]">
              <Select value={rightVersionId} onValueChange={setRightVersionId}>
                <SelectTrigger>
                  <SelectValue placeholder="Versao para comparar" />
                </SelectTrigger>
                <SelectContent>
                  {versionOptions.map((version) => (
                    <SelectItem key={version.id} value={version.id}>
                      v{version.version_number} {version.is_active ? '(ativa)' : ''}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <Button onClick={handleCompare} disabled={isLoading || !leftVersionId || !rightVersionId}>
              Comparar
            </Button>
          </div>

          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Badge variant="outline">Alteracoes</Badge>
              <span className="text-xs text-muted-foreground">
                {changes.length} mudancas detectadas
              </span>
            </div>
            {renderDiff(diff)}
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            <div className="space-y-2">
              <label className="text-sm font-medium">Motivo do rollback</label>
              <Textarea
                value={rollbackReason}
                onChange={(event) => setRollbackReason(event.target.value)}
                placeholder="Descreva o motivo"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Definir como ativa</label>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={setAsActive}
                  onChange={(event) => setSetAsActive(event.target.checked)}
                />
                <span className="text-sm">Ativar esta versao</span>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={handleRollback} disabled={isLoading || !leftVersionId}>
              Rollback
            </Button>
            <Button onClick={handlePublish} disabled={isLoading || !leftVersionId}>
              Publicar
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
