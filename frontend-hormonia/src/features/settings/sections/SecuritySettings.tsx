import React from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as z from 'zod'
import { usePasswordChange } from '../../../hooks/useSettings'
import { SettingsSection } from '../SettingsSection'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Separator } from '@/components/ui/separator'
import { Badge } from '@/components/ui/badge'
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { toast } from '../../../hooks/use-toast'
import { Shield, Loader2 } from 'lucide-react'

const passwordSchema = z.object({
  current_password: z.string().min(1, 'Senha atual é obrigatória'),
  new_password: z.string().min(6, 'Nova senha deve ter pelo menos 6 caracteres'),
  confirm_password: z.string(),
}).refine((data) => data['new_password'] === data['confirm_password'], {
  message: 'Senhas não coincidem',
  path: ['confirm_password'],
})

type PasswordFormData = z.infer<typeof passwordSchema>

/**
 * Security Settings Component
 * Manages password changes, active sessions, and two-factor authentication
 */
export function SecuritySettings() {
  const { changePassword, isChangingPassword } = usePasswordChange()

  const passwordForm = useForm<PasswordFormData>({
    resolver: zodResolver(passwordSchema),
    defaultValues: {
      current_password: '',
      new_password: '',
      confirm_password: '',
    },
  })

  const onPasswordSubmit = (data: PasswordFormData) => {
    changePassword(data)
    passwordForm.reset()
  }

  return (
    <SettingsSection
      title="Segurança"
      description="Senha e autenticação"
      icon={Shield}
    >
      <div className="space-y-6">
        {/* Password Change Form */}
        <div>
          <h3 className="text-lg font-medium mb-4">Alterar Senha</h3>
          <Form {...passwordForm}>
            <form onSubmit={passwordForm.handleSubmit(onPasswordSubmit)} className="space-y-4 max-w-md">
              <FormField
                control={passwordForm.control}
                name="current_password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Senha atual</FormLabel>
                    <FormControl>
                      <Input type="password" placeholder="Sua senha atual" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={passwordForm.control}
                name="new_password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Nova senha</FormLabel>
                    <FormControl>
                      <Input type="password" placeholder="Nova senha" {...field} />
                    </FormControl>
                    <FormDescription>
                      A senha deve ter pelo menos 6 caracteres.
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={passwordForm.control}
                name="confirm_password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Confirmar nova senha</FormLabel>
                    <FormControl>
                      <Input type="password" placeholder="Confirme a nova senha" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <Button type="submit" disabled={isChangingPassword}>
                {isChangingPassword ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Shield className="mr-2 h-4 w-4" />
                )}
                Alterar senha
              </Button>
            </form>
          </Form>
        </div>

        <Separator />

        {/* Active Sessions */}
        <div>
          <h3 className="text-lg font-medium mb-4">Sessões Ativas</h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between p-3 border rounded-lg">
              <div>
                <p className="font-medium">Sessão atual</p>
                <p className="text-sm text-gray-500">
                  {navigator.userAgent.includes('Chrome') ? 'Chrome' :
                   navigator.userAgent.includes('Firefox') ? 'Firefox' :
                   navigator.userAgent.includes('Safari') ? 'Safari' : 'Navegador'} • Agora
                </p>
              </div>
              <Badge variant="outline">Atual</Badge>
            </div>
          </div>
        </div>

        <Separator />

        {/* Two-Factor Authentication */}
        <div>
          <h3 className="text-lg font-medium mb-4">Autenticação de Dois Fatores</h3>
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium">2FA</p>
              <p className="text-sm text-gray-500">
                Adicione uma camada extra de segurança à sua conta
              </p>
            </div>
            <Button
              variant="outline"
              onClick={() => {
                toast({
                  title: 'Em desenvolvimento',
                  description: '2FA será implementado em breve.',
                })
              }}
            >
              Configurar
            </Button>
          </div>
        </div>
      </div>
    </SettingsSection>
  )
}
