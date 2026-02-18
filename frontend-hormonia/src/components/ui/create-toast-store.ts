import * as React from 'react'

interface ToastStoreConfig {
  limit?: number
  removeDelay?: number
}

type ToasterToast<TToastProps, TActionElement> = TToastProps & {
  id: string
  title?: React.ReactNode
  description?: React.ReactNode
  action?: TActionElement
}

type Action<TToastProps, TActionElement> =
  | {
      type: 'ADD_TOAST'
      toast: ToasterToast<TToastProps, TActionElement>
    }
  | {
      type: 'UPDATE_TOAST'
      toast: Partial<ToasterToast<TToastProps, TActionElement>>
    }
  | {
      type: 'DISMISS_TOAST'
      toastId?: string
    }
  | {
      type: 'REMOVE_TOAST'
      toastId?: string
    }

type State<TToastProps, TActionElement> = {
  toasts: Array<ToasterToast<TToastProps, TActionElement>>
}

export function createToastStore<
  TToastProps extends Record<string, unknown>,
  TActionElement,
>(config: ToastStoreConfig = {}) {
  const TOAST_LIMIT = config.limit ?? 1
  const TOAST_REMOVE_DELAY = config.removeDelay ?? 1000000

  let count = 0
  const toastTimeouts = new Map<string, ReturnType<typeof setTimeout>>()
  const listeners: Array<(state: State<TToastProps, TActionElement>) => void> = []
  let memoryState: State<TToastProps, TActionElement> = { toasts: [] }

  function genId() {
    count = (count + 1) % Number.MAX_SAFE_INTEGER
    return count.toString()
  }

  function addToRemoveQueue(toastId: string) {
    if (toastTimeouts.has(toastId)) {
      return
    }

    const timeout = setTimeout(() => {
      toastTimeouts.delete(toastId)
      dispatch({
        type: 'REMOVE_TOAST',
        toastId,
      })
    }, TOAST_REMOVE_DELAY)

    toastTimeouts.set(toastId, timeout)
  }

  function reducer(
    state: State<TToastProps, TActionElement>,
    action: Action<TToastProps, TActionElement>
  ): State<TToastProps, TActionElement> {
    switch (action.type) {
      case 'ADD_TOAST':
        return {
          ...state,
          toasts: [action.toast, ...state.toasts].slice(0, TOAST_LIMIT),
        }

      case 'UPDATE_TOAST':
        return {
          ...state,
          toasts: state.toasts.map((toast) =>
            toast.id === action.toast.id ? { ...toast, ...action.toast } : toast
          ),
        }

      case 'DISMISS_TOAST': {
        const { toastId } = action
        if (toastId) {
          addToRemoveQueue(toastId)
        } else {
          state.toasts.forEach((toast) => {
            addToRemoveQueue(toast.id)
          })
        }

        return {
          ...state,
          toasts: state.toasts.map((toast) =>
            toast.id === toastId || toastId === undefined
              ? {
                  ...toast,
                  open: false,
                }
              : toast
          ),
        }
      }

      case 'REMOVE_TOAST':
        if (action.toastId === undefined) {
          return {
            ...state,
            toasts: [],
          }
        }

        return {
          ...state,
          toasts: state.toasts.filter((toast) => toast.id !== action.toastId),
        }
    }
  }

  function dispatch(action: Action<TToastProps, TActionElement>) {
    memoryState = reducer(memoryState, action)
    listeners.forEach((listener) => {
      listener(memoryState)
    })
  }

  type Toast = Omit<ToasterToast<TToastProps, TActionElement>, 'id'>

  function toast(props: Toast) {
    const id = genId()

    const update = (nextToast: ToasterToast<TToastProps, TActionElement>) =>
      dispatch({
        type: 'UPDATE_TOAST',
        toast: { ...nextToast, id },
      })

    const dismiss = () => dispatch({ type: 'DISMISS_TOAST', toastId: id })

    dispatch({
      type: 'ADD_TOAST',
      toast: {
        ...props,
        id,
        open: true,
        onOpenChange: (open: boolean) => {
          if (!open) {
            dismiss()
          }
        },
      } as ToasterToast<TToastProps, TActionElement>,
    })

    return {
      id,
      dismiss,
      update,
    }
  }

  function useToast() {
    const [state, setState] = React.useState<State<TToastProps, TActionElement>>(
      memoryState
    )

    React.useEffect(() => {
      listeners.push(setState)
      return () => {
        const index = listeners.indexOf(setState)
        if (index > -1) {
          listeners.splice(index, 1)
        }
      }
    }, [])

    return {
      ...state,
      toast,
      dismiss: (toastId?: string) => dispatch({ type: 'DISMISS_TOAST', toastId }),
    }
  }

  return {
    reducer,
    toast,
    useToast,
  }
}
