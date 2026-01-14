import { useState } from 'react'
import { toast as sonnerToast } from 'sonner'

export interface ToastOptions {
  title?: string
  description?: string
  variant?: 'default' | 'destructive' | 'success' | 'warning'
  duration?: number
  action?: {
    label: string
    onClick: () => void
  }
}

export interface Toast extends ToastOptions {
  id: string
}

let toastCount = 0

export function useToast() {
  const [toasts, setToasts] = useState<Toast[]>([])

  const toast = (options: ToastOptions) => {
    const id = `toast-${++toastCount}`
    const { variant = 'default', duration = 5000, ...rest } = options

    // Map to sonner toast based on variant
    if (variant === 'destructive') {
      sonnerToast.error(options.title || options.description, {
        description: options.title ? options.description : undefined,
        duration,
        action: options.action
      })
    } else if (variant === 'success') {
      sonnerToast.success(options.title || options.description, {
        description: options.title ? options.description : undefined,
        duration,
        action: options.action
      })
    } else if (variant === 'warning') {
      sonnerToast.warning(options.title || options.description, {
        description: options.title ? options.description : undefined,
        duration,
        action: options.action
      })
    } else {
      sonnerToast(options.title || options.description, {
        description: options.title ? options.description : undefined,
        duration,
        action: options.action
      })
    }

    const newToast: Toast = { id, variant, duration, ...rest }
    setToasts((prev) => [...prev, newToast])

    // Auto-remove toast after duration
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, duration)

    return id
  }

  const dismiss = (id?: string) => {
    if (id) {
      sonnerToast.dismiss(id)
      setToasts((prev) => prev.filter((t) => t.id !== id))
    } else {
      sonnerToast.dismiss()
      setToasts([])
    }
  }

  return {
    toast,
    dismiss,
    toasts
  }
}

// Standalone toast function for direct import
export const toast = (options: ToastOptions) => {
  const { variant = 'default', duration = 5000 } = options

  // Map to sonner toast based on variant
  if (variant === 'destructive') {
    sonnerToast.error(options.title || options.description, {
      description: options.title ? options.description : undefined,
      duration,
      action: options.action
    })
  } else if (variant === 'success') {
    sonnerToast.success(options.title || options.description, {
      description: options.title ? options.description : undefined,
      duration,
      action: options.action
    })
  } else if (variant === 'warning') {
    sonnerToast.warning(options.title || options.description, {
      description: options.title ? options.description : undefined,
      duration,
      action: options.action
    })
  } else {
    sonnerToast(options.title || options.description, {
      description: options.title ? options.description : undefined,
      duration,
      action: options.action
    })
  }
}