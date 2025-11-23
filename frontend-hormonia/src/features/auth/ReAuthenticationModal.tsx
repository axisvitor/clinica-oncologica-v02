import React, { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as z from 'zod'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Loader2, Shield, AlertCircle } from 'lucide-react'
import { logger } from '@/lib/logger'

const reAuthSchema = z.object({
  password: z.string().min(1, 'Senha é obrigatória'),
})

type ReAuthFormData = z.infer<typeof reAuthSchema>

interface ReAuthenticationModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onSuccess: (password: string) => void | Promise<void>
  title?: string
  description?: string
  error?: string | null
}

/**
 * ReAuthenticationModal Component
 *
 * Prompts user to re-enter their current password before performing
 * sensitive operations like password change.
 *
 * Security:
 * - Password is passed to parent via callback (not stored)
 * - Form is cleared on close
 * - Error messages are user-friendly
 *
 * @param open - Control modal visibility
 * @param onOpenChange - Callback when modal visibility changes
 * @param onSuccess - Callback with password when user confirms (can be async)
 * @param title - Optional custom title
 * @param description - Optional custom description
 * @param error - Optional error message to display
 */
export function ReAuthenticationModal({
  open,
  onOpenChange,
  onSuccess,
  title = 'Confirmar identidade',
  description = 'Por segurança, confirme sua senha atual antes de continuar.',
  error = null,
}: ReAuthenticationModalProps) {
  const [isSubmitting, setIsSubmitting] = useState(false)

  const form = useForm<ReAuthFormData>({
    resolver: zodResolver(reAuthSchema),
    defaultValues: {
      password: '',
    },
  })

  const handleSubmit = async (data: ReAuthFormData) => {
    setIsSubmitting(true)
    try {
      await onSuccess(data.password)
      form.reset()
    } catch (err) {
      // Parent handles error display
      logger.error('Re-authentication error', err)
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleClose = (open: boolean) => {
    if (!open) {
      form.reset()
    }
    onOpenChange(open)
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <div className="flex items-center gap-3 mb-2">
            <div className="p-3 rounded-full bg-blue-100">
              <Shield className="h-6 w-6 text-blue-600" />
            </div>
            <div>
              <DialogTitle className="text-xl">{title}</DialogTitle>
            </div>
          </div>
          <DialogDescription className="text-base">
            {description}
          </DialogDescription>
        </DialogHeader>

        {error && (
          <Alert variant="destructive" className="mt-2">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <Form {...form}>
          <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4 mt-4">
            <FormField
              control={form.control}
              name="password"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Senha atual</FormLabel>
                  <FormControl>
                    <Input
                      type="password"
                      placeholder="Digite sua senha atual"
                      autoComplete="current-password"
                      autoFocus
                      disabled={isSubmitting}
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="flex gap-3 justify-end mt-6">
              <Button
                type="button"
                variant="outline"
                onClick={() => handleClose(false)}
                disabled={isSubmitting}
              >
                Cancelar
              </Button>
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Verificando...
                  </>
                ) : (
                  <>
                    <Shield className="mr-2 h-4 w-4" />
                    Confirmar
                  </>
                )}
              </Button>
            </div>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
