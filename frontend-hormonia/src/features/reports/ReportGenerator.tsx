import React, { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FileText, Calendar, User, Settings } from 'lucide-react'
import { apiClient } from '../../lib/api-client'
import { getErrorMessage } from '@/lib/type-guards'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Checkbox } from '@/components/ui/checkbox'
import { useToast } from '@/components/ui/use-toast'
import { LoadingSpinner } from '@/components/ui/loading-spinner'

const generateReportSchema = z.object({
  patient_id: z.string().min(1, 'Selecione um paciente'),
  type: z.string().min(1, 'Selecione um tipo de relatório'),
  start_date: z.string().optional(),
  end_date: z.string().optional(),
  include_messages: z.boolean().default(true),
  include_quizzes: z.boolean().default(true),
  include_alerts: z.boolean().default(false),
  include_timeline: z.boolean().default(true)
})

type GenerateReportFormData = z.infer<typeof generateReportSchema>

interface ReportGeneratorProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  preselectedPatientId?: string
}

export function ReportGenerator({ open, onOpenChange, preselectedPatientId }: ReportGeneratorProps) {
  const { toast } = useToast()
  const queryClient = useQueryClient()

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
    setValue,
    watch
  } = useForm<GenerateReportFormData>({
    resolver: zodResolver(generateReportSchema),
    defaultValues: {
      patient_id: preselectedPatientId || '',
      type: '',
      include_messages: true,
      include_quizzes: true,
      include_alerts: false,
      include_timeline: true
    }
  })

  const { data: patientsData } = useQuery({
    queryKey: ['patients', { size: 100 }],
    queryFn: () => apiClient.patients.list({ size: 100 })
  })

  const generateReportMutation = useMutation({
    mutationFn: (data: GenerateReportFormData) => {
      const config = {
        start_date: data.start_date,
        end_date: data.end_date,
        include_messages: data.include_messages,
        include_quizzes: data.include_quizzes,
        include_alerts: data.include_alerts,
        include_timeline: data.include_timeline
      }

      return apiClient.reports.generate(data.patient_id, data.type, config)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reports'] })
      toast({
        title: 'Relatório iniciado',
        description: 'A geração do relatório foi iniciada. Você será notificado quando estiver pronto.',
      })
      reset()
      onOpenChange(false)
    },
    onError: (error: unknown) => {
      toast({
        title: 'Erro ao gerar relatório',
        description: getErrorMessage(error) || 'Ocorreu um erro inesperado.',
        variant: 'destructive'
      })
    }
  })

  const onSubmit = (data: GenerateReportFormData) => {
    generateReportMutation.mutate(data)
  }

  const handleClose = () => {
    reset()
    onOpenChange(false)
  }

  const reportTypes = [
    { value: 'monthly', label: 'Relatório Mensal', description: 'Resumo das atividades do mês' },
    { value: 'quarterly', label: 'Relatório Trimestral', description: 'Análise trimestral do progresso' },
    { value: 'treatment_progress', label: 'Progresso do Tratamento', description: 'Evolução do tratamento hormonal' },
    { value: 'engagement', label: 'Relatório de Engajamento', description: 'Análise de participação e respostas' },
    { value: 'custom', label: 'Relatório Personalizado', description: 'Relatório com configurações específicas' }
  ]

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>Gerar Relatório</DialogTitle>
          <DialogDescription>
            Configure os parâmetros para gerar um relatório detalhado
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
          {/* Patient Selection */}
          <div className="space-y-2">
            <Label htmlFor="patient_id">Paciente *</Label>
            <Select
              value={watch('patient_id')}
              onValueChange={(value) => setValue('patient_id', value)}
            >
              <SelectTrigger>
                <SelectValue placeholder="Selecione um paciente" />
              </SelectTrigger>
              <SelectContent>
                {(patientsData?.items || [])?.map((patient: any) => (
                  <SelectItem key={patient.id} value={patient.id}>
                    <div className="flex items-center space-x-2">
                      <User className="h-4 w-4" />
                      <span>{patient.name}</span>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {errors.patient_id && (
              <p className="text-sm text-red-600">{errors.patient_id.message}</p>
            )}
          </div>

          {/* Report Type */}
          <div className="space-y-2">
            <Label htmlFor="type">Tipo de Relatório *</Label>
            <Select
              value={watch('type')}
              onValueChange={(value) => setValue('type', value)}
            >
              <SelectTrigger>
                <SelectValue placeholder="Selecione o tipo de relatório" />
              </SelectTrigger>
              <SelectContent>
                {reportTypes.map((type) => (
                  <SelectItem key={type.value} value={type.value}>
                    <div>
                      <div className="font-medium">{type.label}</div>
                      <div className="text-sm text-gray-500">{type.description}</div>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {errors.type && (
              <p className="text-sm text-red-600">{errors.type.message}</p>
            )}
          </div>

          {/* Date Range */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="start_date">Data de Início</Label>
              <Input
                id="start_date"
                type="date"
                {...register('start_date')}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="end_date">Data de Fim</Label>
              <Input
                id="end_date"
                type="date"
                {...register('end_date')}
              />
            </div>
          </div>

          {/* Content Options */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Conteúdo do Relatório</CardTitle>
              <CardDescription>
                Selecione quais informações incluir no relatório
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="include_messages"
                  checked={watch('include_messages')}
                  onCheckedChange={(checked) => setValue('include_messages', !!checked)}
                />
                <Label htmlFor="include_messages" className="flex items-center space-x-2">
                  <FileText className="h-4 w-4" />
                  <span>Histórico de Mensagens</span>
                </Label>
              </div>

              <div className="flex items-center space-x-2">
                <Checkbox
                  id="include_quizzes"
                  checked={watch('include_quizzes')}
                  onCheckedChange={(checked) => setValue('include_quizzes', !!checked)}
                />
                <Label htmlFor="include_quizzes" className="flex items-center space-x-2">
                  <Settings className="h-4 w-4" />
                  <span>Questionários e Respostas</span>
                </Label>
              </div>

              <div className="flex items-center space-x-2">
                <Checkbox
                  id="include_alerts"
                  checked={watch('include_alerts')}
                  onCheckedChange={(checked) => setValue('include_alerts', !!checked)}
                />
                <Label htmlFor="include_alerts" className="flex items-center space-x-2">
                  <Calendar className="h-4 w-4" />
                  <span>Alertas e Notificações</span>
                </Label>
              </div>

              <div className="flex items-center space-x-2">
                <Checkbox
                  id="include_timeline"
                  checked={watch('include_timeline')}
                  onCheckedChange={(checked) => setValue('include_timeline', !!checked)}
                />
                <Label htmlFor="include_timeline" className="flex items-center space-x-2">
                  <User className="h-4 w-4" />
                  <span>Timeline de Eventos</span>
                </Label>
              </div>
            </CardContent>
          </Card>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={handleClose}
              disabled={generateReportMutation.isPending}
            >
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={generateReportMutation.isPending}
            >
              {generateReportMutation.isPending ? (
                <>
                  <LoadingSpinner size="sm" className="mr-2" />
                  Gerando...
                </>
              ) : (
                <>
                  <FileText className="mr-2 h-4 w-4" />
                  Gerar Relatório
                </>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
