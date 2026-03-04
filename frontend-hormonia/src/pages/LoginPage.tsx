import React, { useState, useRef, useEffect } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Eye, EyeOff, Lock, Mail, CircleAlert as AlertCircle, KeyRound } from 'lucide-react'
import { useAuth } from '@/app/providers/AuthContext'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useIsMobile } from '@/components/ui/use-mobile'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { LoadingSpinner } from '@/components/ui/loading-spinner'
import { isProduction } from '@/lib/runtime-config'
import { useConfig } from '@/lib/config-initializer'
import { useAuthSubmit } from '@/hooks/use-auth-submit'

const loginSchema = z.object({
  email: z.string().email('Email inválido'),
  password: z.string().min(6, 'Senha deve ter pelo menos 6 caracteres'),
  rememberMe: z.boolean().optional(),
})

type LoginFormData = z.infer<typeof loginSchema>

export function LoginPage() {
  const { login, isAuthenticated, isInitializing } = useAuth()
  const { config } = useConfig()
  const location = useLocation()
  const [showPassword, setShowPassword] = useState(false)
  const [showForgotPassword, setShowForgotPassword] = useState(false)
  const errorAlertRef = useRef<HTMLDivElement>(null)
  const isMobile = useIsMobile()

  const {
    isSubmitting: isSubmittingAuth,
    error: authError,
    handleSubmit: handleAuthSubmit,
  } = useAuthSubmit<LoginFormData>({
    onSubmit: async (data) => login(data.email, data.password, data.rememberMe || false),
  })

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
  })

  useEffect(() => {
    if (authError && errorAlertRef.current) {
      errorAlertRef.current.focus()
    }
  }, [authError])

  if (isAuthenticated) {
    const from = location.state?.from?.pathname || '/dashboard'
    return <Navigate to={from} replace />
  }

  const showDemoCredentials =
    !isProduction() &&
    (config?.VITE_ENVIRONMENT === 'development' ||
      config?.VITE_DEBUG_MODE === 'true' ||
      config?.VITE_SHOW_DEMO_CREDENTIALS === 'true')

  const emailErrorId = 'email-error'
  const passwordErrorId = 'password-error'

  const handleForgotPassword = () => {
    setShowForgotPassword(true)
  }

  // Only show full-page spinner during initial Firebase bootstrap
  // During login attempts, the form stays visible with inline spinner
  if (isInitializing) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 p-3 md:p-4">
      <div className="w-full max-w-md space-y-4 md:space-y-8">
        <div className="text-center font-heading">
          <img
            src="/images/logo_system.svg"
            alt="Neoplasias Litoral - Sistema de Gestão"
            width={2430}
            height={1150}
            className="mx-auto h-24 md:h-32 w-auto mb-4"
          />
        </div>

        {showDemoCredentials && (
          <Card className="bg-blue-50 border-blue-200">
            <CardContent className="pt-4 md:pt-6 px-4 md:px-6">
              <div className="flex items-start space-x-2">
                <AlertCircle
                  className="h-4 w-4 md:h-5 md:w-5 text-blue-600 mt-0.5 flex-shrink-0"
                  aria-hidden="true"
                />
                <div className="flex-1 min-w-0">
                  <h3 className="text-xs md:text-sm font-medium text-blue-800">Credenciais Demo</h3>
                  <div className="mt-2 text-xs md:text-sm text-blue-700 space-y-1">
                    <p className="truncate">
                      <strong>Email:</strong> admin@neoplasiaslitoral.com
                    </p>
                    <p>
                      <strong>Senha:</strong> Admin@123456!
                    </p>
                  </div>
                  <p className="mt-2 text-xs text-blue-600">* Apenas em desenvolvimento</p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        <Card>
          <CardHeader className="px-4 md:px-6 pt-4 md:pt-6">
            <CardTitle className="text-xl md:text-2xl font-heading">Entrar na sua conta</CardTitle>
            <CardDescription className="text-sm font-body">
              Digite suas credenciais para acessar o sistema
            </CardDescription>
          </CardHeader>
          <CardContent className="px-4 md:px-6 pb-4 md:pb-6">
            <form onSubmit={handleSubmit(handleAuthSubmit)} className="space-y-3 md:space-y-4">
              <div aria-live="polite" aria-atomic="true" className="sr-only">
                {isSubmittingAuth && 'Enviando dados de login…'}
                {authError && `Erro no login: ${authError}`}
              </div>

              {authError && (
                <Alert
                  ref={errorAlertRef}
                  variant="destructive"
                  role="alert"
                  aria-live="polite"
                  tabIndex={-1}
                  className="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
                >
                  <AlertCircle className="h-4 w-4" aria-hidden="true" />
                  <AlertDescription>{authError}</AlertDescription>
                </Alert>
              )}

              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <div className="relative">
                  <Mail
                    className="absolute left-3 top-3 h-4 w-4 text-gray-400"
                    aria-hidden="true"
                  />
                  <Input
                    id="email"
                    type="email"
                    placeholder={
                      showDemoCredentials ? 'admin@neoplasiaslitoral.com…' : 'seu@email.com…'
                    }
                    className="pl-10"
                    autoComplete="email"
                    spellCheck={false}
                    autoFocus={!isMobile}
                    aria-invalid={errors.email ? 'true' : 'false'}
                    aria-describedby={errors.email ? emailErrorId : undefined}
                    {...register('email')}
                  />
                </div>
                {errors.email && (
                  <p id={emailErrorId} className="text-sm text-red-600" role="alert">
                    {errors.email.message}
                  </p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="password">Senha</Label>
                <div className="relative">
                  <Lock
                    className="absolute left-3 top-3 h-4 w-4 text-gray-400"
                    aria-hidden="true"
                  />
                  <Input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    placeholder="Ex.: Senha@123…"
                    className="pl-10 pr-10"
                    autoComplete="current-password"
                    aria-invalid={errors.password ? 'true' : 'false'}
                    aria-describedby={errors.password ? passwordErrorId : undefined}
                    {...register('password')}
                  />
                  <button
                    type="button"
                    className="absolute right-3 top-3 text-gray-400 hover:text-gray-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-1 rounded"
                    onClick={() => setShowPassword(!showPassword)}
                    aria-label={showPassword ? 'Ocultar senha' : 'Mostrar senha'}
                    tabIndex={0}
                  >
                    {showPassword ? (
                      <EyeOff className="h-4 w-4" aria-hidden="true" />
                    ) : (
                      <Eye className="h-4 w-4" aria-hidden="true" />
                    )}
                  </button>
                </div>
                {errors.password && (
                  <p id={passwordErrorId} className="text-sm text-red-600" role="alert">
                    {errors.password.message}
                  </p>
                )}
              </div>

              <div className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  id="rememberMe"
                  {...register('rememberMe')}
                  className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <Label htmlFor="rememberMe" className="text-sm font-normal cursor-pointer">
                  Manter-me conectado
                </Label>
              </div>

              <Button type="submit" className="w-full" disabled={isSubmittingAuth}>
                {isSubmittingAuth ? (
                  <>
                    <LoadingSpinner size="sm" className="mr-2" />
                    <span aria-live="polite" id="submit-status">
                      Entrando…
                    </span>
                  </>
                ) : (
                  'Entrar'
                )}
              </Button>

              <div className="text-center">
                <button
                  type="button"
                  onClick={handleForgotPassword}
                  disabled={showForgotPassword}
                  className="text-sm text-blue-600 hover:text-blue-700 underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-1 rounded disabled:opacity-50"
                  aria-label="Solicitar redefinição de senha"
                >
                  <KeyRound className="inline h-4 w-4 mr-1" aria-hidden="true" />
                  {showForgotPassword ? 'Processando…' : 'Esqueci minha senha'}
                </button>
              </div>
            </form>
          </CardContent>
        </Card>

        {showForgotPassword && (
          <Alert className="bg-blue-50 border-blue-200">
            <AlertCircle className="h-4 w-4 text-blue-600" aria-hidden="true" />
            <AlertTitle className="text-blue-800">Redefinição de Senha</AlertTitle>
            <AlertDescription className="text-blue-700">
              Para redefinir sua senha, entre em contato com o administrador do sistema ou envie um
              email para{' '}
              <a
                href="mailto:suporte@neoplasiaslitoral.com"
                className="font-medium underline hover:text-blue-900"
              >
                suporte@neoplasiaslitoral.com
              </a>
            </AlertDescription>
            <button
              onClick={() => setShowForgotPassword(false)}
              className="mt-2 text-sm text-blue-600 hover:text-blue-800 underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-1 rounded"
              aria-label="Fechar mensagem"
            >
              Fechar
            </button>
          </Alert>
        )}

        <div className="text-center text-sm text-gray-600">
          <p>Neoplasias Litoral v1.0.0</p>
          <p className="mt-1">Desenvolvido para profissionais de saúde</p>
          {!isProduction() && (
            <p className="mt-2 text-xs text-orange-600">🔧 Ambiente de desenvolvimento</p>
          )}
        </div>
      </div>
    </div>
  )
}
