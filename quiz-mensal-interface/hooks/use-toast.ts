'use client'

import type { ToastActionElement, ToastProps } from '@/components/ui/toast'
import { createToastStore } from '@/lib/create-toast-store'

export const { reducer, toast, useToast } = createToastStore<ToastProps, ToastActionElement>({
  removeDelay: 5000,
})
