import React, { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useLocation, useSearchParams } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import {
  ArrowLeft,
  CheckCircle2,
  CircleAlert,
  KeyRound,
  Link2Off,
  LockKeyhole,
  RefreshCcw,
  ShieldCheck,
} from 'lucide-react'
import { ROUTES } from '@/app/routes/routeConfig'
import { apiClient } from '@/lib/api-client'
import { toUserSafeAuthError } from '@/lib/api-client/auth'
import { createLogger } from '@/lib/logger'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { LoadingSpinner } from '@/components/ui/loading-spinner'

const logger = createLogger('PasswordResetConfirmPage')

const passwordResetConfirmSchema = z
  .object({
    newPassword: z
      .string()
      .min(8, 'Use pelo menos 8 caracteres.')
      .regex(/[A-Z]/, 'Inclua ao menos uma letra maiúscula.')
      .regex(/[a-z]/, 'Inclua ao menos uma letra minúscula.')
      .regex(/[0-9]/, 'Inclua ao menos um número.'),
    confirmPassword: z.string().min(1, 'Confirme a nova senha.'),
  })
  .refine((data) => data.newPassword === data.confirmPassword, {
    path: ['confirmPassword'],
    message: 'As senhas precisam ser iguais.',
  })

type PasswordResetConfirmFormData = z.infer<typeof passwordResetConfirmSchema>

type AuthUiError = {
  message: string
  error?: string
  request_id?: string
  status?: number
}

const INVALID_TOKEN_CODE = 'AUTH_RESET_TOKEN_INVALID_OR_EXPIRED'
const WEAK_PASSWORD_CODE = 'AUTH_PASSWORD_WEAK'

export function PasswordResetConfirmPage() {
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const alertRef = useRef<HTMLDivElement>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submissionState, setSubmissionState] = useState<'idle' | 'success' | 'error'>('idle')
  const [requestError, setRequestError] = useState<AuthUiError | null>(null)
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)

  const token = searchParams.get('token')?.trim() ?? ''
  const isFirstAccessFlow = location.pathname === ROUTES.AUTH.FIRST_ACCESS

  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors },
  } = useForm<PasswordResetConfirmFormData>({
    resolver: zodResolver(passwordResetConfirmSchema),
    defaultValues: {
      newPassword: '',
      confirmPassword: '',
    },
  })

  useEffect(() => {
    if ((submissionState === 'success' || submissionState === 'error' || !token) && alertRef.current) {
      alertRef.current.focus()
    }
  }, [submissionState, token])

  const pageCopy = useMemo(() => {
    if (isFirstAccessFlow) {
      return {
        eyebrow: 'primeiro acesso',
        title: 'Definir a senha inicial',
        description:
          'Escolha uma senha para concluir a ativação da conta e entrar pela rota pública oficial.',
        successTitle: 'Primeiro acesso concluído',
        successDescription:
          'Sua senha inicial foi definida com sucesso. Agora você já pode entrar com email e senha.',
        tokenErrorTitle: 'O link de ativação expirou',
        tokenErrorDescription:
          'Solicite um novo link para concluir o primeiro acesso com segurança.',
      }
    }

    return {
      eyebrow: 'nova senha',
      title: 'Criar uma nova senha',
      description:
        'Use o token recebido por email para redefinir a senha sem depender de fluxos legados do Firebase.',
      successTitle: 'Senha atualizada com sucesso',
      successDescription: 'Você já pode voltar ao login e acessar a plataforma com a nova senha.',
      tokenErrorTitle: 'O link de recuperação expirou',
      tokenErrorDescription: 'Solicite um novo link para continuar a recuperação da conta.',
    }
  }, [isFirstAccessFlow])

  const resolvedErrorMessage = useMemo(() => {
    if (!requestError) {
      return null
    }

    if (requestError.error === INVALID_TOKEN_CODE) {
      return pageCopy.tokenErrorDescription
    }

    if (requestError.error === WEAK_PASSWORD_CODE) {
      return 'A nova senha precisa atender aos requisitos mínimos de segurança.'
    }

    return requestError.message
  }, [pageCopy.tokenErrorDescription, requestError])

  const onSubmit = async ({ newPassword }: PasswordResetConfirmFormData) => {
    if (!token) {
      setRequestError({
        message: 'Invalid or expired reset token.',
        error: INVALID_TOKEN_CODE,
      })
      setSubmissionState('error')
      return
    }

    setIsSubmitting(true)
    setSubmissionState('idle')
    setRequestError(null)

    try {
      logger.log('Auth phase=reset-confirm', {
        hasToken: token.length > 0,
        flow: isFirstAccessFlow ? 'first-access' : 'recovery',
      })

      await apiClient.auth.confirmPasswordReset({
        token,
        new_password: newPassword,
      })

      reset()
      setSubmissionState('success')
    } catch (error) {
      const safeError = toUserSafeAuthError(
        error,
        'Não foi possível atualizar a senha. Solicite um novo link e tente novamente.'
      )

      logger.error('Reset confirmation failed', {
        status: safeError.status,
        error: safeError.error,
        request_id: safeError.request_id,
      })

      if (safeError.error === WEAK_PASSWORD_CODE) {
        setError('newPassword', {
          type: 'server',
          message: 'Use uma senha com pelo menos 8 caracteres, letras maiúsculas, minúsculas e números.',
        })
      }

      setRequestError({
        message: safeError.message,
        error: safeError.error,
        request_id: safeError.request_id,
        status: safeError.status,
      })
      setSubmissionState('error')
    } finally {
      setIsSubmitting(false)
    }
  }

  const hasTokenError = !token || requestError?.error === INVALID_TOKEN_CODE

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(16,185,129,0.12),_transparent_40%),linear-gradient(180deg,_#f8fafc_0%,_#f0fdf4_100%)] px-4 py-10 sm:px-6 lg:px-8">
      <div className="mx-auto flex min-h-[calc(100vh-5rem)] max-w-5xl items-center justify-center">
        <div className="grid w-full gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <Card className="border-slate-200 shadow-xl shadow-slate-200/60">
            <CardHeader className="space-y-4">
              <div className="inline-flex w-fit items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.24em] text-emerald-700">
                <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" />
                {pageCopy.eyebrow}
              </div>
              <div className="space-y-2">
                <CardTitle className="text-3xl font-heading text-slate-950">
                  <h1>{pageCopy.title}</h1>
                </CardTitle>
                <CardDescription className="max-w-xl text-sm leading-6 text-slate-600">
                  {pageCopy.description}
                </CardDescription>
              </div>
            </CardHeader>
            <CardContent className="space-y-5">
              <div aria-live="polite" aria-atomic="true" className="sr-only">
                {isSubmitting && 'Atualizando senha...'}
                {submissionState === 'success' && pageCopy.successDescription}
                {submissionState === 'error' && `Erro ao atualizar senha: ${resolvedErrorMessage}`}
                {!token && pageCopy.tokenErrorDescription}
              </div>

              {!token && (
                <Alert
                  ref={alertRef}
                  variant="destructive"
                  tabIndex={-1}
                  className="focus-visible:ring-2 focus-visible:ring-red-500"
                >
                  <Link2Off className="h-4 w-4" aria-hidden="true" />
                  <AlertTitle>{pageCopy.tokenErrorTitle}</AlertTitle>
                  <AlertDescription>
                    <p>{pageCopy.tokenErrorDescription}</p>
                    <p className="text-xs font-medium text-red-700/90">
                      Código: {INVALID_TOKEN_CODE}
                    </p>
                  </AlertDescription>
                </Alert>
              )}

              {submissionState === 'success' && (
                <Alert
                  ref={alertRef}
                  tabIndex={-1}
                  className="border-emerald-200 bg-emerald-50 text-emerald-900 focus-visible:ring-2 focus-visible:ring-emerald-500"
                >
                  <CheckCircle2 className="h-4 w-4 text-emerald-700" aria-hidden="true" />
                  <AlertTitle className="text-emerald-900">{pageCopy.successTitle}</AlertTitle>
                  <AlertDescription className="text-emerald-800">
                    <p>{pageCopy.successDescription}</p>
                  </AlertDescription>
                </Alert>
              )}

              {submissionState === 'error' && requestError && token && (
                <Alert
                  ref={alertRef}
                  variant="destructive"
                  tabIndex={-1}
                  className="focus-visible:ring-2 focus-visible:ring-red-500"
                >
                  <CircleAlert className="h-4 w-4" aria-hidden="true" />
                  <AlertTitle>
                    {requestError.error === INVALID_TOKEN_CODE
                      ? pageCopy.tokenErrorTitle
                      : 'Não foi possível concluir a atualização'}
                  </AlertTitle>
                  <AlertDescription>
                    <p>{resolvedErrorMessage}</p>
                    {(requestError.error || requestError.request_id) && (
                      <p className="text-xs font-medium text-red-700/90">
                        {requestError.error ? `Código: ${requestError.error}` : 'Código: indisponível'}
                        {requestError.request_id ? ` · Solicitação: ${requestError.request_id}` : ''}
                      </p>
                    )}
                  </AlertDescription>
                </Alert>
              )}

              <form className="space-y-4" onSubmit={handleSubmit(onSubmit)} noValidate>
                <div className="space-y-2">
                  <Label htmlFor="reset-confirm-password">Nova senha</Label>
                  <div className="relative">
                    <LockKeyhole className="absolute left-3 top-3.5 h-4 w-4 text-slate-400" aria-hidden="true" />
                    <Input
                      id="reset-confirm-password"
                      type={showPassword ? 'text' : 'password'}
                      autoComplete="new-password"
                      placeholder="Crie uma senha forte"
                      className="pl-10 pr-12"
                      aria-invalid={errors.newPassword ? 'true' : 'false'}
                      aria-describedby={errors.newPassword ? 'reset-confirm-password-error' : 'reset-confirm-password-help'}
                      {...register('newPassword')}
                    />
                    <button
                      type="button"
                      className="absolute right-3 top-3 text-gray-400 hover:text-gray-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-1 rounded"
                      onClick={() => setShowPassword((current) => !current)}
                      aria-label={showPassword ? 'Ocultar senha' : 'Mostrar senha'}
                    >
                      <KeyRound className="h-4 w-4" aria-hidden="true" />
                    </button>
                  </div>
                  {errors.newPassword ? (
                    <p id="reset-confirm-password-error" role="alert" className="text-sm text-red-600">
                      {errors.newPassword.message}
                    </p>
                  ) : (
                    <p id="reset-confirm-password-help" className="text-sm text-slate-500">
                      Use pelo menos 8 caracteres com letras maiúsculas, minúsculas e números.
                    </p>
                  )}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="reset-confirm-password-confirmation">Confirmar senha</Label>
                  <div className="relative">
                    <LockKeyhole className="absolute left-3 top-3.5 h-4 w-4 text-slate-400" aria-hidden="true" />
                    <Input
                      id="reset-confirm-password-confirmation"
                      type={showConfirmPassword ? 'text' : 'password'}
                      autoComplete="new-password"
                      placeholder="Repita a nova senha"
                      className="pl-10 pr-12"
                      aria-invalid={errors.confirmPassword ? 'true' : 'false'}
                      aria-describedby={errors.confirmPassword ? 'reset-confirm-confirmation-error' : undefined}
                      {...register('confirmPassword')}
                    />
                    <button
                      type="button"
                      className="absolute right-3 top-3 text-gray-400 hover:text-gray-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-1 rounded"
                      onClick={() => setShowConfirmPassword((current) => !current)}
                      aria-label={showConfirmPassword ? 'Ocultar confirmação de senha' : 'Mostrar confirmação de senha'}
                    >
                      <KeyRound className="h-4 w-4" aria-hidden="true" />
                    </button>
                  </div>
                  {errors.confirmPassword && (
                    <p id="reset-confirm-confirmation-error" role="alert" className="text-sm text-red-600">
                      {errors.confirmPassword.message}
                    </p>
                  )}
                </div>

                <Button type="submit" className="w-full" disabled={isSubmitting || !token}>
                  {isSubmitting ? (
                    <>
                      <LoadingSpinner size="sm" className="mr-2" />
                      Salvando nova senha...
                    </>
                  ) : (
                    'Salvar nova senha'
                  )}
                </Button>
              </form>

              <div className="flex flex-col gap-3 border-t border-slate-200 pt-4 sm:flex-row sm:items-center sm:justify-between">
                <Button asChild variant="ghost" className="justify-start px-0 text-slate-600 hover:text-slate-900">
                  <Link to={ROUTES.LOGIN}>
                    <ArrowLeft className="h-4 w-4" aria-hidden="true" />
                    Voltar ao login
                  </Link>
                </Button>
                {(hasTokenError || submissionState === 'success') && (
                  <Button asChild variant="outline">
                    <Link to={ROUTES.AUTH.PASSWORD_RESET_REQUEST}>
                      <RefreshCcw className="h-4 w-4" aria-hidden="true" />
                      Solicitar novo link
                    </Link>
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>

          <Card className="border-slate-200 bg-slate-950 text-slate-50 shadow-xl shadow-slate-300/30">
            <CardHeader>
              <CardTitle className="text-xl font-heading">Requisitos mínimos da senha</CardTitle>
              <CardDescription className="text-slate-300">
                A tela reflete o contrato do backend para evitar tentativas cegas.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 text-sm leading-6 text-slate-200">
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <p className="font-semibold text-white">• 8 caracteres ou mais</p>
                <p className="mt-1 text-slate-300">Inclua uma combinação confiável para uso diário.</p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <p className="font-semibold text-white">• Letras maiúsculas e minúsculas</p>
                <p className="mt-1 text-slate-300">
                  Isso reduz falhas previsíveis e mantém o formulário alinhado ao serviço de reset.
                </p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <p className="font-semibold text-white">• Ao menos um número</p>
                <p className="mt-1 text-slate-300">
                  Se o backend rejeitar a senha, a interface preserva o código e o request_id para inspeção.
                </p>
              </div>
              <Alert className="border-white/10 bg-white/5 text-slate-100">
                <CircleAlert className="h-4 w-4 text-emerald-300" aria-hidden="true" />
                <AlertTitle className="text-slate-50">Sobre links expirados</AlertTitle>
                <AlertDescription className="text-slate-300">
                  Tokens inválidos ou expirados permanecem visíveis como estado acionável, sem cair em uma
                  mensagem genérica de suporte.
                </AlertDescription>
              </Alert>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
