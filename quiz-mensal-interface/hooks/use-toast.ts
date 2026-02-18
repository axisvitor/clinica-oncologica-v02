'use client'

import type { ToastActionElement, ToastProps } from '@/components/ui/toast'
import { createToastStore } from '../../frontend-hormonia/src/components/ui/create-toast-store'

export const { reducer, toast, useToast } = createToastStore<
  ToastProps,
  ToastActionElement
>({
  removeDelay: 5000,
})
