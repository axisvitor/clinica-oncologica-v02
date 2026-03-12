import React, { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { ArrowLeft, CircleAlert, Mail, MailCheck, ShieldAlert } from 'lucide-react'
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

const logger = createLogger('PasswordResetRequestPage')

const passwordResetRequestSchema = z.object({
  email: z.string().trim().email('Informe um email válido.'),
})

type PasswordResetRequestFormData = z.infer<typeof passwordResetRequestSchema>

type AuthUiError = {
  message: string
  error?: string
  request_id?: string
  status?: number
}

const GENERIC_SUCCESS_COPY =
  'Se existir uma conta vinculada a este email, enviaremos um link para recuperar a senha ou concluir o primeiro acesso.'

const deliveryFailureCopy =
  'Não foi possível enviar o email agora. Tente novamente em alguns minutos ou repita a solicitação mais tarde.'

export function PasswordResetRequestPage() {
  const alertRef = useRef<HTMLDivElement>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submissionState, setSubmissionState] = useState<'idle' | 'success' | 'error'>('idle')
  const [requestError, setRequestError] = useState<AuthUiError | null>(null)
  const [lastSubmittedEmail, setLastSubmittedEmail] = useState<string>('')

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<PasswordResetRequestFormData>({
    resolver: zodResolver(passwordResetRequestSchema),
    defaultValues: {
      email: '',
    },
  })

  useEffect(() => {
    if ((submissionState === 'success' || submissionState === 'error') && alertRef.current) {
      alertRef.current.focus()
    }
  }, [submissionState])

  const errorMessage = useMemo(() => {
    if (!requestError) {
      return null
    }

    if (requestError.error === 'AUTH_PASSWORD_RESET_DELIVERY_FAILED') {
      return deliveryFailureCopy
    }

    return requestError.message
  }, [requestError])

  const onSubmit = async ({ email }: PasswordResetRequestFormData) => {
    const normalizedEmail = email.trim().toLowerCase()

    setIsSubmitting(true)
    setSubmissionState('idle')
    setRequestError(null)

    try {
      logger.log('Auth phase=reset-request', { hasEmail: normalizedEmail.length > 0 })
      await apiClient.auth.requestPasswordReset({ email: normalizedEmail })
      setLastSubmittedEmail(normalizedEmail)
      setSubmissionState('success')
      reset({ email: normalizedEmail })
    } catch (error) {
      const safeError = toUserSafeAuthError(
        error,
        'Não foi possível iniciar a recuperação de senha. Tente novamente.'
      )

      logger.error('Reset request failed', {
        status: safeError.status,
        error: safeError.error,
        request_id: safeError.request_id,
      })

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

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(59,130,246,0.18),_transparent_45%),linear-gradient(180deg,_#f8fafc_0%,_#eef6ff_100%)] px-4 py-10 sm:px-6 lg:px-8">
      <div className="mx-auto flex min-h-[calc(100vh-5rem)] max-w-5xl items-center justify-center">
        <div className="grid w-full gap-6 lg:grid-cols-[1.15fr_0.85fr]">
          <Card className="border-slate-200 shadow-xl shadow-slate-200/60">
            <CardHeader className="space-y-4">
              <div className="inline-flex w-fit items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.24em] text-blue-700">
                <MailCheck className="h-3.5 w-3.5" aria-hidden="true" />
                recuperação e primeiro acesso
              </div>
              <div className="space-y-2">
                <CardTitle className="text-3xl font-heading text-slate-950">
                  <h1>Receber um novo link de acesso</h1>
                </CardTitle>
                <CardDescription className="max-w-xl text-sm leading-6 text-slate-600">
                  Informe o email cadastrado para receber um link seguro. A resposta exibida aqui é
                  sempre genérica para proteger a privacidade das contas.
                </CardDescription>
              </div>
            </CardHeader>
            <CardContent className="space-y-5">
              <div aria-live="polite" aria-atomic="true" className="sr-only">
                {isSubmitting && 'Enviando solicitação de recuperação de senha...'}
                {submissionState === 'success' && GENERIC_SUCCESS_COPY}
                {submissionState === 'error' && `Erro na recuperação de senha: ${errorMessage}`}
              </div>

              {submissionState === 'success' && (
                <Alert
                  ref={alertRef}
                  tabIndex={-1}
                  className="border-emerald-200 bg-emerald-50 text-emerald-900 focus-visible:ring-2 focus-visible:ring-emerald-500"
                >
                  <MailCheck className="h-4 w-4 text-emerald-700" aria-hidden="true" />
                  <AlertTitle className="text-emerald-900">Confira sua caixa de entrada</AlertTitle>
                  <AlertDescription className="text-emerald-800">
                    <p>{GENERIC_SUCCESS_COPY}</p>
                    <p>
                      Se o email já estiver ativo no sistema, o link permitirá redefinir a senha ou
                      concluir o primeiro acesso.
                    </p>
                  </AlertDescription>
                </Alert>
              )}

              {submissionState === 'error' && requestError && (
                <Alert
                  ref={alertRef}
                  variant="destructive"
                  tabIndex={-1}
                  className="focus-visible:ring-2 focus-visible:ring-red-500"
                >
                  <ShieldAlert className="h-4 w-4" aria-hidden="true" />
                  <AlertTitle>Não foi possível enviar o link agora</AlertTitle>
                  <AlertDescription>
                    <p>{errorMessage}</p>
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
                  <Label htmlFor="reset-request-email">Email</Label>
                  <div className="relative">
                    <Mail className="absolute left-3 top-3.5 h-4 w-4 text-slate-400" aria-hidden="true" />
                    <Input
                      id="reset-request-email"
                      type="email"
                      autoComplete="email"
                      placeholder="seu@email.com"
                      className="pl-10"
                      aria-invalid={errors.email ? 'true' : 'false'}
                      aria-describedby={errors.email ? 'reset-request-email-error' : 'reset-request-email-help'}
                      {...register('email')}
                    />
                  </div>
                  {errors.email ? (
                    <p id="reset-request-email-error" role="alert" className="text-sm text-red-600">
                      {errors.email.message}
                    </p>
                  ) : (
                    <p id="reset-request-email-help" className="text-sm text-slate-500">
                      Use o mesmo email informado pela equipe administrativa.
                    </p>
                  )}
                </div>

                <Button type="submit" className="w-full" disabled={isSubmitting}>
                  {isSubmitting ? (
                    <>
                      <LoadingSpinner size="sm" className="mr-2" />
                      Enviando link...
                    </>
                  ) : (
                    'Enviar link de recuperação'
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
                {lastSubmittedEmail && submissionState === 'success' && (
                  <p className="text-xs text-slate-500">
                    Solicitação registrada para o email informado agora há pouco.
                  </p>
                )}
              </div>
            </CardContent>
          </Card>

          <Card className="border-slate-200 bg-slate-950 text-slate-50 shadow-xl shadow-slate-300/30">
            <CardHeader>
              <CardTitle className="text-xl font-heading">O que acontece depois?</CardTitle>
              <CardDescription className="text-slate-300">
                O fluxo foi alinhado ao backend de sessão própria, sem instruções estáticas de suporte.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 text-sm leading-6 text-slate-200">
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <p className="font-semibold text-white">1. O link é enviado por email</p>
                <p className="mt-1 text-slate-300">
                  O sistema usa o endpoint de recuperação para enviar o mesmo fluxo usado em
                  redefinição de senha e primeiro acesso.
                </p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <p className="font-semibold text-white">2. O conteúdo nunca revela se a conta existe</p>
                <p className="mt-1 text-slate-300">
                  A mensagem de sucesso permanece genérica para evitar enumeração de usuários.
                </p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <p className="font-semibold text-white">3. Falhas seguem um contrato observável</p>
                <p className="mt-1 text-slate-300">
                  Quando o backend recusa a entrega, a interface mostra um estado acionável com código
                  estável e identificador de solicitação.
                </p>
              </div>
              <Alert className="border-white/10 bg-white/5 text-slate-100">
                <CircleAlert className="h-4 w-4 text-blue-300" aria-hidden="true" />
                <AlertTitle className="text-slate-50">Dica rápida</AlertTitle>
                <AlertDescription className="text-slate-300">
                  Links antigos podem expirar. Se isso acontecer, volte aqui e solicite um novo envio.
                </AlertDescription>
              </Alert>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
