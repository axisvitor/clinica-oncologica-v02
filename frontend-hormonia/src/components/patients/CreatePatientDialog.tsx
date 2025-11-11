import React, { useEffect, useMemo, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
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
import { useAuth } from '@/contexts/AuthContext'

const normalizePhoneNumber = (value: string) => {
  if (!value) return value
  const digits = value.replace(/\D/g, '')
  if (!digits) return value

  if (value.trim().startsWith('+')) {
    return `+${digits}`
  }

  // Default to Brazil country code if none provided
  if (digits.length === 11) {
    return `+55${digits}`
  }

  return `+${digits}`
}

const createPatientSchema = z.object({
  name: z.string().min(2, 'Nome deve ter pelo menos 2 caracteres'),
  phone: z.string()
    .min(10, 'Telefone deve ter pelo menos 10 dígitos')
    .transform(normalizePhoneNumber)
    .refine((value) => /^\+[1-9]\d{9,14}$/.test(value), 'Telefone deve incluir código do país (ex: +5511999999999)'),
  email: z.string().email('Email inválido').optional().or(z.literal('')),
  birth_date: z.string().optional(),
  treatment_type: z.string().min(1, 'Selecione um tipo de tratamento'),
  treatment_start_date: z.string().optional(),
  doctor_notes: z.string().optional()
})

type CreatePatientFormData = z.infer<typeof createPatientSchema>

interface CreatePatientDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

interface DoctorUser {
  id: string
  full_name?: string
  name?: string
  email?: string
}

export function CreatePatientDialog({ open, onOpenChange }: CreatePatientDialogProps) {
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const normalizedRole = (user?.role ?? '').toLowerCase()
  const isAdminUser = normalizedRole === 'admin' || normalizedRole === 'super_admin'
  const userId = user?.id ?? ''
  const [selectedDoctorId, setSelectedDoctorId] = useState<string>(isAdminUser ? '' : userId)

  const { data: doctorList = [], isLoading: isLoadingDoctors } = useQuery<DoctorUser[]>({
    queryKey: ['admin-doctors', isAdminUser],
    queryFn: async () => {
      const response = await apiClient.adminUsers.list({ size: 100, role: 'doctor' })
      const rawList = Array.isArray(response)
        ? response
        : Array.isArray((response as any)?.items)
          ? (response as any).items
          : Array.isArray((response as any)?.data)
            ? (response as any).data
            : []
      return rawList.filter((doctor: any): doctor is DoctorUser => typeof doctor?.id === 'string')
    },
    enabled: isAdminUser
  })

  const doctorOptions = useMemo(
    () =>
      doctorList.map((doctor) => ({
        id: doctor.id,
        label: doctor.full_name || doctor.name || doctor.email || 'M�dico'
      })),
    [doctorList]
  )

  const hasDoctorOptions = doctorOptions.length > 0
  const requiresDoctorSelection = isAdminUser && hasDoctorOptions

  useEffect(() => {
    if (isAdminUser && hasDoctorOptions) {
      setSelectedDoctorId('')
    } else {
      setSelectedDoctorId(userId)
    }
  }, [isAdminUser, hasDoctorOptions, userId])

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
    setValue
  } = useForm<CreatePatientFormData>({
    resolver: zodResolver(createPatientSchema)
  })

  const createPatientMutation = useMutation({
    mutationFn: (data: CreatePatientFormData) => {
      if (!userId) {
        throw new Error('Não foi possível identificar o médico autenticado. Refaça o login e tente novamente.')
      }
      const targetDoctorId = requiresDoctorSelection ? selectedDoctorId : userId
      if (!targetDoctorId) {
        throw new Error('Selecione o medico responsavel antes de criar o paciente.')
      }
      // Build payload omitting undefined optional fields (exactOptionalPropertyTypes compliance)
      const cleanData: any = {
        name: data.name,
        phone: data.phone,
        treatment_type: data.treatment_type,
        doctor_id: targetDoctorId
      }

      // Only include optional fields if they have values
      if (data['email']) cleanData.email = data['email']
      if (data.birth_date) cleanData.birth_date = data.birth_date
      if (data.treatment_start_date) cleanData.treatment_start_date = data.treatment_start_date
      if (data.doctor_notes) cleanData.doctor_notes = data.doctor_notes

      return apiClient.patients.create(cleanData)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patients'] })
      toast({
        title: 'Paciente criado com sucesso',
        description: 'O novo paciente foi adicionado ao sistema.',
      })
      reset()
      setSelectedDoctorId(isAdminUser && hasDoctorOptions ? '' : userId)
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
    if (requiresDoctorSelection && !selectedDoctorId) {
      toast({
        title: 'Selecione o m�dico respons�vel',
        description: '� necess�rio definir o m�dico respons�vel pelo paciente.',
        variant: 'destructive'
      })
      return
    }
    createPatientMutation.mutate(data)
  }

  const handleClose = () => {
    reset()
    setSelectedDoctorId(isAdminUser && hasDoctorOptions ? '' : userId)
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

          {isAdminUser && hasDoctorOptions && (
            <div className="space-y-2">
              <Label htmlFor="doctor_id">Médico responsável *</Label>
              <Select
                value={selectedDoctorId}
                onValueChange={setSelectedDoctorId}
                disabled={isLoadingDoctors}
              >
                <SelectTrigger>
                  <SelectValue placeholder={isLoadingDoctors ? 'Carregando médicos...' : 'Selecione o médico responsável'} />
                </SelectTrigger>
                <SelectContent>
                  {doctorOptions.map((doctor) => (
                    <SelectItem key={doctor.id} value={doctor.id}>
                      {doctor.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {requiresDoctorSelection && !selectedDoctorId && !isLoadingDoctors && (
                <p className="text-sm text-red-600">Selecione o médico responsável.</p>
              )}
            </div>
          )}

          {isAdminUser && !hasDoctorOptions && (
            <div className="space-y-2">
              <Label>Médico responsável</Label>
              <div className="rounded-md border border-dashed border-muted-foreground/40 px-3 py-2 text-sm text-muted-foreground">
                Nenhum médico foi cadastrado ainda. O paciente será atribuído ao administrador atual.
              </div>
            </div>
          )}

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
