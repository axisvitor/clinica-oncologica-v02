import * as React from 'react'
import * as ToastPrimitives from '@radix-ui/react-toast'
import { X } from 'lucide-react'

import { cn } from '@/lib/utils'

interface ToastCloseOptions {
  ariaLabel?: string
}

export function createToastAction(defaultClassName: string) {
  const ToastAction = React.forwardRef<
    React.ElementRef<typeof ToastPrimitives.Action>,
    React.ComponentPropsWithoutRef<typeof ToastPrimitives.Action>
  >(({ className, ...props }, ref) => (
    <ToastPrimitives.Action
      ref={ref}
      className={cn(defaultClassName, className)}
      {...props}
    />
  ))

  ToastAction.displayName = ToastPrimitives.Action.displayName
  return ToastAction
}

export function createToastClose(
  defaultClassName: string,
  options: ToastCloseOptions = {}
) {
  const ToastClose = React.forwardRef<
    React.ElementRef<typeof ToastPrimitives.Close>,
    React.ComponentPropsWithoutRef<typeof ToastPrimitives.Close>
  >(({ className, ...props }, ref) => (
    <ToastPrimitives.Close
      ref={ref}
      className={cn(defaultClassName, className)}
      toast-close=""
      aria-label={options.ariaLabel}
      {...props}
    >
      <X className="h-4 w-4" />
    </ToastPrimitives.Close>
  ))

  ToastClose.displayName = ToastPrimitives.Close.displayName
  return ToastClose
}

export function createToastTitle(defaultClassName: string) {
  const ToastTitle = React.forwardRef<
    React.ElementRef<typeof ToastPrimitives.Title>,
    React.ComponentPropsWithoutRef<typeof ToastPrimitives.Title>
  >(({ className, ...props }, ref) => (
    <ToastPrimitives.Title
      ref={ref}
      className={cn(defaultClassName, className)}
      {...props}
    />
  ))

  ToastTitle.displayName = ToastPrimitives.Title.displayName
  return ToastTitle
}

export function createToastDescription(defaultClassName: string) {
  const ToastDescription = React.forwardRef<
    React.ElementRef<typeof ToastPrimitives.Description>,
    React.ComponentPropsWithoutRef<typeof ToastPrimitives.Description>
  >(({ className, ...props }, ref) => (
    <ToastPrimitives.Description
      ref={ref}
      className={cn(defaultClassName, className)}
      {...props}
    />
  ))

  ToastDescription.displayName = ToastPrimitives.Description.displayName
  return ToastDescription
}
