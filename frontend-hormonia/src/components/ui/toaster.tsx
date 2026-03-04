import { useToast } from '@/components/ui/use-toast'
import {
  Toast,
  ToastClose,
  ToastDescription,
  ToastProvider,
  ToastTitle,
  ToastViewport,
} from '@/components/ui/toast'

export function Toaster() {
  const { toasts } = useToast()

  // Group toasts by position to create multiple viewports
  const toastsByPosition = toasts.reduce(
    (acc, toast) => {
      const position = 'bottom-right' // Default position since position property doesn't exist
      if (!acc[position]) {
        acc[position] = []
      }
      acc[position].push(toast)
      return acc
    },
    {} as Record<string, typeof toasts>
  )

  return (
    <ToastProvider>
      {Object.entries(toastsByPosition).map(([position, positionToasts]) => (
        <div key={position}>
          {positionToasts.map(function ({ id, title, description, action, ...props }) {
            return (
              <Toast key={id} {...props}>
                <div className="grid gap-1">
                  {title && <ToastTitle>{title}</ToastTitle>}
                  {description && <ToastDescription>{description}</ToastDescription>}
                </div>
                {action}
                <ToastClose />
              </Toast>
            )
          })}
          <ToastViewport
            position={
              position as
                | 'top-left'
                | 'top-center'
                | 'top-right'
                | 'bottom-left'
                | 'bottom-center'
                | 'bottom-right'
            }
          />
        </div>
      ))}
      {/* Fallback viewport when no toasts are present */}
      {toasts.length === 0 && <ToastViewport />}
    </ToastProvider>
  )
}
