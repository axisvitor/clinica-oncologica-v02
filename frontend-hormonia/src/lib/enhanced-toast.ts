/**
 * Enhanced Toast Notification System
 *
 * Provides improved toast notifications with better UX and error handling
 */

import { toast as baseToast, type ToastProps } from '../hooks/use-toast'
import { createLogger } from './logger'

const logger = createLogger('Toast')

interface EnhancedToastOptions extends Omit<ToastProps, 'title' | 'description'> {
  title: string
  description?: string
  duration?: number
  persistent?: boolean
  action?: {
    label: string
    onClick: () => void
  }
}

export const enhancedToast = {
  // Success notifications
  success: (options: Omit<EnhancedToastOptions, 'variant'>) => {
    logger.debug('Success toast:', options.title)
    return baseToast({
      ...options,
      variant: 'default',
      duration: options.duration || 4000,
      className: 'border-green-200 bg-green-50 text-green-800'
    })
  },

  // Error notifications
  error: (options: Omit<EnhancedToastOptions, 'variant'>) => {
    logger.debug('Error toast:', options.title)
    return baseToast({
      ...options,
      variant: 'destructive',
      duration: options.persistent ? undefined : (options.duration || 8000)
    })
  },

  // Warning notifications
  warning: (options: Omit<EnhancedToastOptions, 'variant'>) => {
    logger.debug('Warning toast:', options.title)
    return baseToast({
      ...options,
      variant: 'default',
      duration: options.duration || 6000,
      className: 'border-yellow-200 bg-yellow-50 text-yellow-800'
    })
  },

  // Info notifications
  info: (options: Omit<EnhancedToastOptions, 'variant'>) => {
    logger.debug('Info toast:', options.title)
    return baseToast({
      ...options,
      variant: 'default',
      duration: options.duration || 5000,
      className: 'border-blue-200 bg-blue-50 text-blue-800'
    })
  },

  // Loading notifications with progress
  loading: (options: Omit<EnhancedToastOptions, 'variant'>) => {
    logger.debug('Loading toast:', options.title)
    return baseToast({
      ...options,
      variant: 'default',
      duration: undefined, // Don't auto-dismiss loading toasts
      className: 'border-gray-200 bg-gray-50 text-gray-800'
    })
  },

  // Network error specific
  networkError: (retryFn?: () => void) => {
    return enhancedToast.error({
      title: 'Erro de Conexão',
      description: 'Não foi possível conectar ao servidor. Verifique sua conexão.',
      persistent: true,
      action: retryFn ? {
        label: 'Tentar Novamente',
        onClick: retryFn
      } : undefined
    })
  },

  // Authentication error
  authError: () => {
    return enhancedToast.error({
      title: 'Sessão Expirada',
      description: 'Sua sessão expirou. Você será redirecionado para o login.',
      persistent: true
    })
  },

  // Permission error
  permissionError: () => {
    return enhancedToast.error({
      title: 'Acesso Negado',
      description: 'Você não tem permissão para realizar esta ação.',
      duration: 6000
    })
  },

  // Validation error
  validationError: (message: string) => {
    return enhancedToast.error({
      title: 'Dados Inválidos',
      description: message,
      duration: 6000
    })
  },

  // Operation success
  operationSuccess: (operation: string, entity?: string) => {
    return enhancedToast.success({
      title: 'Operação Realizada',
      description: `${operation}${entity ? ` ${entity}` : ''} realizada com sucesso.`,
      duration: 4000
    })
  },

  // Batch operation result
  batchResult: (successful: number, failed: number, operation: string) => {
    if (failed === 0) {
      return enhancedToast.success({
        title: 'Operação Concluída',
        description: `${successful} ${operation}(s) processada(s) com sucesso.`
      })
    } else if (successful === 0) {
      return enhancedToast.error({
        title: 'Operação Falhada',
        description: `Todas as ${failed} ${operation}(s) falharam.`
      })
    } else {
      return enhancedToast.warning({
        title: 'Operação Parcial',
        description: `${successful} ${operation}(s) concluída(s), ${failed} falharam.`
      })
    }
  },

  // Connection status
  connectionRestored: () => {
    return enhancedToast.success({
      title: 'Conexão Restaurada',
      description: 'A conexão com o servidor foi restabelecida.',
      duration: 3000
    })
  },

  connectionLost: () => {
    return enhancedToast.warning({
      title: 'Conexão Perdida',
      description: 'Verifique sua conexão com a internet.',
      persistent: true
    })
  },

  // Data sync
  dataSynced: () => {
    return enhancedToast.info({
      title: 'Dados Sincronizados',
      description: 'Seus dados foram atualizados com o servidor.',
      duration: 3000
    })
  },

  // Auto-save
  autoSaved: () => {
    return enhancedToast.info({
      title: 'Salvamento Automático',
      description: 'Suas alterações foram salvas automaticamente.',
      duration: 2000
    })
  }
}

// Hook for using enhanced toasts
export const useEnhancedToast = () => {
  return enhancedToast
}

export default enhancedToast