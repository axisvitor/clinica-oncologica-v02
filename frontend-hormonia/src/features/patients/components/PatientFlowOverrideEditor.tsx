/**
 * PatientFlowOverrideEditor — Dialog for per-patient flow day overrides.
 *
 * Displays the merged day list (global + override) with source badges,
 * editability gating on past days, skip toggles, and add-day capability.
 * Only override-source days are sent to the PUT endpoint on save.
 *
 * Observability:
 * - Query key ['patient-flow-overrides', patientId] visible in React Query DevTools
 * - Network tab: GET/PUT /api/v2/patients/{id}/flow-overrides
 * - Save failures surfaced via toast and mutation error state
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
import { Badge } from '@/components/ui/badge'
import { Switch } from '@/components/ui/switch'
import { useToast } from '@/components/ui/use-toast'
import { Loader2, Plus } from 'lucide-react'
import { usePatientFlowOverrides } from '@/features/patients/hooks'
import type { MergedDayItem, OverrideDayInput } from '@/features/patients/hooks'

interface PatientFlowOverrideEditorProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  patientId: string
}

const MESSAGE_TYPE_LABELS: Record<string, string> = {
  question: 'Pergunta',
  motivation: 'Motivação',
  reminder: 'Lembrete',
}

export function PatientFlowOverrideEditor({
  open,
  onOpenChange,
  patientId,
}: PatientFlowOverrideEditorProps) {
  const { data, isLoading, saveOverrides, isSaving } = usePatientFlowOverrides(patientId)
  const { toast } = useToast()

  const [days, setDays] = useState<MergedDayItem[]>([])

  // Sync local state from fetched data whenever the dialog opens or data changes
  useEffect(() => {
    if (open && data?.days) {
      setDays(data.days)
    }
  }, [open, data])

  // ── Day mutation helpers ──────────────────────────────────────────

  const updateDay = useCallback(
    (index: number, field: keyof MergedDayItem, value: MergedDayItem[keyof MergedDayItem]) => {
      setDays((prev) =>
        prev.map((d, i) => {
          if (i !== index) return d
          // When a global day is modified, promote it to an override
          const updated = { ...d, [field]: value }
          if (d.source === 'global') {
            updated.source = 'override'
          }
          return updated
        })
      )
    },
    []
  )

  const addDay = useCallback(() => {
    setDays((prev) => {
      const maxDay = prev.reduce((max, d) => Math.max(max, d.day_number), 0)
      const newDay: MergedDayItem = {
        day_number: maxDay + 1,
        content: '',
        message_type: 'question',
        expects_response: false,
        skip: false,
        source: 'override',
        editable: true,
      }
      return [...prev, newDay]
    })
  }, [])

  // ── Save handler ──────────────────────────────────────────────────

  const handleSave = async () => {
    // Filter to only override days (user-modified or new)
    const overrideDays: OverrideDayInput[] = days
      .filter((d) => d.source === 'override')
      .map(({ day_number, content, message_type, expects_response, skip }) => ({
        day_number,
        content,
        message_type,
        expects_response,
        skip,
      }))

    try {
      await saveOverrides({ days: overrideDays })
      toast({
        title: 'Personalização salva',
        description: `${overrideDays.length} dia(s) personalizado(s) atualizado(s) com sucesso.`,
      })
      onOpenChange(false)
    } catch {
      toast({
        title: 'Erro ao salvar',
        description: 'Não foi possível salvar as personalizações. Tente novamente.',
        variant: 'destructive',
      })
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Personalizar Fluxo do Paciente</DialogTitle>
        </DialogHeader>

        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : (
          <ScrollArea className="flex-1 pr-4 -mr-4">
            <div className="space-y-6 py-2">
              {days.map((day, index) => (
                <div
                  key={`day-${day.day_number}`}
                  className={`rounded-lg border p-4 space-y-3 ${
                    !day.editable ? 'opacity-60' : ''
                  }`}
                >
                  {/* Header row: day number + source badges */}
                  <div className="flex items-center gap-2">
                    <Label className="text-sm font-semibold">
                      Dia {day.day_number}
                    </Label>
                    {day.source === 'global' ? (
                      <Badge variant="secondary">Global</Badge>
                    ) : (
                      <Badge variant="default">Personalizado</Badge>
                    )}
                    {day.skip && (
                      <Badge variant="destructive">Pulado</Badge>
                    )}
                  </div>

                  {/* Content textarea */}
                  <Textarea
                    value={day.content}
                    onChange={(e) => updateDay(index, 'content', e.target.value)}
                    disabled={!day.editable}
                    rows={3}
                    placeholder="Conteúdo da mensagem para este dia..."
                  />

                  {/* Controls row */}
                  <div className="flex items-center gap-4 flex-wrap">
                    {/* Type select */}
                    <div className="flex items-center gap-2">
                      <Label className="text-sm text-muted-foreground whitespace-nowrap">
                        Tipo:
                      </Label>
                      <Select
                        value={day.message_type}
                        onValueChange={(v) => updateDay(index, 'message_type', v)}
                        disabled={!day.editable}
                      >
                        <SelectTrigger className="w-[140px]">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {Object.entries(MESSAGE_TYPE_LABELS).map(
                            ([value, label]) => (
                              <SelectItem key={value} value={value}>
                                {label}
                              </SelectItem>
                            )
                          )}
                        </SelectContent>
                      </Select>
                    </div>

                    {/* Expects response checkbox */}
                    <div className="flex items-center gap-2">
                      <Checkbox
                        id={`override-expects-response-${index}`}
                        checked={day.expects_response}
                        onCheckedChange={(checked) =>
                          updateDay(index, 'expects_response', !!checked)
                        }
                        disabled={!day.editable}
                      />
                      <Label
                        htmlFor={`override-expects-response-${index}`}
                        className="text-sm text-muted-foreground cursor-pointer"
                      >
                        Espera resposta
                      </Label>
                    </div>

                    {/* Skip toggle */}
                    <div className="flex items-center gap-2">
                      <Switch
                        id={`override-skip-${index}`}
                        checked={day.skip}
                        onCheckedChange={(checked) =>
                          updateDay(index, 'skip', checked)
                        }
                        disabled={!day.editable}
                      />
                      <Label
                        htmlFor={`override-skip-${index}`}
                        className="text-sm text-muted-foreground cursor-pointer"
                      >
                        Pular dia
                      </Label>
                    </div>
                  </div>
                </div>
              ))}

              {days.length === 0 && !isLoading && (
                <p className="text-center text-sm text-muted-foreground py-8">
                  Nenhum dia configurado. Clique em &quot;Adicionar Dia&quot; para começar.
                </p>
              )}
            </div>
          </ScrollArea>
        )}

        <DialogFooter className="gap-2 sm:gap-0">
          <Button
            variant="outline"
            onClick={addDay}
            disabled={isLoading || isSaving}
          >
            <Plus className="h-4 w-4 mr-1" />
            Adicionar Dia
          </Button>
          <Button onClick={handleSave} disabled={isLoading || isSaving}>
            {isSaving && <Loader2 className="h-4 w-4 mr-1 animate-spin" />}
            Salvar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
