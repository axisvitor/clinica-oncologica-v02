import React from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '../../lib/api-client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
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
import { useToast } from '@/components/ui/use-toast'
import { LoadingSpinner } from '../ui/loading-spinner'

const createPatientSchema = z.object({
  name: z.string().min(2, 'Nome deve ter pelo menos 2 caracteres'),
  phone: z.string().min(10, 'Telefone deve ter pelo menos 10 dígitos'),
  email: z.string().email('Email inválido').optional().or(z.literal('')),
  birth_date: z.string().optional(),
  treatment_type: z.string().min(1, 'Selecione um tipo de tratamento'),
  treatment_start_date: z.string().optional(),
  notes: z.string().optional()
})

type CreatePatientFormData = z.infer<typeof createPatientSchema>

interface CreatePatientDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function CreatePatientDialog({ open, onOpenChange }: CreatePatientDialogProps) {
  const { toast } = useToast()
  const queryClient = useQueryClient()

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
    setValue,
    watch
  } = useForm<CreatePatientFormData>({
    resolver: zodResolver(createPatientSchema)
  })

  const createPatientMutation = useMutation({
    mutationFn: (data: CreatePatientFormData) => {
      // Build payload omitting undefined optional fields (exactOptionalPropertyTypes compliance)
      const cleanData: any = {
        name: data.name,
        phone: data.phone,
        treatment_type: data.treatment_type
      }

      // Only include optional fields if they have values
      if (data['email']) cleanData.email = data['email']
      if (data.birth_date) cleanData.birth_date = data.birth_date
      if (data.treatment_start_date) cleanData.treatment_start_date = data.treatment_start_date
      if (data.notes) cleanData.notes = data.notes

      return apiClient.patients.create(cleanData)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patients'] })
      toast({
        title: 'Paciente criado com sucesso',
        description: 'O novo paciente foi adicionado ao sistema.',
      })
      reset()
      onOpenChange(false)
    },
    onError: (error: any) => {
      toast({
        title: 'Erro ao criar paciente',
        description: error.data?.message || 'Ocorreu um erro inesperado.',
        variant: 'destructive'
      })
    }
  })

  const onSubmit = (data: CreatePatientFormData) => {
    createPatientMutation.mutate(data)
  }

  const handleClose = () => {
    reset()
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>Novo Paciente</DialogTitle>
          <DialogDescription>
            Adicione um novo paciente ao sistema de terapia hormonal.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="name">Nome completo *</Label>
              <Input
                id="name"
                placeholder="Nome do paciente"
                {...register('name')}
              />
              {errors.name && (
                <p className="text-sm text-red-600">{errors.name.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="phone">Telefone *</Label>
              <Input
                id="phone"
                placeholder="+55 11 99999-9999"
                {...register('phone')}
              />
              {errors.phone && (
                <p className="text-sm text-red-600">{errors.phone.message}</p>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="email@exemplo.com"
                {...register('email')}
              />
              {errors['email'] && (
                <p className="text-sm text-red-600">{errors['email'].message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="birth_date">Data de nascimento</Label>
              <Input
                id="birth_date"
                type="date"
                {...register('birth_date')}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="treatment_type">Tipo de tratamento *</Label>
              <Select onValueChange={(value) => setValue('treatment_type', value)}>
                <SelectTrigger>
                  <SelectValue placeholder="Selecione o tratamento" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="Terapia Hormonal Feminina">
                    Terapia Hormonal Feminina
                  </SelectItem>
                  <SelectItem value="Terapia Hormonal Masculina">
                    Terapia Hormonal Masculina
                  </SelectItem>
                  <SelectItem value="Reposição Hormonal">
                    Reposição Hormonal
                  </SelectItem>
                  <SelectItem value="Tratamento Personalizado">
                    Tratamento Personalizado
                  </SelectItem>
                </SelectContent>
              </Select>
              {errors.treatment_type && (
                <p className="text-sm text-red-600">{errors.treatment_type.message}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="treatment_start_date">Data de início do tratamento</Label>
              <Input
                id="treatment_start_date"
                type="date"
                {...register('treatment_start_date')}
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="notes">Observações</Label>
            <Textarea
              id="notes"
              placeholder="Observações sobre o paciente ou tratamento..."
              rows={3}
              {...register('notes')}
            />
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={handleClose}
              disabled={createPatientMutation.isPending}
            >
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={createPatientMutation.isPending}
            >
              {createPatientMutation.isPending ? (
                <>
                  <LoadingSpinner size="sm" className="mr-2" />
                  Criando...
                </>
              ) : (
                'Criar Paciente'
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
