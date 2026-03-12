/* eslint-disable @typescript-eslint/no-explicit-any */

declare module 'react-hook-form' {
  export type FieldValues = object
  export type FieldPath<TFieldValues extends FieldValues = FieldValues> = [
    keyof TFieldValues,
  ] extends [never]
    ? string
    : Extract<keyof TFieldValues, string>

  export interface FormState<TFieldValues extends FieldValues = FieldValues> {
    errors: Partial<Record<FieldPath<TFieldValues>, { message?: string }>>
    isDirty?: boolean
    isValid?: boolean
    isSubmitting?: boolean
    isSubmitSuccessful?: boolean
    isValidating?: boolean
  }

  export interface UseFormReturn<TFieldValues extends FieldValues = FieldValues> {
    register: (name: FieldPath<TFieldValues>, options?: unknown) => Record<string, unknown>
    handleSubmit: (
      handler: (values: TFieldValues) => void | Promise<void>
    ) => (event?: unknown) => void
    control: unknown
    formState: FormState<TFieldValues>
    reset: (values?: Partial<TFieldValues>) => void
    setValue: (name: FieldPath<TFieldValues>, value: unknown, options?: unknown) => void
    getValues: () => TFieldValues
    watch(): TFieldValues
    watch<TFieldName extends FieldPath<TFieldValues>>(name: TFieldName): TFieldValues[TFieldName]
    watch(names: FieldPath<TFieldValues>[]): Array<TFieldValues[FieldPath<TFieldValues>]>
    trigger: (name?: FieldPath<TFieldValues> | FieldPath<TFieldValues>[]) => Promise<boolean>
    clearErrors: (name?: FieldPath<TFieldValues> | FieldPath<TFieldValues>[]) => void
    setError: (name: FieldPath<TFieldValues>, error: { type?: string; message?: string }) => void
    setFocus: (name: FieldPath<TFieldValues>) => void
    getFieldState: (
      name: FieldPath<TFieldValues>,
      formState: FormState<TFieldValues>
    ) => {
      error?: { message?: string }
    }
  }

  export interface ControllerProps<
    TFieldValues extends FieldValues = FieldValues,
    TName extends FieldPath<TFieldValues> = FieldPath<TFieldValues>,
  > {
    name: TName
    control?: unknown
    defaultValue?: unknown
    rules?: Record<string, unknown>
    render: (props: {
      field: Record<string, unknown>
      fieldState: Record<string, unknown>
      formState: Record<string, unknown>
    }) => import('react').ReactElement
  }

  export const Controller: import('react').ComponentType<ControllerProps>
  export function FormProvider<TFieldValues extends FieldValues = FieldValues>(
    props: { children: import('react').ReactNode } & UseFormReturn<TFieldValues>
  ): import('react').ReactElement
  export function useFormContext<
    TFieldValues extends FieldValues = FieldValues,
  >(): UseFormReturn<TFieldValues>
  export function useForm<TFieldValues extends FieldValues = FieldValues>(
    options?: Record<string, unknown>
  ): UseFormReturn<TFieldValues>
  export type SubmitHandler<TFieldValues extends FieldValues = FieldValues> = (
    values: TFieldValues
  ) => void | Promise<void>
}

declare module '@hookform/resolvers/zod' {
  export function zodResolver(
    schema: unknown,
    schemaOptions?: unknown,
    resolverOptions?: unknown
  ): (values: unknown, context: unknown, options: unknown) => Promise<unknown>
}

declare module 'recharts' {
  export type TooltipPayload<TValue = number, TName = string> = {
    value?: TValue
    name?: TName
    color?: string
    dataKey?: string
    payload?: Record<string, unknown>
  }

  export type TooltipProps<TValue = number, TName = string> = {
    active?: boolean
    payload?: TooltipPayload<TValue, TName>[]
    label?: string
  }

  export const LineChart: import('react').ComponentType<any>
  export const AreaChart: import('react').ComponentType<any>
  export const BarChart: import('react').ComponentType<any>
  export const PieChart: import('react').ComponentType<any>
  export const RadarChart: import('react').ComponentType<any>
  export const RadialBarChart: import('react').ComponentType<any>
  export const ScatterChart: import('react').ComponentType<any>
  export const ComposedChart: import('react').ComponentType<any>
  export const FunnelChart: import('react').ComponentType<any>
  export const Treemap: import('react').ComponentType<any>
  export const Sankey: import('react').ComponentType<any>

  export const XAxis: import('react').ComponentType<any>
  export const YAxis: import('react').ComponentType<any>
  export const ZAxis: import('react').ComponentType<any>
  export const CartesianGrid: import('react').ComponentType<any>
  export const PolarGrid: import('react').ComponentType<any>
  export const PolarAngleAxis: import('react').ComponentType<any>
  export const PolarRadiusAxis: import('react').ComponentType<any>
  export const Tooltip: import('react').ComponentType<any>
  export const Legend: import('react').ComponentType<any>
  export const ResponsiveContainer: import('react').ComponentType<any>
  export const Line: import('react').ComponentType<any>
  export const Area: import('react').ComponentType<any>
  export const Bar: import('react').ComponentType<any>
  export const Cell: import('react').ComponentType<any>
  export const Pie: import('react').ComponentType<any>
  export const Radar: import('react').ComponentType<any>
  export const RadialBar: import('react').ComponentType<any>
  export const Scatter: import('react').ComponentType<any>
  export const Funnel: import('react').ComponentType<any>
  export const ReferenceLine: import('react').ComponentType<any>
  export const ReferenceArea: import('react').ComponentType<any>
  export const ReferenceDot: import('react').ComponentType<any>
  export const Brush: import('react').ComponentType<any>
  export const Label: import('react').ComponentType<any>
  export const LabelList: import('react').ComponentType<any>
  export const Customized: import('react').ComponentType<any>
  export const Rectangle: import('react').ComponentType<any>
  export const Sector: import('react').ComponentType<any>
  export const Curve: import('react').ComponentType<any>
  export const Cross: import('react').ComponentType<any>
  export const Dot: import('react').ComponentType<any>
  export const Polygon: import('react').ComponentType<any>
}

declare module '@sentry/types' {
  export type Primitive = string | number | boolean | bigint | symbol | null | undefined

  export interface Request {
    headers?: Record<string, string>
    url?: string
    method?: string
  }

  export interface Event {
    environment?: string
    level?: string
    message?: string
    tags?: Record<string, Primitive>
    user?: Record<string, unknown>
    extra?: Record<string, unknown>
    request?: Request
  }

  export interface ErrorEvent extends Event {}

  export interface TransactionEvent extends Event {
    timestamp?: number
    start_timestamp?: number
    spans?: unknown[]
  }

  export type EventHint = unknown

  export interface Transaction extends TransactionEvent {}
}
