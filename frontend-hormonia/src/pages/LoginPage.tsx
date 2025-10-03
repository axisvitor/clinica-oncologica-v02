import React, { useState, useRef, useEffect } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Eye, EyeOff, Lock, Mail, CircleAlert as AlertCircle, KeyRound } from 'lucide-react'
import { useAuth } from '@/contexts/AuthContext'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { LoadingSpinner } from '../components/ui/loading-spinner'
import { isProduction } from '@/lib/runtime-config'
import { useConfig } from '@/lib/config-initializer'

const loginSchema = z.object({
  email: z.string().email('Email inválido'),
  password: z.string().min(6, 'Senha deve ter pelo menos 6 caracteres')
})

type LoginFormData = z.infer<typeof loginSchema>

export function LoginPage() {
  const { login, isAuthenticated, isLoading } = useAuth()
  const { config } = useConfig()
  const location = useLocation()
  const [showPassword, setShowPassword] = useState(false)
  const [loginError, setLoginError] = useState<string | null>(null)
  const [showForgotPassword, setShowForgotPassword] = useState(false)
  const [isSubmittingForm, setIsSubmittingForm] = useState(false)
  const errorAlertRef = useRef<HTMLDivElement>(null)
  const submitStatusRef = useRef<HTMLDivElement>(null)

  // Check if we should show demo credentials (only in development)
  const showDemoCredentials = !isProduction() && (
    config?.VITE_ENVIRONMENT === 'development' ||
    config?.VITE_DEBUG_MODE === 'true' ||
    config?.VITE_SHOW_DEMO_CREDENTIALS === 'true'
  )

  // Generate unique IDs for error messages
  const emailErrorId = 'email-error'
  const passwordErrorId = 'password-error'

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting }
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema)
  })

  // Focus management for accessibility
  useEffect(() => {
    if (loginError && errorAlertRef.current) {
      errorAlertRef.current.focus()
    }
  }, [loginError])

  // Redirect if already authenticated
  if (isAuthenticated) {
    const from = location.state?.from?.pathname || '/dashboard'
    return <Navigate to={from} replace />
  }

  const onSubmit = async (data: LoginFormData) => {
    try {
      setLoginError(null)
      setIsSubmittingForm(true)
      await login(data['email'], data['password'])
    } catch (error: any) {
      console.error('Login error:', error)
      
      // Handle different types of errors
      let errorMessage = 'Erro ao fazer login. Tente novamente.'
      
      if (error.status === 0) {
        errorMessage = 'Não foi possível conectar ao servidor. Verifique sua conexão com a internet.'
      } else if (error.status === 401) {
        errorMessage = 'Email ou senha incorretos. Verifique suas credenciais.'
      } else if (error.status === 408) {
        errorMessage = 'A requisição demorou muito para responder. Tente novamente.'
      } else if (error.status === 429) {
        errorMessage = 'Muitas tentativas de login. Aguarde alguns minutos antes de tentar novamente.'
      } else if (error.data?.message) {
        errorMessage = error.data.message
      } else if (error.message) {
        errorMessage = error.message
      }
      
      setLoginError(errorMessage)
    } finally {
      setIsSubmittingForm(false)
    }
  }

  const handleForgotPassword = () => {
    // Simple forgot password implementation - can be expanded
    setShowForgotPassword(true)
    setTimeout(() => {
      alert('Para redefinir sua senha, entre em contato com o administrador do sistema ou envie um email para suporte@neoplasiaslitoral.com')
      setShowForgotPassword(false)
    }, 100)
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <LoadingSpinner size="lg" />
      </div>
    )
  }
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 p-3 md:p-4">
      <div className="w-full max-w-md space-y-4 md:space-y-8">
        {/* Header */}
        <div className="text-center font-heading">
          <img
            src="/images/logo_system.svg"
            alt="Neoplasias Litoral - Sistema de Gestão"
            className="mx-auto h-24 md:h-32 w-auto mb-4"
          />
        </div>

        {/* Demo Credentials Info - Only in Development */}
        {showDemoCredentials && (
          <Card className="bg-blue-50 border-blue-200">
            <CardContent className="pt-4 md:pt-6 px-4 md:px-6">
              <div className="flex items-start space-x-2">
                <AlertCircle className="h-4 w-4 md:h-5 md:w-5 text-blue-600 mt-0.5 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <h3 className="text-xs md:text-sm font-medium text-blue-800">Credenciais Demo</h3>
                  <div className="mt-2 text-xs md:text-sm text-blue-700 space-y-1">
                    <p className="truncate"><strong>Email:</strong> admin@neoplasiaslitoral.com</p>
                    <p><strong>Senha:</strong> Admin@123456!</p>
                  </div>
                  <p className="mt-2 text-xs text-blue-600">
                    * Apenas em desenvolvimento
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Login Form */}
        <Card>
          <CardHeader className="px-4 md:px-6 pt-4 md:pt-6">
            <CardTitle className="text-xl md:text-2xl font-heading">Entrar na sua conta</CardTitle>
            <CardDescription className="text-sm font-body">
              Digite suas credenciais para acessar o sistema
            </CardDescription>
          </CardHeader>
          <CardContent className="px-4 md:px-6 pb-4 md:pb-6">
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-3 md:space-y-4">
              {/* Submit Status - Accessible announcements */}
              <div 
                ref={submitStatusRef}
                aria-live="polite" 
                aria-atomic="true"
                className="sr-only"
              >
                {isSubmittingForm && "Enviando dados de login..."}
                {loginError && `Erro no login: ${loginError}`}
              </div>

              {loginError && (
                <Alert
                  ref={errorAlertRef}
                  variant="destructive"
                  role="alert"
                  aria-live="polite"
                  tabIndex={-1}
                  className="focus:outline-none focus:ring-2 focus:ring-red-500"
                >
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>{loginError}</AlertDescription>
                </Alert>
              )}

              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <div className="relative">
                  <Mail className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
                  <Input
                    id="email"
                    type="email"
                    placeholder={showDemoCredentials ? "admin@neoplasiaslitoral.com" : "seu@email.com"}
                    className="pl-10"
                    autoComplete="email"
                    autoFocus
                    aria-invalid={errors['email'] ? 'true' : 'false'}
                    aria-describedby={errors['email'] ? emailErrorId : undefined}
                    {...register('email')}
                  />
                </div>
                {errors['email'] && (
                  <p id={emailErrorId} className="text-sm text-red-600" role="alert">
                    {errors['email'].message}
                  </p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="password">Senha</Label>
                <div className="relative">
                  <Lock className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
                  <Input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    placeholder="Sua senha"
                    className="pl-10 pr-10"
                    autoComplete="current-password"
                    aria-invalid={errors['password'] ? 'true' : 'false'}
                    aria-describedby={errors['password'] ? passwordErrorId : undefined}
                    {...register('password')}
                  />
                  <button
                    type="button"
                    className="absolute right-3 top-3 text-gray-400 hover:text-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 rounded"
                    onClick={() => setShowPassword(!showPassword)}
                    aria-label={showPassword ? "Ocultar senha" : "Mostrar senha"}
                    tabIndex={0}
                  >
                    {showPassword ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </button>
                </div>
                {errors['password'] && (
                  <p id={passwordErrorId} className="text-sm text-red-600" role="alert">
                    {errors['password'].message}
                  </p>
                )}
              </div>

              <Button
                type="submit"
                className="w-full"
                disabled={isSubmitting || isSubmittingForm}
                aria-describedby="submit-status"
              >
                {(isSubmitting || isSubmittingForm) ? (
                  <>
                    <LoadingSpinner size="sm" className="mr-2" />
                    <span aria-live="polite">Entrando...</span>
                  </>
                ) : (
                  'Entrar'
                )}
              </Button>

              {/* Forgot Password Link */}
              <div className="text-center">
                <button
                  type="button"
                  onClick={handleForgotPassword}
                  disabled={showForgotPassword}
                  className="text-sm text-blue-600 hover:text-blue-700 underline focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 rounded disabled:opacity-50"
                  aria-label="Solicitar redefinição de senha"
                >
                  <KeyRound className="inline h-4 w-4 mr-1" />
                  {showForgotPassword ? 'Processando...' : 'Esqueci minha senha'}
                </button>
              </div>
            </form>
          </CardContent>
        </Card>

        {/* Footer */}
        <div className="text-center text-sm text-gray-600">
          <p>Neoplasias Litoral v1.0.0</p>
          <p className="mt-1">
            Desenvolvido para profissionais de saúde
          </p>
          {!isProduction() && (
            <p className="mt-2 text-xs text-orange-600">
              🔧 Ambiente de desenvolvimento
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
