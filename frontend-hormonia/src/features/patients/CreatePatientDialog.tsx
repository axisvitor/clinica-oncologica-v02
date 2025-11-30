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
import { LoadingSpinner } from '@/components/ui/loading-spinner'
import { useAuth } from '@/app/providers/AuthContext'
import { getErrorMessage } from '@/lib/utils/type-guards'
import { normalizePhone } from '@/lib/utils/phone'
import { cpfRefinement, cleanCPF } from '@/lib/utils/cpf'

const createPatientSchema = z.object({
  name: z.string().min(2, 'Nome deve ter pelo menos 2 caracteres'),
  phone: z.string()
    .min(10, 'Telefone deve ter pelo menos 10 dígitos')
    .transform(normalizePhone)
    .refine((value) => /^\+[1-9]\d{9,14}$/.test(value), 'Telefone deve incluir código do país (ex: +5511999999999)'),
  email: z.string().email('Email inválido').optional().nullable(),
  birth_date: z.string().optional(),
  treatment_type: z.string().min(1, 'Selecione um tipo de tratamento'),
  treatment_start_date: z.string().optional(),
  doctor_notes: z.string().optional(),
  timezone: z.string().default('America/Sao_Paulo'),
  cpf: z.string()
    .optional()
    .refine(cpfRefinement, { message: 'CPF inválido' })
    .transform(val => val ? cleanCPF(val) : undefined),
  diagnosis: z.string().optional(),
  treatment_phase: z.string().optional()
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
      return rawList.filter((doctor: unknown): doctor is DoctorUser =>
        typeof doctor === 'object' && doctor !== null && 'id' in doctor && typeof doctor.id === 'string'
      )
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

      // STRICT ENFORCEMENT: If not admin, ALWAYS use current user ID, ignoring selection state
      const targetDoctorId = isAdminUser ? selectedDoctorId : userId

      if (!targetDoctorId) {
        throw new Error('Selecione o médico responsável antes de criar o paciente.')
      }

      // Build payload omitting undefined optional fields (exactOptionalPropertyTypes compliance)
      const cleanData: Partial<CreatePatientFormData> & { doctor_id: string } = {
        name: data.name,
        phone: data.phone,
        treatment_type: data.treatment_type,
        doctor_id: targetDoctorId,
        timezone: data.timezone,
        cpf: data.cpf,
        diagnosis: data.diagnosis,
        treatment_phase: data.treatment_phase
      }

      // Only include optional fields if they have values
      if (data['email']) cleanData.email = data['email']
      if (data.birth_date) cleanData.birth_date = data.birth_date
      if (data.treatment_start_date) cleanData.treatment_start_date = data.treatment_start_date
      if (data.doctor_notes) cleanData.doctor_notes = data.doctor_notes

      return apiClient.patients.create(cleanData as Parameters<typeof apiClient.patients.create>[0])
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['patients'] })
      toast({
        title: 'Paciente criado com sucesso',
        description: 'O novo paciente foi adicionado e o fluxo de onboarding foi iniciado via WhatsApp.',
      })
      reset()
      // Reset selection state safely
      if (isAdminUser) {
        setSelectedDoctorId('')
      }
      onOpenChange(false)
    },
    onError: (error: unknown) => {
      toast({
        title: 'Erro ao criar paciente',
        description: getErrorMessage(error) || 'Ocorreu um erro inesperado.',
        variant: 'destructive'
      })
    }
  })

  const onSubmit = (data: CreatePatientFormData) => {
    // Validation for admins
    if (isAdminUser && requiresDoctorSelection && !selectedDoctorId) {
      toast({
        title: 'Selecione o médico responsável',
        description: 'É necessário definir o médico responsável pelo paciente.',
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


          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="cpf">CPF</Label>
              <Input
                id="cpf"
                placeholder="000.000.000-00"
                {...register('cpf')}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="treatment_phase">Fase do Tratamento</Label>
              <Select onValueChange={(value) => setValue('treatment_phase', value)}>
                <SelectTrigger>
                  <SelectValue placeholder="Selecione a fase" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="initial">Inicial</SelectItem>
                  <SelectItem value="adjustment">Ajuste</SelectItem>
                  <SelectItem value="maintenance">Manutenção</SelectItem>
                  <SelectItem value="monitoring">Monitoramento</SelectItem>
                  <SelectItem value="followup">Acompanhamento</SelectItem>
                  <SelectItem value="completed">Concluído</SelectItem>
                </SelectContent>
              </Select>
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

          {/* Show current user as responsible doctor for non-admins */}
          {!isAdminUser && (
            <div className="space-y-2">
              <Label>Médico responsável</Label>
              <Input
                disabled
                value={user?.full_name || user?.email || 'Você'}
                className="bg-muted text-muted-foreground"
              />
              <p className="text-xs text-muted-foreground">
                Você será registrado como o médico responsável por este paciente.
              </p>
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

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="timezone">Fuso Horário</Label>
              <Select
                defaultValue="America/Sao_Paulo"
                onValueChange={(value) => setValue('timezone', value)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Selecione o fuso horário" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="America/Sao_Paulo">Brasília (GMT-3)</SelectItem>
                  <SelectItem value="America/Manaus">Manaus (GMT-4)</SelectItem>
                  <SelectItem value="America/Belem">Belém (GMT-3)</SelectItem>
                  <SelectItem value="America/Fortaleza">Fortaleza (GMT-3)</SelectItem>
                  <SelectItem value="America/Recife">Recife (GMT-3)</SelectItem>
                  <SelectItem value="America/Cuiaba">Cuiabá (GMT-4)</SelectItem>
                  <SelectItem value="America/Campo_Grande">Campo Grande (GMT-4)</SelectItem>
                  <SelectItem value="America/Porto_Velho">Porto Velho (GMT-4)</SelectItem>
                  <SelectItem value="America/Rio_Branco">Rio Branco (GMT-5)</SelectItem>
                  <SelectItem value="America/Noronha">Fernando de Noronha (GMT-2)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="diagnosis">Diagnóstico</Label>
            <Textarea
              id="diagnosis"
              placeholder="Diagnóstico médico..."
              rows={2}
              {...register('diagnosis')}
            />
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
      </DialogContent >
    </Dialog >
  )
}
