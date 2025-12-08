import React, { useState, useCallback } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Eye, EyeOff, Shield, AlertCircle, CheckCircle, Clock } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Progress } from '@/components/ui/progress'
import { Checkbox } from '@/components/ui/checkbox'
import {
  AdminLoginCredentials,
  PasswordStrength,
  AdminLoginResponse,
  AdminAuthError
} from '@/types/admin'
import { createLogger } from '@/lib/logger'

const logger = createLogger('AdminLoginForm')

// Password strength validation
const calculatePasswordStrength = (password: string): PasswordStrength => {
  const score = (() => {
    if (password.length < 6) return 0

    let strength = 0

    // Length checks
    if (password.length >= 8) strength += 1
    if (password.length >= 12) strength += 1

    // Character type checks
    if (/[a-z]/.test(password)) strength += 1
    if (/[A-Z]/.test(password)) strength += 1
    if (/[0-9]/.test(password)) strength += 1
    if (/[^A-Za-z0-9]/.test(password)) strength += 1

    // Bonus for very long passwords
    if (password.length >= 16) strength += 1

    return Math.min(4, Math.max(0, strength - 1))
  })() as 0 | 1 | 2 | 3 | 4

  const feedback: string[] = []
  const suggestions: string[] = []

  if (password.length < 8) {
    feedback.push('Senha muito curta')
    suggestions.push('Use pelo menos 8 caracteres')
  }

  if (!/[a-z]/.test(password)) {
    feedback.push('Faltam letras minúsculas')
    suggestions.push('Adicione letras minúsculas')
  }

  if (!/[A-Z]/.test(password)) {
    feedback.push('Faltam letras maiúsculas')
    suggestions.push('Adicione letras maiúsculas')
  }

  if (!/[0-9]/.test(password)) {
    feedback.push('Faltam números')
    suggestions.push('Adicione números')
  }

  if (!/[^A-Za-z0-9]/.test(password)) {
    feedback.push('Faltam caracteres especiais')
    suggestions.push('Adicione caracteres especiais (!@#$%^&*)')
  }

  const isValid = score >= 3 && password.length >= 8

  return { score, feedback, suggestions, isValid }
}

// Validation schema
const adminLoginSchema = z.object({
  email: z
    .string()
    .min(1, 'Email é obrigatório')
    .email('Formato de email inválido'),
  password: z
    .string()
    .min(1, 'Senha é obrigatória')
    .min(8, 'Senha deve ter pelo menos 8 caracteres'),
  twoFactorCode: z
    .string()
    .optional()
    .refine((code) => !code || /^\d{6}$/.test(code), {
      message: 'Código 2FA deve ter 6 dígitos'
    }),
  rememberMe: z.boolean().optional()
})

type AdminLoginFormData = z.infer<typeof adminLoginSchema>

interface AdminLoginFormProps {
  onLogin: (credentials: AdminLoginCredentials) => Promise<AdminLoginResponse>
  onForgotPassword?: (email: string) => void
  isLoading?: boolean
  requiresTwoFactor?: boolean
  lockoutTime?: number
  maxAttempts?: number
  currentAttempts?: number
}

export const AdminLoginForm: React.FC<AdminLoginFormProps> = ({
  onLogin,
  onForgotPassword,
  isLoading = false,
  requiresTwoFactor = false,
  lockoutTime = 0,
  maxAttempts = 5,
  currentAttempts = 0
}) => {
  const [showPassword, setShowPassword] = useState(false)
  const [passwordStrength, setPasswordStrength] = useState<PasswordStrength | null>(null)
  const [loginError, setLoginError] = useState<string | null>(null)
  const [isLocked, setIsLocked] = useState(lockoutTime > 0)
  const [timeRemaining, setTimeRemaining] = useState(lockoutTime)

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
    setValue,
    clearErrors
  } = useForm<AdminLoginFormData>({
    resolver: zodResolver(adminLoginSchema),
    defaultValues: {
      email: '',
      password: '',
      twoFactorCode: '',
      rememberMe: false
    }
  })

  const watchedPassword = watch('password')
  const watchedEmail = watch('email')

  // Update password strength when password changes
  React.useEffect(() => {
    if (watchedPassword) {
      setPasswordStrength(calculatePasswordStrength(watchedPassword))
    } else {
      setPasswordStrength(null)
    }
  }, [watchedPassword])

  // Lockout timer
  React.useEffect(() => {
    if (timeRemaining > 0) {
      const timer = setTimeout(() => {
        setTimeRemaining(time => {
          const newTime = time - 1
          if (newTime <= 0) {
            setIsLocked(false)
            return 0
          }
          return newTime
        })
      }, 1000)

      return () => clearTimeout(timer)
    }
    // Return undefined when timeRemaining <= 0
    return undefined
  }, [timeRemaining])

  const formatLockoutTime = (seconds: number): string => {
    const minutes = Math.floor(seconds / 60)
    const remainingSeconds = seconds % 60
    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`
  }

  const getPasswordStrengthColor = (score: number): string => {
    switch (score) {
      case 0:
      case 1:
        return 'bg-red-500'
      case 2:
        return 'bg-yellow-500'
      case 3:
        return 'bg-blue-500'
      case 4:
        return 'bg-green-500'
      default:
        return 'bg-gray-300'
    }
  }

  const getPasswordStrengthText = (score: number): string => {
    switch (score) {
      case 0:
        return 'Muito Fraca'
      case 1:
        return 'Fraca'
      case 2:
        return 'Razoável'
      case 3:
        return 'Boa'
      case 4:
        return 'Forte'
      default:
        return 'Desconhecida'
    }
  }

  const onSubmit = useCallback(async (data: AdminLoginFormData) => {
    if (isLocked) return

    try {
      setLoginError(null)
      clearErrors()

      const response = await onLogin({
        email: data['email'],
        password: data['password'],
        ...(data.twoFactorCode ? { twoFactorCode: data.twoFactorCode } : {}),
        ...(data.rememberMe !== undefined ? { rememberMe: data.rememberMe } : {})
      })

      if (!response.success) {
        throw new AdminAuthError(response.error || 'Falha no login')
      }
    } catch (error) {
      logger.error('Login error', { error })

      if (error instanceof AdminAuthError) {
        setLoginError(error.message)

        // Handle account lockout
        if (error.code === 'ACCOUNT_LOCKED') {
          setIsLocked(true)
          setTimeRemaining(lockoutTime)
        }
      } else {
        setLoginError('Ocorreu um erro inesperado. Tente novamente.')
      }
    }
  }, [onLogin, isLocked, clearErrors, lockoutTime])

  const handleForgotPassword = useCallback(() => {
    if (onForgotPassword && watchedEmail) {
      onForgotPassword(watchedEmail)
    }
  }, [onForgotPassword, watchedEmail])

  const remainingAttempts = maxAttempts - currentAttempts

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-1">
          <div className="flex items-center justify-center mb-4">
            <Shield className="h-12 w-12 text-blue-600" />
          </div>
          <CardTitle className="text-2xl text-center">Portal Administrativo</CardTitle>
          <CardDescription className="text-center">
            Entre para acessar o painel administrativo
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-4">
          {/* Account Lockout Warning */}
          {isLocked && (
            <Alert className="border-red-200 bg-red-50">
              <Clock className="h-4 w-4 text-red-600" />
              <AlertDescription className="text-red-800">
                Conta temporariamente bloqueada devido a múltiplas tentativas de login falhadas.
                <br />
                Tente novamente em: {formatLockoutTime(timeRemaining)}
              </AlertDescription>
            </Alert>
          )}

          {/* Login Error */}
          {loginError && (
            <Alert className="border-red-200 bg-red-50">
              <AlertCircle className="h-4 w-4 text-red-600" />
              <AlertDescription className="text-red-800">
                {loginError}
              </AlertDescription>
            </Alert>
          )}

          {/* Remaining Attempts Warning */}
          {!isLocked && remainingAttempts <= 2 && remainingAttempts > 0 && (
            <Alert className="border-yellow-200 bg-yellow-50">
              <AlertCircle className="h-4 w-4 text-yellow-600" />
              <AlertDescription className="text-yellow-800">
                Aviso: {remainingAttempts} {remainingAttempts !== 1 ? 'tentativas de login restantes' : 'tentativa de login restante'}
              </AlertDescription>
            </Alert>
          )}

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            {/* Email Field */}
            <div className="space-y-2">
              <Label htmlFor="email">Endereço de Email</Label>
              <Input
                id="email"
                type="email"
                autoComplete="email"
                disabled={isLocked || isLoading || isSubmitting}
                {...register('email')}
                className={errors['email'] ? 'border-red-500' : ''}
              />
              {errors['email'] && (
                <p className="text-sm text-red-600">{errors['email']?.['message']}</p>
              )}
            </div>

            {/* Password Field */}
            <div className="space-y-2">
              <Label htmlFor="password">Senha</Label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  disabled={isLocked || isLoading || isSubmitting}
                  {...register('password')}
                  className={errors['password'] ? 'border-red-500 pr-10' : 'pr-10'}
                />
                <button
                  type="button"
                  className="absolute inset-y-0 right-0 pr-3 flex items-center"
                  onClick={() => setShowPassword(!showPassword)}
                  disabled={isLocked || isLoading || isSubmitting}
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4 text-gray-400" />
                  ) : (
                    <Eye className="h-4 w-4 text-gray-400" />
                  )}
                </button>
              </div>
              {errors['password'] && (
                <p className="text-sm text-red-600">{errors['password']?.['message']}</p>
              )}

              {/* Password Strength Indicator */}
              {passwordStrength && watchedPassword && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-600">Força da Senha:</span>
                    <span className={`text-xs font-medium ${passwordStrength.score >= 3 ? 'text-green-600' :
                        passwordStrength.score >= 2 ? 'text-yellow-600' : 'text-red-600'
                      }`}>
                      {getPasswordStrengthText(passwordStrength.score)}
                    </span>
                  </div>
                  <Progress
                    value={(passwordStrength.score / 4) * 100}
                    className={`h-2 ${getPasswordStrengthColor(passwordStrength.score)}`}
                  />
                  {passwordStrength.feedback.length > 0 && (
                    <div className="text-xs text-gray-600">
                      {passwordStrength.suggestions.join(', ')}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Two-Factor Authentication Code */}
            {requiresTwoFactor && (
              <div className="space-y-2">
                <Label htmlFor="twoFactorCode">Código 2FA</Label>
                <Input
                  id="twoFactorCode"
                  type="text"
                  placeholder="000000"
                  maxLength={6}
                  autoComplete="one-time-code"
                  disabled={isLocked || isLoading || isSubmitting}
                  {...register('twoFactorCode')}
                  className={errors.twoFactorCode ? 'border-red-500' : ''}
                />
                {errors.twoFactorCode && (
                  <p className="text-sm text-red-600">{errors.twoFactorCode.message}</p>
                )}
              </div>
            )}

            {/* Remember Me */}
            <div className="flex items-center space-x-2">
              <Checkbox
                id="rememberMe"
                disabled={isLocked || isLoading || isSubmitting}
                onCheckedChange={(checked) => setValue('rememberMe', !!checked)}
              />
              <Label htmlFor="rememberMe" className="text-sm text-gray-600">
                Lembrar-me por 30 dias
              </Label>
            </div>

            {/* Submit Button */}
            <Button
              type="submit"
              className="w-full"
              disabled={isLocked || isLoading || isSubmitting}
            >
              {isSubmitting ? (
                <div className="flex items-center space-x-2">
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                  <span>Entrando...</span>
                </div>
              ) : (
                'Entrar'
              )}
            </Button>

            {/* Forgot Password */}
            {onForgotPassword && (
              <div className="text-center">
                <button
                  type="button"
                  onClick={handleForgotPassword}
                  disabled={!watchedEmail || isLocked || isLoading}
                  className="text-sm text-blue-600 hover:text-blue-500 disabled:text-gray-400 disabled:cursor-not-allowed"
                >
                  Esqueceu sua senha?
                </button>
              </div>
            )}
          </form>

          {/* Security Notice */}
          <div className="mt-6 p-3 bg-gray-50 rounded-md">
            <div className="flex items-start space-x-2">
              <CheckCircle className="h-4 w-4 text-green-600 mt-0.5 flex-shrink-0" />
              <div className="text-xs text-gray-600">
                <p className="font-medium">Login Seguro</p>
                <ul className="mt-1 space-y-1">
                  <li>• Criptografia ponta a ponta</li>
                  <li>• Monitoramento de sessão</li>
                  <li>• Proteção contra tentativas falhadas</li>
                </ul>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export default AdminLoginForm