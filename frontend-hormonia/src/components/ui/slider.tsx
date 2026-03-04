import * as React from 'react'

import { cn } from '@/lib/utils'

interface SliderProps extends Omit<
  React.InputHTMLAttributes<HTMLInputElement>,
  'value' | 'defaultValue' | 'min' | 'max' | 'step'
> {
  defaultValue?: number[] | undefined
  value?: number[] | undefined
  min?: number
  max?: number
  step?: number
  onValueChange?: (value: number[]) => void
}

function Slider({ className, defaultValue, value, min = 0, max = 100, ...props }: SliderProps) {
  const [internalValue, setInternalValue] = React.useState<number>(
    Array.isArray(defaultValue) ? (defaultValue[0] ?? min) : min
  )
  const currentValue = Array.isArray(value) ? (value[0] ?? min) : internalValue
  const { onValueChange, onChange, ...inputProps } = props

  return (
    <input
      type="range"
      data-slot="slider"
      value={currentValue}
      min={min}
      max={max}
      className={cn('w-full accent-primary data-[disabled]:opacity-50', className)}
      onChange={(event) => {
        const nextValue = Number(event.target.value)
        if (!Array.isArray(value)) {
          setInternalValue(nextValue)
        }
        onValueChange?.([nextValue])
        onChange?.(event)
      }}
      {...inputProps}
    />
  )
}

export { Slider }
