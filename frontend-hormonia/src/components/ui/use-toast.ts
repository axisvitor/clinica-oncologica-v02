import type { ToastActionElement, ToastProps } from '@/components/ui/toast'
import { createToastStore } from '@/components/ui/create-toast-store'

export const { reducer, toast, useToast } = createToastStore<
  ToastProps,
  ToastActionElement
>({
  removeDelay: 1000000,
})
