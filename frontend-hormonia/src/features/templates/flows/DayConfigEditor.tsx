/**
 * DayConfigEditor — Physician-facing day-config editing dialog.
 *
 * Loads the day list for a flow template, lets the doctor edit content,
 * message type, and expects_response per day. Supports add/remove days
 * with auto-renumbering.
 */

import React, { useState, useEffect, useCallback } from 'react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useTemplates } from '@/hooks/useTemplates'
import type { DayConfigItem } from '@/hooks/useTemplates'
import { useToast } from '@/components/ui/use-toast'
import { logger } from '@/lib/logger'
import { Trash2, Plus, Loader2 } from 'lucide-react'

interface DayConfigEditorProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  templateId: string
  templateName: string
}

const MESSAGE_TYPE_LABELS: Record<DayConfigItem['message_type'], string> = {
  question: 'Pergunta',
  motivation: 'Motivação',
  reminder: 'Lembrete',
}

export function DayConfigEditor({
  open,
  onOpenChange,
  templateId,
  templateName,
}: DayConfigEditorProps) {
  const { getFlowTemplateDays, updateFlowTemplateDays } = useTemplates()
  const { toast } = useToast()

  const [days, setDays] = useState<DayConfigItem[]>([])
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)

  // Load days when dialog opens
  useEffect(() => {
    if (!open || !templateId) return

    let cancelled = false

    const loadDays = async () => {
      setLoading(true)
      try {
        const result = await getFlowTemplateDays(templateId)
        if (!cancelled && result) {
          setDays(result.days)
        }
      } catch (error) {
        logger.error('Failed to load day configs', error)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    loadDays()
    return () => {
      cancelled = true
    }
  }, [open, templateId, getFlowTemplateDays])

  // ---- Day mutations ----

  const updateDay = useCallback(
    (index: number, field: keyof DayConfigItem, value: DayConfigItem[keyof DayConfigItem]) => {
      setDays((prev) => prev.map((d, i) => (i === index ? { ...d, [field]: value } : d)))
    },
    []
  )

  const removeDay = useCallback((index: number) => {
    setDays((prev) => {
      const updated = prev.filter((_, i) => i !== index)
      // Renumber sequentially
      return updated.map((d, i) => ({ ...d, day_number: i + 1 }))
    })
  }, [])

  const addDay = useCallback(() => {
    setDays((prev) => [
      ...prev,
      {
        day_number: prev.length + 1,
        content: '',
        message_type: 'question' as const,
        expects_response: false,
      },
    ])
  }, [])

  // ---- Save ----

  const handleSave = async () => {
    setSaving(true)
    try {
      await updateFlowTemplateDays(templateId, days)
      toast({
        title: 'Dias salvos',
        description: `${days.length} dia(s) atualizados com sucesso.`,
      })
      onOpenChange(false)
    } catch (error) {
      // Error toast already shown by the hook
      logger.error('Failed to save day configs', error)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Editar Dias — {templateName}</DialogTitle>
        </DialogHeader>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <ScrollArea className="flex-1 pr-4 -mr-4">
            <div className="space-y-6 py-2">
              {days.map((day, index) => (
                <div
                  key={day.day_number}
                  className="rounded-lg border p-4 space-y-3"
                >
                  <div className="flex items-center justify-between">
                    <Label className="text-sm font-semibold">
                      Dia {day.day_number}
                    </Label>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => removeDay(index)}
                      className="h-8 w-8 p-0 text-destructive hover:text-destructive"
                      title="Remover dia"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>

                  <Textarea
                    value={day.content}
                    onChange={(e) => updateDay(index, 'content', e.target.value)}
                    placeholder="Conteúdo da mensagem para este dia..."
                    rows={3}
                  />

                  <div className="flex items-center gap-4 flex-wrap">
                    <div className="flex items-center gap-2">
                      <Label className="text-sm text-muted-foreground whitespace-nowrap">
                        Tipo:
                      </Label>
                      <Select
                        value={day.message_type}
                        onValueChange={(v) =>
                          updateDay(index, 'message_type', v as DayConfigItem['message_type'])
                        }
                      >
                        <SelectTrigger className="w-[140px]">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {(Object.entries(MESSAGE_TYPE_LABELS) as [DayConfigItem['message_type'], string][]).map(
                            ([value, label]) => (
                              <SelectItem key={value} value={value}>
                                {label}
                              </SelectItem>
                            )
                          )}
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="flex items-center gap-2">
                      <Checkbox
                        id={`expects-response-${index}`}
                        checked={day.expects_response}
                        onCheckedChange={(checked) =>
                          updateDay(index, 'expects_response', !!checked)
                        }
                      />
                      <Label
                        htmlFor={`expects-response-${index}`}
                        className="text-sm text-muted-foreground cursor-pointer"
                      >
                        Espera resposta
                      </Label>
                    </div>
                  </div>
                </div>
              ))}

              {days.length === 0 && !loading && (
                <p className="text-center text-sm text-muted-foreground py-8">
                  Nenhum dia configurado. Clique em &quot;Adicionar Dia&quot; para começar.
                </p>
              )}
            </div>
          </ScrollArea>
        )}

        <DialogFooter className="gap-2 sm:gap-0">
          <Button variant="outline" onClick={addDay} disabled={loading || saving}>
            <Plus className="h-4 w-4 mr-1" />
            Adicionar Dia
          </Button>
          <Button onClick={handleSave} disabled={loading || saving}>
            {saving && <Loader2 className="h-4 w-4 mr-1 animate-spin" />}
            Salvar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
