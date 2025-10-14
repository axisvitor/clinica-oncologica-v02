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

const normalizePhoneNumber = (value: string | undefined) => {
  if (!value) return value
  const digits = value.replace(/\D/g, '')
  if (!digits) return value

  if (value.trim().startsWith('+')) {
    return `+${digits}`
  }

  if (digits.length === 11) {
    return `+55${digits}`
  }

  return `+${digits}`
}

const updatePatientSchema = z.object({
  name: z.string().min(2, 'Nome deve ter pelo menos 2 caracteres').optional(),
  phone: z.string().min(10, 'Telefone deve ter pelo menos 10 dígitos').optional()
    .transform(value => normalizePhoneNumber(value))
    .refine((value) => !value || /^\+[1-9]\d{9,14}$/.test(value), 'Telefone deve incluir código do país (ex: +5511999999999)'),
  email: z.string().email('Email inválido').optional().or(z.literal('')),
  birth_date: z.string().optional(),
  treatment_type: z.string().optional(),
  treatment_start_date: z.string().optional(),
  doctor_notes: z.string().optional()
})

type UpdatePatientFormData = z.infer<typeof updatePatientSchema>

interface Patient {
  id: string
  name: string
  phone: string
  email?: string
  birth_date?: string
  treatment_type: string
  treatment_start_date?: string
  doctor_notes?: string
  status: string
  current_day?: number
  created_at: string
  updated_at: string
}

interface EditPatientDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  patient: Patient | null
}

export function EditPatientDialog({ open, onOpenChange, patient }: EditPatientDialogProps) {
  const { toast } = useToast()
  const queryClient = useQueryClient()

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
    setValue,
    watch
  } = useForm<UpdatePatientFormData>({
    resolver: zodResolver(updatePatientSchema),
    defaultValues: patient ? {
      name: patient.name,
      phone: patient.phone,
      email: patient.email || '',
      birth_date: patient.birth_date || '',
      treatment_type: patient.treatment_type,
      treatment_start_date: patient.treatment_start_date || '',
      doctor_notes: patient.doctor_notes || ''
    } : {}
  })

  const updatePatientMutation = useMutation({
    mutationFn: (data: UpdatePatientFormData) => {
      if (!patient) throw new Error('No patient selected')
      
      // Clean up empty strings and undefined values
      const cleanData = Object.fromEntries(
        Object.entries(data).filter(([_, value]) => value !== '' && value !== undefined)
      )
      
      return apiClient.patients.update(patient.id, cleanData)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patients'] })
      queryClient.invalidateQueries({ queryKey: ['patient', patient?.id] })
      toast({
        title: 'Paciente atualizado com sucesso',
        description: 'As informações do paciente foram atualizadas.',
      })
      reset()
      onOpenChange(false)
    },
    onError: (error: any) => {
      toast({
        title: 'Erro ao atualizar paciente',
        description: error.data?.message || 'Ocorreu um erro inesperado.',
        variant: 'destructive'
      })
    }
  })

  const onSubmit = (data: UpdatePatientFormData) => {
    updatePatientMutation.mutate(data)
  }

  const handleClose = () => {
    reset()
    onOpenChange(false)
  }

  // Reset form when patient changes
  React.useEffect(() => {
    if (patient) {
      reset({
        name: patient.name,
        phone: patient.phone,
        email: patient.email || '',
        birth_date: patient.birth_date || '',
        treatment_type: patient.treatment_type,
        treatment_start_date: patient.treatment_start_date || '',
      doctor_notes: patient?.doctor_notes || ''
      })
    }
  }, [patient, reset])

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>Editar Paciente</DialogTitle>
          <DialogDescription>
            Atualize as informações do paciente {patient?.name}.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="name">Nome completo</Label>
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
              <Label htmlFor="phone">Telefone</Label>
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
              <Label htmlFor="treatment_type">Tipo de tratamento</Label>
              <Select
                value={watch('treatment_type') ?? ''}
                onValueChange={(value) => setValue('treatment_type', value)}
              >
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
            <Label htmlFor="doctor_notes">Observações</Label>
            <Textarea
              id="doctor_notes"
              placeholder="Observações sobre o paciente ou tratamento..."
              rows={3}
              {...register('doctor_notes')}
            />
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={handleClose}
              disabled={updatePatientMutation.isPending}
            >
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={updatePatientMutation.isPending}
            >
              {updatePatientMutation.isPending ? (
                <>
                  <LoadingSpinner size="sm" className="mr-2" />
                  Atualizando...
                </>
              ) : (
                'Atualizar Paciente'
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
