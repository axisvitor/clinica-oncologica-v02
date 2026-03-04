import * as React from 'react'
import { CircleIcon } from 'lucide-react'

import { cn } from '@/lib/utils'

const itemClassName =
  'border-input text-primary focus-visible:border-ring focus-visible:ring-ring/50 aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive dark:bg-input/30 aspect-square size-4 shrink-0 rounded-full border shadow-xs transition-[color,box-shadow] outline-none focus-visible:ring-[3px] disabled:cursor-not-allowed disabled:opacity-50'

type RadioGroupValueContext = {
  value?: string
  onValueChange?: (value: string) => void
  disabled?: boolean
}

const RadioGroupContext = React.createContext<RadioGroupValueContext | null>(null)

type RadioGroupProps = React.HTMLAttributes<HTMLDivElement> & {
  value?: string
  defaultValue?: string
  onValueChange?: (value: string) => void
  disabled?: boolean
}

type RadioGroupItemProps = Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'value'> & {
  value: string
}

const RadioGroup = React.forwardRef<HTMLDivElement, RadioGroupProps>(
  ({ className, value, defaultValue, onValueChange, disabled, ...props }, ref) => {
    const [internalValue, setInternalValue] = React.useState<string | undefined>(defaultValue)
    const currentValue = value ?? internalValue

    const handleValueChange = React.useCallback(
      (nextValue: string) => {
        if (value === undefined) {
          setInternalValue(nextValue)
        }
        onValueChange?.(nextValue)
      },
      [onValueChange, value]
    )

    return (
      <RadioGroupContext.Provider
        value={{ value: currentValue, onValueChange: handleValueChange, disabled }}
      >
        <div
          ref={ref}
          role="radiogroup"
          data-slot="radio-group"
          className={cn('grid gap-3', className)}
          {...props}
        />
      </RadioGroupContext.Provider>
    )
  }
)
RadioGroup.displayName = 'RadioGroup'

const RadioGroupItem = React.forwardRef<HTMLButtonElement, RadioGroupItemProps>(
  ({ className, value, disabled, onClick, ...props }, ref) => {
    const group = React.useContext(RadioGroupContext)
    const checked = group?.value === value
    const isDisabled = Boolean(group?.disabled || disabled)

    return (
      <button
        ref={ref}
        type="button"
        role="radio"
        aria-checked={checked}
        data-state={checked ? 'checked' : 'unchecked'}
        data-slot="radio-group-item"
        disabled={isDisabled}
        className={cn(itemClassName, className)}
        onClick={(event) => {
          onClick?.(event)
          if (!event.defaultPrevented && !isDisabled) {
            group?.onValueChange?.(value)
          }
        }}
        {...props}
      >
        {checked ? (
          <span
            data-slot="radio-group-indicator"
            className="relative flex items-center justify-center"
          >
            <CircleIcon className="fill-primary absolute top-1/2 left-1/2 size-2 -translate-x-1/2 -translate-y-1/2" />
          </span>
        ) : null}
      </button>
    )
  }
)
RadioGroupItem.displayName = 'RadioGroupItem'

export { RadioGroup, RadioGroupItem }
