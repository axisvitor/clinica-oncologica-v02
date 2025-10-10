import React, { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card'
import { Button } from '../ui/button'
import { Input } from '../ui/input'
import { Label } from '../ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select'
import { Checkbox } from '../ui/checkbox'
import { Badge } from '../ui/badge'
import {
  User,
  Mail,
  Phone,
  Shield,
  Key,
  UserPlus,
  CheckCircle,
  AlertTriangle,
  Eye,
  EyeOff
} from 'lucide-react'
import { Alert, AlertDescription } from '../ui/alert'
import { LoadingSpinner } from './LoadingSpinner'
import { toast } from '../../hooks/use-toast'
import { createLogger } from '../../lib/logger'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'

const logger = createLogger('InitialUserSetup')

const userSetupSchema = z.object({
  name: z.string().min(2, 'Nome deve ter pelo menos 2 caracteres'),
  email: z.string().email('Email inválido'),
  phone: z.string().min(10, 'Telefone deve ter pelo menos 10 dígitos'),
  crm: z.string().min(4, 'CRM deve ter pelo menos 4 caracteres'),
  specialization: z.string().min(1, 'Especialização é obrigatória'),
  password: z.string().min(8, 'Senha deve ter pelo menos 8 caracteres'),
  confirmPassword: z.string(),
  role: z.enum(['admin', 'medico', 'enfermeiro']),
  acceptTerms: z.boolean().refine(val => val === true, 'Você deve aceitar os termos'),
  enableNotifications: z.boolean().optional()
}).refine(data => data.password === data.confirmPassword, {
  message: 'Senhas não coincidem',
  path: ['confirmPassword']
})

type UserSetupForm = z.infer<typeof userSetupSchema>

interface InitialUserSetupProps {
  onComplete: () => void
  onError: (error: string) => void
}

export function InitialUserSetup({ onComplete, onError }: InitialUserSetupProps) {
  const [isCreating, setIsCreating] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)
  const [step, setStep] = useState(1)

  const {
    register,
    handleSubmit,
    formState: { errors, isValid },
    watch,
    setValue,
    trigger
  } = useForm<UserSetupForm>({
    resolver: zodResolver(userSetupSchema),
    mode: 'onChange',
    defaultValues: {
      role: 'admin',
      acceptTerms: false,
      enableNotifications: true
    }
  })

  const watchedValues = watch()

  const specializations = [
    'Oncologia Clínica',
    'Oncologia Cirúrgica',
    'Radio-oncologia',
    'Hematologia',
    'Oncologia Pediátrica',
    'Ginecologia Oncológica',
    'Mastologia',
    'Urologia Oncológica',
    'Administração',
    'Outra'
  ]

  const roles = [
    { value: 'admin', label: 'Administrador', description: 'Acesso completo ao sistema' },
    { value: 'medico', label: 'Médico', description: 'Acesso a pacientes e tratamentos' },
    { value: 'enfermeiro', label: 'Enfermeiro', description: 'Acesso limitado a cuidados' }
  ]

  const handleCreateUser = async (data: UserSetupForm) => {
    setIsCreating(true)
    logger.log('Creating initial admin user:', data.email)

    try {
      // Simulate user creation API call
      await new Promise(resolve => setTimeout(resolve, 2000))

      // In real implementation, call the API to create user
      const response = await fetch('/api/auth/setup-admin', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          name: data.name,
          email: data.email,
          phone: data.phone,
          crm: data.crm,
          specialization: data.specialization,
          password: data.password,
          role: data.role,
          enableNotifications: data.enableNotifications
        })
      })

      if (!response.ok) {
        throw new Error('Falha ao criar usuário')
      }

      toast({
        title: 'Usuário Criado com Sucesso',
        description: `Administrador ${data.name} foi criado e pode fazer login no sistema.`,
      })

      logger.log('Initial admin user created successfully')
      onComplete()

    } catch (error) {
      logger.error('Failed to create initial user:', error)
      onError('Falha ao criar usuário inicial: ' + (error as Error).message)
    } finally {
      setIsCreating(false)
    }
  }

  const handleNextStep = async () => {
    const fieldsToValidate = step === 1
      ? ['name', 'email', 'phone']
      : ['crm', 'specialization', 'role']

    const isStepValid = await trigger(fieldsToValidate as any)
    if (isStepValid) {
      setStep(step + 1)
    }
  }

  const handlePreviousStep = () => {
    setStep(step - 1)
  }

  const getPasswordStrength = (password: string) => {
    let strength = 0
    if (password.length >= 8) strength++
    if (/[A-Z]/.test(password)) strength++
    if (/[a-z]/.test(password)) strength++
    if (/\d/.test(password)) strength++
    if (/[^A-Za-z\d]/.test(password)) strength++

    if (strength < 2) return { level: 'weak', color: 'red', text: 'Fraca' }
    if (strength < 4) return { level: 'medium', color: 'yellow', text: 'Média' }
    return { level: 'strong', color: 'green', text: 'Forte' }
  }

  const passwordStrength = watchedValues.password ? getPasswordStrength(watchedValues.password) : null

  return (
    <div className="space-y-6">
      {/* Progress Steps */}
      <div className="flex items-center justify-center space-x-4 mb-8">
        {[1, 2, 3].map((stepNumber) => (
          <div key={stepNumber} className="flex items-center">
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                stepNumber < step
                  ? 'bg-green-500 text-white'
                  : stepNumber === step
                  ? 'bg-blue-500 text-white'
                  : 'bg-gray-300 text-gray-600'
              }`}
            >
              {stepNumber < step ? <CheckCircle className="w-4 h-4" /> : stepNumber}
            </div>
            {stepNumber < 3 && (
              <div
                className={`w-16 h-1 mx-2 ${
                  stepNumber < step ? 'bg-green-500' : 'bg-gray-300'
                }`}
              />
            )}
          </div>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <UserPlus className="w-5 h-5" />
            <span>Criar Usuário Administrador</span>
          </CardTitle>
          <CardDescription>
            Configure o primeiro usuário administrador do sistema
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(handleCreateUser)} className="space-y-6">
            {/* Step 1: Personal Information */}
            {step === 1 && (
              <div className="space-y-4">
                <h3 className="text-lg font-semibold flex items-center space-x-2">
                  <User className="w-5 h-5" />
                  <span>Informações Pessoais</span>
                </h3>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="name">Nome Completo *</Label>
                    <Input
                      id="name"
                      {...register('name')}
                      placeholder="Dr. João Silva"
                      className={errors.name ? 'border-red-500' : ''}
                    />
                    {errors.name && (
                      <p className="text-sm text-red-600">{errors.name.message}</p>
                    )}
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="email">Email *</Label>
                    <Input
                      id="email"
                      type="email"
                      {...register('email')}
                      placeholder="joao@clinica.com"
                      className={errors.email ? 'border-red-500' : ''}
                    />
                    {errors.email && (
                      <p className="text-sm text-red-600">{errors.email.message}</p>
                    )}
                  </div>

                  <div className="space-y-2 md:col-span-2">
                    <Label htmlFor="phone">Telefone *</Label>
                    <Input
                      id="phone"
                      {...register('phone')}
                      placeholder="(11) 99999-9999"
                      className={errors.phone ? 'border-red-500' : ''}
                    />
                    {errors.phone && (
                      <p className="text-sm text-red-600">{errors.phone.message}</p>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Step 2: Professional Information */}
            {step === 2 && (
              <div className="space-y-4">
                <h3 className="text-lg font-semibold flex items-center space-x-2">
                  <Shield className="w-5 h-5" />
                  <span>Informações Profissionais</span>
                </h3>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="crm">CRM *</Label>
                    <Input
                      id="crm"
                      {...register('crm')}
                      placeholder="CRM/SP 123456"
                      className={errors.crm ? 'border-red-500' : ''}
                    />
                    {errors.crm && (
                      <p className="text-sm text-red-600">{errors.crm.message}</p>
                    )}
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="specialization">Especialização *</Label>
                    <Select
                      value={watchedValues.specialization}
                      onValueChange={(value) => setValue('specialization', value)}
                    >
                      <SelectTrigger className={errors.specialization ? 'border-red-500' : ''}>
                        <SelectValue placeholder="Selecione a especialização" />
                      </SelectTrigger>
                      <SelectContent>
                        {specializations.map((spec) => (
                          <SelectItem key={spec} value={spec}>
                            {spec}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {errors.specialization && (
                      <p className="text-sm text-red-600">{errors.specialization.message}</p>
                    )}
                  </div>

                  <div className="space-y-2 md:col-span-2">
                    <Label>Nível de Acesso *</Label>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                      {roles.map((role) => (
                        <Card
                          key={role.value}
                          className={`cursor-pointer transition-colors ${
                            watchedValues.role === role.value
                              ? 'border-blue-500 bg-blue-50'
                              : 'hover:border-gray-400'
                          }`}
                          onClick={() => setValue('role', role.value as any)}
                        >
                          <CardContent className="pt-4">
                            <div className="flex items-center space-x-2 mb-2">
                              <input
                                type="radio"
                                {...register('role')}
                                value={role.value}
                                className="sr-only"
                              />
                              <Badge variant={watchedValues.role === role.value ? 'default' : 'outline'}>
                                {role.label}
                              </Badge>
                            </div>
                            <p className="text-xs text-gray-600">{role.description}</p>
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                    {errors.role && (
                      <p className="text-sm text-red-600">{errors.role.message}</p>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Step 3: Security */}
            {step === 3 && (
              <div className="space-y-4">
                <h3 className="text-lg font-semibold flex items-center space-x-2">
                  <Key className="w-5 h-5" />
                  <span>Configurações de Segurança</span>
                </h3>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="password">Senha *</Label>
                    <div className="relative">
                      <Input
                        id="password"
                        type={showPassword ? 'text' : 'password'}
                        {...register('password')}
                        placeholder="Digite uma senha segura"
                        className={errors.password ? 'border-red-500 pr-10' : 'pr-10'}
                      />
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="absolute right-0 top-0 h-full px-3"
                        onClick={() => setShowPassword(!showPassword)}
                      >
                        {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </Button>
                    </div>
                    {watchedValues.password && passwordStrength && (
                      <div className="flex items-center space-x-2 text-sm">
                        <div
                          className={`w-3 h-3 rounded-full bg-${passwordStrength.color}-500`}
                        />
                        <span className={`text-${passwordStrength.color}-600`}>
                          Força da senha: {passwordStrength.text}
                        </span>
                      </div>
                    )}
                    {errors.password && (
                      <p className="text-sm text-red-600">{errors.password.message}</p>
                    )}
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="confirmPassword">Confirmar Senha *</Label>
                    <div className="relative">
                      <Input
                        id="confirmPassword"
                        type={showConfirmPassword ? 'text' : 'password'}
                        {...register('confirmPassword')}
                        placeholder="Confirme sua senha"
                        className={errors.confirmPassword ? 'border-red-500 pr-10' : 'pr-10'}
                      />
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="absolute right-0 top-0 h-full px-3"
                        onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                      >
                        {showConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </Button>
                    </div>
                    {errors.confirmPassword && (
                      <p className="text-sm text-red-600">{errors.confirmPassword.message}</p>
                    )}
                  </div>
                </div>

                <div className="space-y-4 pt-4">
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id="enableNotifications"
                      checked={watchedValues.enableNotifications ?? false}
                      onCheckedChange={(checked) => setValue('enableNotifications', checked === true)}
                    />
                    <Label htmlFor="enableNotifications" className="text-sm">
                      Habilitar notificações por email e WhatsApp
                    </Label>
                  </div>

                  <div className="flex items-start space-x-2">
                    <Checkbox
                      id="acceptTerms"
                      checked={watchedValues.acceptTerms ?? false}
                      onCheckedChange={(checked) => setValue('acceptTerms', checked === true)}
                      className={errors.acceptTerms ? 'border-red-500' : ''}
                    />
                    <Label htmlFor="acceptTerms" className="text-sm leading-relaxed">
                      Aceito os <a href="#" className="text-blue-600 hover:underline">termos de uso</a> e
                      confirmo que tenho autorização para criar este usuário administrador *
                    </Label>
                  </div>
                  {errors.acceptTerms && (
                    <p className="text-sm text-red-600 ml-6">{errors.acceptTerms.message}</p>
                  )}
                </div>

                <Alert className="bg-blue-50 border-blue-200">
                  <AlertTriangle className="h-4 w-4 text-blue-600" />
                  <AlertDescription className="text-blue-800">
                    <strong>Importante:</strong> Este será o primeiro usuário administrador do sistema.
                    Guarde as credenciais em local seguro e certifique-se de que apenas pessoas
                    autorizadas tenham acesso.
                  </AlertDescription>
                </Alert>
              </div>
            )}

            {/* Navigation Buttons */}
            <div className="flex items-center justify-between pt-6">
              <Button
                type="button"
                variant="outline"
                onClick={handlePreviousStep}
                disabled={step === 1}
              >
                Anterior
              </Button>

              <span className="text-sm text-gray-500">
                Etapa {step} de 3
              </span>

              {step < 3 ? (
                <Button
                  type="button"
                  onClick={handleNextStep}
                >
                  Próximo
                </Button>
              ) : (
                <Button
                  type="submit"
                  disabled={!isValid || isCreating}
                  className="min-w-[120px]"
                >
                  {isCreating ? (
                    <LoadingSpinner size="sm" text="Criando..." />
                  ) : (
                    <>
                      <UserPlus className="w-4 h-4 mr-2" />
                      Criar Usuário
                    </>
                  )}
                </Button>
              )}
            </div>
          </form>
        </CardContent>
      </Card>

      {isCreating && (
        <div className="text-center py-8">
          <LoadingSpinner
            size="lg"
            text="Criando usuário administrador..."
            showProgress
            progress={70}
          />
        </div>
      )}
    </div>
  )
}