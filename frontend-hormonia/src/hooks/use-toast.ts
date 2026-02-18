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

function dispatchSonnerToast(options: ToastOptions) {
  const { variant = 'default', duration = 5000 } = options
  const title = options.title || options.description
  const description = options.title ? options.description : undefined
  const shared = {
    description,
    duration,
    action: options.action,
  }

  if (variant === 'destructive') {
    sonnerToast.error(title, shared)
    return
  }

  if (variant === 'success') {
    sonnerToast.success(title, shared)
    return
  }

  if (variant === 'warning') {
    sonnerToast.warning(title, shared)
    return
  }

  sonnerToast(title, shared)
}

export function useToast() {
  const [toasts, setToasts] = useState<Toast[]>([])

  const toast = (options: ToastOptions) => {
    const id = `toast-${++toastCount}`
    const { variant = 'default', duration = 5000, ...rest } = options

    dispatchSonnerToast(options)

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
  dispatchSonnerToast(options)
}
